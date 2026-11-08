"""Tests of the trip file and user profile checks.

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import copy
import datetime
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import schema_check  # noqa: E402
import validate  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str):
    with open(FIXTURES / name, encoding="utf-8") as handle:
        return json.load(handle)


def messages(report, level=None):
    return [
        f"{issue['path']}: {issue['message']}"
        for issue in report.issues
        if level is None or issue["level"] == level
    ]


class SchemaFilesTest(unittest.TestCase):
    def test_schemas_use_only_supported_keywords(self):
        for name in ("trip", "profile"):
            with self.subTest(schema=name):
                self.assertEqual(schema_check.unsupported_keywords(validate.load_schema(name)), [])

    def test_shared_definitions_are_identical(self):
        trip = validate.load_schema("trip")["$defs"]
        profile = validate.load_schema("profile")["$defs"]
        for name, definition in profile.items():
            with self.subTest(definition=name):
                self.assertEqual(definition, trip[name])

    def test_unsupported_keyword_is_refused(self):
        with self.assertRaises(schema_check.SchemaError):
            schema_check.check({}, {"type": "object", "oneOf": []})


class SchemaCheckTest(unittest.TestCase):
    def test_types_and_constraints(self):
        schema = {
            "type": "object",
            "required": ["a"],
            "additionalProperties": False,
            "properties": {
                "a": {"type": "integer", "minimum": 1},
                "b": {"type": "string", "pattern": "^x"},
                "c": {"type": "string", "format": "date"},
                "d": {"type": "array", "minItems": 1, "items": {"enum": ["p", "q"]}},
            },
        }
        self.assertEqual(schema_check.check({"a": 1, "b": "xy", "c": "2027-02-28", "d": ["p"]}, schema), [])
        problems = dict(schema_check.check({"a": 0, "b": "y", "c": "2027-02-30", "d": ["z"], "e": 1}, schema))
        self.assertIn("/a", problems)
        self.assertIn("/b", problems)
        self.assertIn("/c", problems)
        self.assertIn("/d/0", problems)
        self.assertIn("/e", problems)

    def test_booleans_are_not_numbers(self):
        self.assertTrue(schema_check.check(True, {"type": "integer"}))
        self.assertTrue(schema_check.check(False, {"type": "number"}))

    def test_missing_required_field(self):
        problems = schema_check.check({}, {"type": "object", "required": ["x"]})
        self.assertEqual(problems, [("/", "missing required field 'x'")])


class TripTest(unittest.TestCase):
    def setUp(self):
        self.trip = load("valid_trip.json")

    today = datetime.date(2027, 3, 10)

    def check(self):
        return validate.check_trip(self.trip, today=self.today)

    def assertIssue(self, level, path, fragment):
        report = self.check()
        found = [
            issue
            for issue in report.issues
            if issue["level"] == level and issue["path"] == path and fragment in issue["message"]
        ]
        self.assertTrue(found, f"expected {level} at {path} containing '{fragment}', got {messages(report)}")

    def test_valid_trip(self):
        report = self.check()
        self.assertTrue(report.ok, messages(report))
        self.assertEqual(report.issues, [])

    def test_schema_errors_stop_the_coherence_rules(self):
        self.trip["days"][0]["base"] = "nowhere"
        self.trip["trip"]["status"] = "unknown-status"
        report = self.check()
        self.assertEqual(messages(report), ["/trip/status: must be one of: idea, planning, booked, completed, cancelled; found 'unknown-status'"])

    def test_unknown_field(self):
        self.trip["trip"]["colour"] = "blue"
        self.assertIssue("error", "/trip/colour", "unknown field")

    def test_bad_place_id(self):
        self.trip["places"]["Bad Id"] = copy.deepcopy(self.trip["places"]["siena"])
        self.assertIssue("error", "/places/Bad Id", "invalid key")

    def test_duplicate_id(self):
        self.trip["stays"].append(copy.deepcopy(self.trip["stays"][0]))
        self.assertIssue("error", "/stays/2/id", "duplicate id")

    def test_unknown_references(self):
        self.trip["days"][0]["items"][0]["place"] = "nowhere"
        self.trip["days"][1]["base"] = "no-stay"
        self.trip["entry_requirements"][0]["traveller"] = "bob"
        self.trip["deadlines"][0]["related"] = "ghost"
        self.assertIssue("error", "/days/0/items/0/place", "unknown place")
        self.assertIssue("error", "/days/1/base", "unknown stay")
        self.assertIssue("error", "/entry_requirements/0/traveller", "unknown traveller")
        self.assertIssue("error", "/deadlines/0/related", "unknown id")

    def test_day_outside_trip(self):
        self.trip["days"][2]["date"] = "2027-06-20"
        self.assertIssue("error", "/days/2/date", "outside the trip dates")

    def test_days_out_of_order_and_duplicated(self):
        self.trip["days"][1]["date"] = "2027-06-10"
        self.assertIssue("error", "/days/1/date", "appears twice")
        self.trip["days"][1]["date"] = "2027-06-12"
        self.trip["days"][2]["date"] = "2027-06-11"
        self.assertIssue("error", "/days/2/date", "chronological order")

    def test_fixed_dates_need_both_ends(self):
        del self.trip["constraints"]["dates"]["end"]
        self.assertIssue("error", "/constraints/dates", "both 'start' and 'end'")

    def test_window_too_short(self):
        self.trip["constraints"]["dates"] = {"window_start": "2027-06-01", "window_end": "2027-06-05", "length_days": 7}
        self.assertIssue("error", "/constraints/dates/length_days", "longer than the window")
        self.assertIssue("warning", "/constraints/dates", "flexible window")

    def test_no_dates_after_brief(self):
        self.trip["constraints"]["dates"] = {}
        self.trip["days"] = []
        self.assertIssue("warning", "/constraints/dates", "no dates yet")

    def test_no_dates_during_brief_is_fine(self):
        self.trip["constraints"]["dates"] = {}
        self.trip["days"] = []
        self.trip["progress"]["phase"] = "brief"
        report = self.check()
        self.assertFalse([m for m in messages(report) if "/constraints/dates" in m], messages(report))

    def test_stay_dates(self):
        self.trip["stays"][1]["check_out"] = "2027-06-12"
        self.assertIssue("error", "/stays/1/check_out", "must be after 'check_in'")

    def test_overlapping_stays(self):
        self.trip["stays"][1]["check_in"] = "2027-06-11"
        self.assertIssue("warning", "/stays/1", "overlaps")

    def test_base_does_not_cover_the_night(self):
        self.trip["days"][2]["base"] = "stay-florence"
        self.assertIssue("warning", "/days/2/base", "does not cover the night")

    def test_more_than_one_main_activity(self):
        self.trip["days"][0]["items"][1]["role"] = "main"
        self.assertIssue("warning", "/days/0/items", "more than one main activity")

    def test_stops_out_of_time_order(self):
        self.trip["days"][0]["items"][1]["start"] = "14:00"
        self.assertIssue("warning", "/days/0/items/1/start", "earlier than the previous stop")

    def test_failed_verification(self):
        self.trip["places"]["uffizi"]["verification"]["status"] = "failed"
        self.assertIssue("warning", "/days/1/items/0/place", "failed its verification")

    def test_two_chosen_destinations(self):
        self.trip["options"][1]["chosen"] = True
        self.assertIssue("error", "/options", "more than one chosen destination")

    def test_transport_to_same_place(self):
        self.trip["transports"][0]["to"] = "milan-central"
        self.assertIssue("error", "/transports/0/to", "same place")

    def test_document_expires_during_trip(self):
        self.trip["travellers"][0]["documents"][0]["expires"] = "2027-06-11"
        self.assertIssue("warning", "/travellers/0/documents/0/expires", "expires before the end of the trip")

    def test_deadline_after_departure(self):
        self.trip["deadlines"][0]["due"] = "2027-06-11"
        self.assertIssue("warning", "/deadlines/0/due", "after the start of the trip")

    def test_requirement_without_source(self):
        del self.trip["entry_requirements"][0]["source"]
        self.assertIssue("error", "/entry_requirements/0/source", "needs its source")

    def test_unknown_requirement_without_source(self):
        req = self.trip["entry_requirements"][0]
        del req["source"]
        req["status"] = "unknown"
        req["check_url"] = "https://www.viaggiaresicuri.it/"
        self.assertIssue("warning", "/entry_requirements/0/status", "not verified yet")
        self.assertEqual(messages(self.check(), "error"), [])

    def test_requirement_to_do(self):
        self.trip["entry_requirements"][0]["status"] = "action_needed"
        self.assertIssue("warning", "/entry_requirements/0/status", "still to do")

    def test_requirement_checked_long_ago(self):
        self.today = datetime.date(2027, 6, 5)
        self.assertIssue("warning", "/entry_requirements/0/source/checked_at", "more than three months ago")

    def test_old_check_of_a_past_trip_is_fine(self):
        self.today = datetime.date(2028, 1, 1)
        self.assertNotIn("checked_at", " ".join(messages(self.check())))

    def add_stay(self, stay_id, check_in, check_out):
        self.trip["stays"].append(
            {"id": stay_id, "place": "siena", "check_in": check_in, "check_out": check_out, "booking": {"status": "to_book"}}
        )

    def test_gap_between_stays(self):
        self.trip["constraints"]["dates"]["end"] = "2027-06-16"
        self.add_stay("stay-later", "2027-06-14", "2027-06-16")
        self.assertIssue("warning", "/stays/2/check_in", "no stay for the nights from 2027-06-13 to 2027-06-14")

    def test_gap_covered_by_a_move(self):
        self.trip["constraints"]["dates"]["end"] = "2027-06-16"
        self.add_stay("stay-later", "2027-06-14", "2027-06-16")
        self.trip["transports"].append(
            {"id": "night-ferry", "mode": "ferry", "from": "siena", "to": "florence", "date": "2027-06-13", "booking": {"status": "to_book"}}
        )
        self.assertNotIn("no stay for the nights", " ".join(messages(self.check())))

    def test_single_night_in_the_middle(self):
        self.trip["constraints"]["dates"]["end"] = "2027-06-16"
        self.add_stay("stay-later", "2027-06-13", "2027-06-16")
        self.assertIssue("warning", "/stays/1", "only one night in the middle")

    def test_single_night_at_the_end_is_fine(self):
        self.assertNotIn("only one night", " ".join(messages(self.check())))

    def test_duration_without_source(self):
        del self.trip["transports"][1]["duration_estimated"]
        self.assertIssue("warning", "/transports/1/duration_min", "has no source")

    def test_duration_with_source(self):
        move = self.trip["transports"][1]
        del move["duration_estimated"]
        move["duration_source"] = {"provider": "osm", "checked_at": "2027-03-10"}
        self.assertNotIn("has no source", " ".join(messages(self.check())))

    def test_updated_before_created(self):
        self.trip["trip"]["updated"] = "2027-02-01"
        self.assertIssue("error", "/trip/updated", "earlier than the creation date")


class ProfileTest(unittest.TestCase):
    def test_valid_profile(self):
        report = validate.check_profile(load("valid_profile.json"))
        self.assertEqual(report.issues, [])

    def test_duplicate_traveller(self):
        profile = load("valid_profile.json")
        profile["travellers"].append(copy.deepcopy(profile["travellers"][0]))
        report = validate.check_profile(profile)
        self.assertIn("/travellers/1/id: duplicate id 'anna'", messages(report))

    def test_document_number_is_not_allowed(self):
        profile = load("valid_profile.json")
        profile["travellers"][0]["documents"][0]["number"] = "YA1234567"
        report = validate.check_profile(profile)
        self.assertIn("/travellers/0/documents/0/number: unknown field", messages(report))


class CommandLineTest(unittest.TestCase):
    def run_main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, err
        try:
            code = validate.main(list(args))
        finally:
            sys.stdout, sys.stderr = old_out, old_err
        return code, out.getvalue(), err.getvalue()

    def test_trip_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / ".triply").mkdir()
            (Path(folder) / ".triply" / "trip.json").write_text(
                (FIXTURES / "valid_trip.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
            code, out, _ = self.run_main(folder, "--json")
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["ok"])

    def test_trips_folder_with_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / ".triply").mkdir()
            (Path(folder) / ".triply" / "profile.json").write_text(
                (FIXTURES / "valid_profile.json").read_text(encoding="utf-8"), encoding="utf-8"
            )
            code, out, _ = self.run_main(folder)
        self.assertEqual(code, 0)
        self.assertIn("0 error(s)", out)

    def test_errors_give_exit_status_1(self):
        trip = load("valid_trip.json")
        trip["days"][0]["base"] = "no-stay"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trip.json"
            path.write_text(json.dumps(trip), encoding="utf-8")
            code, out, _ = self.run_main(str(path))
        self.assertEqual(code, 1)
        self.assertIn("unknown stay", out)

    def test_kind_option(self):
        code, _, _ = self.run_main(str(FIXTURES / "valid_profile.json"), "--kind", "profile")
        self.assertEqual(code, 0)
        code, _, _ = self.run_main(str(FIXTURES / "valid_profile.json"), "--kind", "trip")
        self.assertEqual(code, 1)

    def test_unreadable_file_gives_exit_status_2(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "trip.json"
            path.write_text("{ not json", encoding="utf-8")
            code, _, err = self.run_main(str(path))
            self.assertEqual(code, 2)
            self.assertIn("cannot read", err)
            code, _, _ = self.run_main(folder)
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
