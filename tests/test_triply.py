"""Tests of the trips folder management (scripts/triply.py).

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import datetime
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import climate  # noqa: E402
import triply  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run(*args):
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        code = triply.main(list(args))
    finally:
        sys.stdout = old
    return code, json.loads(out.getvalue())


class TripsFolderTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.base = Path(self._temp.name).resolve()
        self.data = self.base / "plugin-data"
        self.folder = self.base / "Viaggi"

    def tearDown(self):
        self._temp.cleanup()

    def write_profile(self):
        profile = (FIXTURES / "valid_profile.json").read_text(encoding="utf-8")
        (self.folder / ".triply" / "profile.json").write_text(profile, encoding="utf-8")

    def test_nothing_found(self):
        code, result = run("locate", "--start", str(self.base), "--data", str(self.data))
        self.assertEqual(code, 0)
        self.assertIsNone(result["trips_folder"])
        self.assertFalse(result["profile"])

    def test_init_then_locate_from_anywhere(self):
        code, result = run("init", str(self.folder), "--data", str(self.data))
        self.assertEqual(code, 0)
        self.assertTrue((self.folder / ".triply").is_dir())
        self.assertFalse(result["profile"])
        code, result = run("locate", "--start", str(self.base), "--data", str(self.data))
        self.assertEqual(result["trips_folder"], str(self.folder))
        self.assertEqual(result["found_by"], "remembered")

    def test_locate_inside_the_current_folder(self):
        run("init", str(self.folder))
        self.write_profile()
        code, result = run("locate", "--start", str(self.base))
        self.assertEqual(result["trips_folder"], str(self.folder))
        self.assertEqual(result["found_by"], "folder")

    def test_init_keeps_existing_files(self):
        self.folder.mkdir()
        (self.folder / "notes.txt").write_text("mine", encoding="utf-8")
        run("init", str(self.folder))
        self.assertEqual((self.folder / "notes.txt").read_text(encoding="utf-8"), "mine")

    def test_new_trip_needs_a_profile(self):
        run("init", str(self.folder))
        code, result = run("new-trip", str(self.folder), "--title", "Giappone 2027")
        self.assertEqual(code, 1)
        self.assertIn("no user profile", result["refused"])

    def test_new_trip_and_locate_from_inside(self):
        run("init", str(self.folder))
        self.write_profile()
        with mock.patch.object(triply, "today", return_value="2027-01-10"):
            code, result = run("new-trip", str(self.folder), "--title", "Giappone 2027")
        self.assertEqual(code, 0, result)
        trip_folder = self.folder / "Giappone 2027"
        data = json.loads((trip_folder / ".triply" / "trip.json").read_text(encoding="utf-8"))
        self.assertEqual(data["trip"]["id"], "giappone-2027")
        self.assertEqual(data["trip"]["language"], "it")
        self.assertEqual(data["trip"]["currency"], "EUR")
        self.assertEqual(data["trip"]["created"], "2027-01-10")
        self.assertEqual(data["progress"]["phase"], "brief")

        inside = trip_folder / "biglietti"
        inside.mkdir()
        code, result = run("locate", "--start", str(inside))
        self.assertEqual(result["current_trip"], str(trip_folder))
        self.assertEqual(result["trips_folder"], str(self.folder))
        self.assertEqual(result["found_by"], "folder")
        self.assertTrue(result["profile"])
        self.assertEqual([t["title"] for t in result["trips"]], ["Giappone 2027"])

    def test_new_trip_never_overwrites(self):
        run("init", str(self.folder))
        self.write_profile()
        run("new-trip", str(self.folder), "--title", "Islanda")
        code, result = run("new-trip", str(self.folder), "--title", "Islanda")
        self.assertEqual(code, 1)
        self.assertIn("already exists", result["refused"])

    def test_new_trip_travellers(self):
        run("init", str(self.folder))
        self.write_profile()
        code, result = run("new-trip", str(self.folder), "--title", "Islanda", "--travellers", "anna")
        self.assertEqual(code, 0, result)
        data = json.loads(Path(result["trip_file"]).read_text(encoding="utf-8"))
        self.assertEqual([t["id"] for t in data["travellers"]], ["anna"])
        code, result = run("new-trip", str(self.folder), "--title", "Norvegia", "--travellers", "anna,bob")
        self.assertEqual(code, 1)
        self.assertIn("bob", result["refused"])

    def test_check_updates_the_date_only_when_valid(self):
        run("init", str(self.folder))
        self.write_profile()
        with mock.patch.object(triply, "today", return_value="2027-01-10"):
            _, created = run("new-trip", str(self.folder), "--title", "Islanda")
        trip_file = Path(created["trip_file"])

        with mock.patch.object(triply, "today", return_value="2027-01-12"):
            code, result = run("check", created["trip_folder"])
        self.assertEqual(code, 0, result)
        self.assertEqual(json.loads(trip_file.read_text(encoding="utf-8"))["trip"]["updated"], "2027-01-12")
        self.assertEqual(result["talk_to_user_in"], json.loads(trip_file.read_text(encoding="utf-8"))["trip"]["language"])

        data = json.loads(trip_file.read_text(encoding="utf-8"))
        data["trip"]["status"] = "dreaming"
        trip_file.write_text(json.dumps(data), encoding="utf-8")
        with mock.patch.object(triply, "today", return_value="2027-01-15"):
            code, result = run("check", created["trip_folder"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(trip_file.read_text(encoding="utf-8"))["trip"]["updated"], "2027-01-12")

    def test_check_profile(self):
        run("init", str(self.folder))
        self.write_profile()
        code, result = run("check", str(self.folder))
        self.assertEqual(code, 0, result)
        self.assertEqual(result["kind"], "profile")

    def test_unreadable_file(self):
        run("init", str(self.folder))
        (self.folder / ".triply" / "profile.json").write_text("{ broken", encoding="utf-8")
        code, _ = run("check", str(self.folder))
        self.assertEqual(code, 2)


    def test_rename_trip(self):
        run("init", str(self.folder))
        self.write_profile()
        _, created = run("new-trip", str(self.folder), "--title", "Agosto 2027")
        (Path(created["trip_folder"]) / "biglietto.pdf").write_text("mine", encoding="utf-8")
        code, result = run("rename-trip", created["trip_folder"], "--title", "Sardegna 2027")
        self.assertEqual(code, 0, result)
        renamed = self.folder / "Sardegna 2027"
        self.assertFalse(Path(created["trip_folder"]).exists())
        self.assertEqual((renamed / "biglietto.pdf").read_text(encoding="utf-8"), "mine")
        data = json.loads((renamed / ".triply" / "trip.json").read_text(encoding="utf-8"))
        self.assertEqual(data["trip"]["title"], "Sardegna 2027")
        self.assertEqual(data["trip"]["id"], "agosto-2027")

    def test_rename_trip_never_overwrites(self):
        run("init", str(self.folder))
        self.write_profile()
        _, first = run("new-trip", str(self.folder), "--title", "Agosto 2027")
        run("new-trip", str(self.folder), "--title", "Sardegna 2027")
        code, result = run("rename-trip", first["trip_folder"], "--title", "Sardegna 2027")
        self.assertEqual(code, 1)
        self.assertIn("already exists", result["refused"])


    def test_rename_trip_only_the_case(self):
        run("init", str(self.folder))
        self.write_profile()
        _, created = run("new-trip", str(self.folder), "--title", "sardegna 2027")
        code, result = run("rename-trip", created["trip_folder"], "--title", "Sardegna 2027")
        self.assertEqual(code, 0, result)
        self.assertEqual([p.name for p in self.folder.iterdir() if not p.name.startswith(".")], ["Sardegna 2027"])

    def test_same_folder(self):
        # On Windows and macOS "sardegna" and "Sardegna" are one folder: a
        # rename that only changes the case must not look like a clash.
        self.folder.mkdir()
        other = self.base / "Altro"
        other.mkdir()
        self.assertTrue(triply._same_folder(self.base / "." / "Viaggi", self.folder))
        self.assertFalse(triply._same_folder(other, self.folder))
        self.assertFalse(triply._same_folder(self.base / "missing", self.folder))


class OutputTest(unittest.TestCase):
    def test_output_is_utf8_with_a_windows_code_page(self):
        # Windows often gives a script a local code page such as cp1252,
        # which cannot write 東京: the answer must still come out whole.
        script = Path(__file__).resolve().parent.parent / "scripts" / "triply.py"
        env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
        missing = str(Path(tempfile.gettempdir()) / "東京-triply-missing")
        done = subprocess.run([sys.executable, str(script), "check", missing], env=env, capture_output=True)
        self.assertNotIn(b"Traceback", done.stderr)
        result = json.loads(done.stdout.decode("utf-8"))
        self.assertIn("東京", result["refused"])


class PlaceAndClimateTest(unittest.TestCase):
    def fake_archive(self, url):
        """Every day: max 30, min 20; rain 2 mm on the 1st and the 2nd of each month."""
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        first = datetime.date.fromisoformat(query["start_date"][0])
        last = datetime.date.fromisoformat(query["end_date"][0])
        days = [first + datetime.timedelta(days=n) for n in range((last - first).days + 1)]
        return {
            "daily": {
                "time": [d.isoformat() for d in days],
                "temperature_2m_max": [30.0] * len(days),
                "temperature_2m_min": [20.0] * len(days),
                "precipitation_sum": [2.0 if d.day <= 2 else 0.0 for d in days],
            }
        }

    def test_periods_use_complete_years_only(self):
        spans = climate.periods((8, 1), (8, 31), 3, datetime.date(2026, 8, 20))
        self.assertEqual([s[0].year for s in spans], [2023, 2024, 2025])
        spans = climate.periods((8, 1), (8, 31), 3, datetime.date(2026, 11, 6))
        self.assertEqual([s[0].year for s in spans], [2024, 2025, 2026])

    def test_period_across_the_new_year(self):
        spans = climate.periods((12, 20), (1, 10), 2, datetime.date(2026, 11, 6))
        self.assertEqual(spans[-1], (datetime.date(2025, 12, 20), datetime.date(2026, 1, 10)))

    def test_leap_day(self):
        spans = climate.periods((2, 20), (2, 29), 2, datetime.date(2026, 11, 6))
        self.assertEqual([s[1] for s in spans], [datetime.date(2025, 2, 28), datetime.date(2026, 2, 28)])

    def test_climate_averages(self):
        result = climate.climate(39.23, 9.12, "08-01", "08-31", 3, datetime.date(2026, 11, 6), self.fake_archive)
        self.assertEqual(result["years"], [2024, 2025, 2026])
        self.assertEqual(result["temp_max_c"], 30.0)
        self.assertEqual(result["temp_min_c"], 20.0)
        self.assertEqual(result["precipitation_mm"], 4.0)
        self.assertEqual(result["rain_days"], 2.0)
        self.assertEqual(result["source"]["provider"], "open-meteo")
        self.assertEqual(result["source"]["checked_at"], "2026-11-06")

    def test_climate_without_data(self):
        def empty(url):
            return {"daily": {"time": [], "temperature_2m_max": [], "temperature_2m_min": [], "precipitation_sum": []}}

        with self.assertRaises(climate.ServiceError):
            climate.climate(39.23, 9.12, "08-01", "08-31", 3, datetime.date(2026, 11, 6), empty)

    def test_bad_month_day(self):
        with self.assertRaises(ValueError):
            climate.parse_month_day("08-32")

    def test_find_places(self):
        def fake(url):
            self.assertIn("countryCode=IT", url)
            return {"results": [{"name": "Cagliari", "admin1": "Sardegna", "country_code": "IT",
                                 "country": "Italia", "latitude": 39.23, "longitude": 9.12, "population": 149257}]}

        places = climate.find_places("Cagliari", "it", "it", fetch=fake)
        self.assertEqual(places[0]["region"], "Sardegna")
        self.assertEqual(places[0]["lat"], 39.23)

    def test_service_unavailable(self):
        with mock.patch.object(climate, "fetch_json", side_effect=climate.ServiceError("offline")):
            code, result = run("place", "Cagliari")
        self.assertEqual(code, 1)
        self.assertIn("unavailable", result)

    def test_place_not_found(self):
        with mock.patch.object(climate, "fetch_json", return_value={}):
            code, result = run("place", "Nowhereland")
        self.assertEqual(code, 1)
        self.assertIn("no place found", result["refused"])


class GuideTest(unittest.TestCase):
    def test_every_topic_named_in_the_instructions_exists(self):
        texts = [p.read_text(encoding="utf-8") for p in (ROOT / "skills" / "plan-trip").rglob("*.md")]
        named = {topic for text in texts for topic in re.findall(r"`guide ([a-z-]+)`", text)}
        self.assertTrue(named)
        self.assertLessEqual(named, set(triply.guide_topics()))

    def test_guide_prints_the_topic(self):
        out = io.StringIO()
        old = sys.stdout
        sys.stdout = out
        try:
            code = triply.main(["guide", "setup"])
        finally:
            sys.stdout = old
        self.assertEqual(code, 0)
        self.assertIn("Phase 0", out.getvalue())
        self.assertTrue(out.getvalue().startswith("> Write every message to the user"))

    def test_unknown_topic(self):
        with self.assertRaises(triply.RefusedError):
            triply.cmd_guide("../SKILL")


class NamesTest(unittest.TestCase):
    def test_folder_name(self):
        self.assertEqual(triply.folder_name('Parigi: weekend / "lungo"'), "Parigi weekend lungo")
        self.assertEqual(triply.folder_name("Côte d'Azur 2027."), "Côte d'Azur 2027")
        with self.assertRaises(ValueError):
            triply.folder_name("  ?? ")
        with self.assertRaises(ValueError):
            triply.folder_name("CON")

    def test_slug(self):
        self.assertEqual(triply.slug("Côte d'Azur 2027"), "cote-d-azur-2027")
        self.assertEqual(triply.slug("東京"), "trip")


if __name__ == "__main__":
    unittest.main()
