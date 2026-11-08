"""Tests of the search of points of interest and of the map service keys.

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import io
import json
import os
import stat
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import climate  # noqa: E402
import places  # noqa: E402
import triply  # noqa: E402

MAPBOX_KEY = "pk.eyJ1IjoidGVzdCIsImEiOiJjbGV4YW1wbGUifQ.abcdefghij"
GOOGLE_KEY = "AIzaSyA-abcdefghijklmnopqrstuvwxyz12345"


def run(*args):
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        code = triply.main(list(args))
    finally:
        sys.stdout = old
    return code, out.getvalue()


def query_of(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


class ProvidersTest(unittest.TestCase):
    def test_osm(self):
        def fake(url, body, headers):
            q = query_of(url)
            self.assertEqual(q["q"], "Senso-ji")
            self.assertEqual(q["countrycodes"], "jp")
            self.assertEqual(q["bounded"], "0")
            self.assertIsNone(body)
            return [{"osm_type": "way", "osm_id": 173154847, "lat": "35.7134", "lon": "139.7955", "name": "Senso-ji",
                     "display_name": "Senso-ji, Asakusa, Tokyo", "category": "amenity", "type": "place_of_worship",
                     "extratags": {"opening_hours": "Mo-Su 06:00-17:00"}}]

        result = places.find("osm", ["Senso-ji"], (35.71, 139.79), "JP", "it", 3, None, "2026-11-08", fake)
        place = result["results"][0]["places"][0]
        self.assertEqual(place["provider_id"], "way/173154847")
        self.assertEqual(place["opening_hours"], "Mo-Su 06:00-17:00")
        self.assertEqual(place["lat"], 35.7134)
        self.assertIn("OpenStreetMap", result["source"]["title"])
        self.assertEqual(result["source"]["checked_at"], "2026-11-08")

    def test_osm_waits_between_queries(self):
        waits = []
        places.find("osm", ["a", "b", "c"], request=lambda u, b, h: [], sleep=waits.append)
        self.assertEqual(len(waits), 2)
        self.assertTrue(all(w >= 1 for w in waits))

    def test_mapbox(self):
        def fake(url, body, headers):
            q = query_of(url)
            self.assertEqual(q["access_token"], MAPBOX_KEY)
            self.assertEqual(q["proximity"], "139.79,35.71")  # longitude first
            return {"type": "FeatureCollection", "features": [
                {"type": "Feature", "geometry": {"type": "Point", "coordinates": [139.7966, 35.7148]},
                 "properties": {"name": "Sensō-ji", "full_address": "2-3-1 Asakusa, Taito, Tokyo", "mapbox_id": "dXJuOm1ieHBvaTo",
                                "feature_type": "poi", "poi_category": ["temple", "place of worship"],
                                "coordinates": {"latitude": 35.7148, "longitude": 139.7966}}}]}

        result = places.find("mapbox", ["Senso-ji"], (35.71, 139.79), key=MAPBOX_KEY, request=fake)
        place = result["results"][0]["places"][0]
        self.assertEqual(place["provider_id"], "dXJuOm1ieHBvaTo")
        self.assertEqual(place["category"], "temple, place of worship")
        self.assertEqual(place["lon"], 139.7966)

    def test_google(self):
        def fake(url, body, headers):
            self.assertEqual(url, places.GOOGLE_URL)
            self.assertEqual(headers["X-Goog-Api-Key"], GOOGLE_KEY)
            self.assertNotIn("OpeningHours", headers["X-Goog-FieldMask"])  # keeps the request in the Pro tier
            self.assertEqual(body["textQuery"], "Senso-ji")
            self.assertEqual(body["locationBias"]["circle"]["center"], {"latitude": 35.71, "longitude": 139.79})
            return {"places": [{"id": "ChIJ8T1GpMGOGGARDYGSgpooDWw", "displayName": {"text": "Sensō-ji"},
                                "formattedAddress": "2 Chome-3-1 Asakusa, Taito City, Tokyo", "types": ["buddhist_temple", "place_of_worship"],
                                "location": {"latitude": 35.7147651, "longitude": 139.7966553},
                                "googleMapsUri": "https://maps.google.com/?cid=1"}]}

        result = places.find("google", ["Senso-ji"], (35.71, 139.79), "JP", key=GOOGLE_KEY, request=fake)
        place = result["results"][0]["places"][0]
        self.assertEqual(place["name"], "Sensō-ji")
        self.assertEqual(place["lat"], 35.714765)
        self.assertEqual(place["url"], "https://maps.google.com/?cid=1")

    def test_one_failed_query_does_not_stop_the_others(self):
        def fake(url, body, headers):
            if query_of(url)["q"] == "bad":
                raise climate.ServiceError("HTTP 500")
            return []

        result = places.find("osm", ["bad", "good"], request=fake, sleep=lambda s: None)
        self.assertIn("error", result["results"][0])
        self.assertNotIn("error", result["results"][1])

    def test_all_queries_failed(self):
        def fake(url, body, headers):
            raise climate.ServiceError("offline")

        with self.assertRaises(climate.ServiceError):
            places.find("osm", ["a"], request=fake)

    def test_near_must_be_a_point(self):
        self.assertEqual(places.parse_near("35.7,139.8"), (35.7, 139.8))
        for bad in ("35.7", "a,b", "95,10"):
            with self.subTest(near=bad), self.assertRaises(ValueError):
                places.parse_near(bad)


class KeysTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.data = Path(self._temp.name) / "plugin-data"

    def tearDown(self):
        self._temp.cleanup()

    def test_save_list_forget_without_printing_the_key(self):
        code, out = run("set-key", "mapbox", MAPBOX_KEY, "--data", str(self.data))
        self.assertEqual(code, 0)
        self.assertNotIn(MAPBOX_KEY, out)
        keys_file = self.data / "keys.json"
        self.assertEqual(json.loads(keys_file.read_text())["mapbox"], MAPBOX_KEY)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(keys_file.stat().st_mode), 0o600)

        code, out = run("keys", "--data", str(self.data))
        self.assertEqual(json.loads(out)["keys"], {"mapbox": True, "google": False})
        self.assertNotIn(MAPBOX_KEY, out)

        code, out = run("forget-key", "mapbox", "--data", str(self.data))
        self.assertTrue(json.loads(out)["removed"])
        self.assertEqual(json.loads(keys_file.read_text()), {})

    def test_secret_mapbox_token_is_refused(self):
        code, out = run("set-key", "mapbox", "sk.eyJ1IjoidGVzdCIsImEiOiJzZWNyZXQifQ.abc", "--data", str(self.data))
        self.assertEqual(code, 1)
        self.assertIn("public token", json.loads(out)["refused"])
        self.assertFalse((self.data / "keys.json").exists())

    def test_malformed_keys_are_refused(self):
        for provider, key in (("mapbox", "hello"), ("google", "short key")):
            with self.subTest(provider=provider):
                code, _ = run("set-key", provider, key, "--data", str(self.data))
                self.assertEqual(code, 1)

    def test_key_written_by_hand_is_used(self):
        self.data.mkdir(parents=True)
        (self.data / "keys.json").write_text(json.dumps({"google": f"  {GOOGLE_KEY}\n"}))
        seen = {}

        def fake(url, body, headers):
            seen.update(headers)
            return {"places": []}

        with mock.patch.object(places, "http_json", side_effect=fake):
            code, _ = run("find-place", "Senso-ji", "--provider", "google", "--data", str(self.data))
        self.assertEqual(code, 0)
        self.assertEqual(seen["X-Goog-Api-Key"], GOOGLE_KEY)

    def test_missing_key(self):
        code, out = run("find-place", "Senso-ji", "--provider", "mapbox", "--data", str(self.data))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["issues"], [{"key": "missing", "provider": "mapbox"}])

    def test_refused_key(self):
        run("set-key", "mapbox", MAPBOX_KEY, "--data", str(self.data))
        with mock.patch.object(places, "http_json", side_effect=places.KeyRefusedError("HTTP 401")):
            code, out = run("find-place", "Senso-ji", "--provider", "mapbox", "--data", str(self.data))
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["issues"], [{"key": "refused", "provider": "mapbox"}])
        self.assertNotIn(MAPBOX_KEY, out)

    def test_too_many_queries(self):
        code, _ = run("find-place", *[f"q{i}" for i in range(11)], "--provider", "osm")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
