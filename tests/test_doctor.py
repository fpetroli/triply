"""Tests of the self-test (scripts/doctor.py and the doctor command).

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import datetime
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import doctor  # noqa: E402
import triply  # noqa: E402

NOW = datetime.datetime(2026, 11, 11, 10, 0, tzinfo=datetime.timezone.utc)


def good(url, body, headers):
    """Every service answers as it should, without keys."""
    if "mapbox" in url or "googleapis" in url:
        if "access_token" in url or "X-Goog-Api-Key" in headers:
            return 200, b'{"ok": true}'
        return 401, b'{"message": "Not Authorized - No Token"}'
    return 200, b'{"results": []}'


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.base = Path(self._temp.name).resolve()
        self.data = self.base / "data"

    def tearDown(self):
        self._temp.cleanup()

    def test_all_good(self):
        report = doctor.run(self.base, self.data, {}, NOW, good)
        self.assertTrue(report["ok"], report["problems"])
        self.assertTrue(report["folder"]["writable"])
        self.assertEqual(list(self.base.glob(".triply-doctor-*")), [])
        self.assertEqual(len(report["network"]), 9)
        self.assertEqual(report["blocked_hosts"], [])

    def test_mark_kept_between_runs(self):
        first = doctor.run(self.base, self.data, {}, NOW, good)
        self.assertIsNone(first["data"]["previous_run"])
        second = doctor.run(self.base, self.data, {}, NOW + datetime.timedelta(days=1), good)
        self.assertEqual(second["data"]["previous_run"], NOW.isoformat(timespec="seconds"))
        self.assertEqual(json.loads((self.data / "doctor.json").read_text())["runs"], 2)

    def test_blocked_by_a_proxy(self):
        def proxy(url, body, headers):
            if "nominatim" in url:
                return 403, b"Host not in allowlist"
            if "nagerholidays" in url:
                raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")
            return good(url, body, headers)

        report = doctor.run(self.base, self.data, {}, NOW, proxy)
        self.assertFalse(report["ok"])
        self.assertEqual(report["blocked_hosts"], ["nagerholidays.com", "nominatim.openstreetmap.org"])
        self.assertIn("not an answer of the service", " ".join(report["problems"]))

    def test_keys_used_and_never_printed(self):
        seen = []

        def refuse_google(url, body, headers):
            seen.append((url, headers))
            if "googleapis" in url:
                return 403, b'{"error": {"status": "PERMISSION_DENIED"}}'
            return good(url, body, headers)

        keys = {"mapbox": "pk.mapbox-secret-value-123456789", "google": "AIza-google-secret-value-123456789"}
        report = doctor.run(self.base, self.data, keys, NOW, refuse_google)
        text = json.dumps(report)
        self.assertNotIn("secret", text)
        self.assertTrue(any("access_token=pk.mapbox" in url for url, _ in seen))
        self.assertTrue(any(h.get("X-Goog-Api-Key") == keys["google"] for _, h in seen))
        services = {entry["service"]: entry for entry in report["network"]}
        self.assertTrue(services["Mapbox"]["ok"])
        self.assertFalse(services["Google Places"]["ok"])
        self.assertIn("key is refused", services["Google Routes"]["detail"])
        self.assertEqual(report["data"]["keys"], {"mapbox": True, "google": True})

    def test_folder_missing_and_no_data(self):
        report = doctor.run(self.base / "missing", None, {}, NOW, good)
        self.assertFalse(report["ok"])
        self.assertFalse(report["folder"]["exists"])
        self.assertFalse(report["data"]["writable"])
        self.assertEqual(len(report["problems"]), 2)

    def test_command_finds_trips_folder(self):
        trips = self.base / "Viaggi"
        (trips / ".triply").mkdir(parents=True)
        out = io.StringIO()
        with mock.patch.object(doctor, "http_probe", good), mock.patch.object(sys, "stdout", out):
            code = triply.main(["doctor", "--folder", str(trips), "--data", str(self.data)])
        result = json.loads(out.getvalue())
        self.assertEqual(code, 0, result["problems"])
        self.assertEqual(result["folder"]["trips_folder"], str(trips))


if __name__ == "__main__":
    unittest.main()
