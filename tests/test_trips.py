"""Tests of the trips folder management (scripts/trips.py).

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import trips  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run(*args):
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        code = trips.main(list(args))
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
        with mock.patch.object(trips, "today", return_value="2027-01-10"):
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
        with mock.patch.object(trips, "today", return_value="2027-01-10"):
            _, created = run("new-trip", str(self.folder), "--title", "Islanda")
        trip_file = Path(created["trip_file"])

        with mock.patch.object(trips, "today", return_value="2027-01-12"):
            code, result = run("check", created["trip_folder"])
        self.assertEqual(code, 0, result)
        self.assertEqual(json.loads(trip_file.read_text(encoding="utf-8"))["trip"]["updated"], "2027-01-12")

        data = json.loads(trip_file.read_text(encoding="utf-8"))
        data["trip"]["status"] = "dreaming"
        trip_file.write_text(json.dumps(data), encoding="utf-8")
        with mock.patch.object(trips, "today", return_value="2027-01-15"):
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


class GuideTest(unittest.TestCase):
    def test_every_topic_named_in_the_instructions_exists(self):
        texts = [p.read_text(encoding="utf-8") for p in (ROOT / "skills" / "plan-trip").rglob("*.md")]
        named = {topic for text in texts for topic in re.findall(r"`guide ([a-z-]+)`", text)}
        self.assertTrue(named)
        self.assertLessEqual(named, set(trips.guide_topics()))

    def test_guide_prints_the_topic(self):
        out = io.StringIO()
        old = sys.stdout
        sys.stdout = out
        try:
            code = trips.main(["guide", "setup"])
        finally:
            sys.stdout = old
        self.assertEqual(code, 0)
        self.assertIn("Phase 0", out.getvalue())

    def test_unknown_topic(self):
        with self.assertRaises(trips.RefusedError):
            trips.cmd_guide("../SKILL")


class NamesTest(unittest.TestCase):
    def test_folder_name(self):
        self.assertEqual(trips.folder_name('Parigi: weekend / "lungo"'), "Parigi weekend lungo")
        self.assertEqual(trips.folder_name("Côte d'Azur 2027."), "Côte d'Azur 2027")
        with self.assertRaises(ValueError):
            trips.folder_name("  ?? ")
        with self.assertRaises(ValueError):
            trips.folder_name("CON")

    def test_slug(self):
        self.assertEqual(trips.slug("Côte d'Azur 2027"), "cote-d-azur-2027")
        self.assertEqual(trips.slug("東京"), "trip")


if __name__ == "__main__":
    unittest.main()
