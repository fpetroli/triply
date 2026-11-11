"""Tests of the documents for the user: itinerary, calendar, packing list.

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import documents  # noqa: E402
import triply  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load():
    return json.loads((FIXTURES / "valid_trip.json").read_text(encoding="utf-8"))


def labels(language="it"):
    return documents.load_labels(language, Path("/nowhere"))[0]


class LabelsTest(unittest.TestCase):
    def test_built_in_languages_are_complete(self):
        for code in documents.LABELS:
            with self.subTest(language=code):
                self.assertEqual(set(documents.LABELS[code]), set(documents.LABELS["en"]))
                self.assertEqual(len(documents.LABELS[code]["weekdays"]), 7)
                self.assertEqual(len(documents.LABELS[code]["months"]), 12)

    def test_other_language_uses_its_file(self):
        with tempfile.TemporaryDirectory() as folder:
            L, missing = documents.load_labels("de", Path(folder))
            self.assertEqual(L["file_itinerary"], "Itinerary")
            self.assertIn("file_itinerary", missing)
            (Path(folder) / "labels-de.json").write_text(json.dumps({"file_itinerary": "Reiseplan", "weekdays": "wrong type"}))
            L, missing = documents.load_labels("de-AT", Path(folder))
            self.assertEqual(L["file_itinerary"], "Reiseplan")
            self.assertNotIn("file_itinerary", missing)
            self.assertIn("weekdays", missing)

    def test_dates(self):
        self.assertEqual(documents.fmt_date("2027-04-05", labels()), "lun 5 apr 2027")
        self.assertEqual(documents.fmt_duration(150, labels()), "2 h 30")
        self.assertEqual(documents.fmt_duration(45, labels()), "45 min")


class ItineraryTest(unittest.TestCase):
    def test_html(self):
        data = load()
        data["days"][0]["items"][0]["notes"] = "<script>alert(1)</script>"
        data["places"]["boboli"]["name"] = "Boboli </script>"
        page = documents.render_html(data, labels())
        self.assertTrue(page.startswith("<!doctype html>\n<!-- triply:generated -->"))
        self.assertNotIn("<script>alert(1)", page)
        self.assertIn("&lt;script&gt;alert(1)", page)
        self.assertNotIn("Boboli </script>", page)  # also inside the map data
        self.assertIn("Bozza", page)  # the fixture is in the verification phase
        self.assertIn(documents.MAPLIBRE_JS_SRI, page)
        self.assertIn("Giorno 1 · gio 10 giu 2027", page)
        self.assertIn("↓ 10 min a piedi", page)

    def test_no_draft_after_the_verification(self):
        data = load()
        data["progress"]["phase"] = "bookings"
        self.assertNotIn("Bozza", documents.render_html(data, labels()))
        self.assertNotIn("Bozza", documents.render_markdown(data, labels()))

    def test_markdown(self):
        text = documents.render_markdown(load(), labels())
        self.assertTrue(text.startswith("<!-- triply:generated -->\n# "))
        self.assertIn("### Giorno 1 · gio 10 giu 2027", text)
        self.assertIn("[Ponte Vecchio](https://www.openstreetmap.org/?mlat=", text)
        self.assertIn("1. gio 10 giu 2027: Arrivo e centro storico — Firenze", text)


class CalendarTest(unittest.TestCase):
    def setUp(self):
        self.text = documents.render_calendar(load(), labels())

    def test_format(self):
        self.assertTrue(self.text.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"))
        self.assertTrue(self.text.endswith("END:VCALENDAR\r\n"))
        for line in self.text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75, line)

    def test_deadlines_with_two_reminders(self):
        self.assertIn("UID:", self.text)
        self.assertIn("SUMMARY:Book the stay in Siena", self.text)
        self.assertEqual(self.text.count("TRIGGER:-P6DT15H"), 2)  # two open deadlines
        self.assertEqual(self.text.count("TRIGGER:-PT15H"), 2)

    def test_stays_and_moves(self):
        self.assertIn("DTSTART;VALUE=DATE:20270610\r\nDTEND;VALUE=DATE:20270612\r\nSUMMARY:Alloggio: Firenze", self.text)
        self.assertIn("SUMMARY:Treno Milano Centrale → Firenze 08:10–10:05", self.text)

    def test_done_deadlines_are_left_out(self):
        data = load()
        for deadline in data["deadlines"]:
            deadline["done"] = True
        self.assertNotIn("VALARM", documents.render_calendar(data, labels()))

    def test_escaping(self):
        data = load()
        data["deadlines"][0]["title"] = "Pay; now, please"
        self.assertIn("SUMMARY:Pay\; now\\, please", documents.render_calendar(data, labels()))


class PackingTest(unittest.TestCase):
    def test_keys_are_unique(self):
        items = [{"item": "Calze"}, {"item": "Calze"}, {"item": "Calze", "traveller": "anna"}]
        self.assertEqual(documents.packing_keys(items), ["calze", "calze-2", "calze-anna"])

    def test_round_trip(self):
        data = load()
        text = documents.render_packing(data, labels())
        self.assertIn("- [ ] ID card <!-- triply:id-card:0 -->", text)
        edited = text.replace("- [ ] ID card", "- [x] ID card") + "- [x] Cuscino da viaggio\n- [ ] \n"
        self.assertEqual(documents.read_ticks(edited, data), 2)
        self.assertTrue(data["packing"][0]["packed"])
        self.assertEqual(data["packing"][-1], {"item": "Cuscino da viaggio", "category": "other", "packed": True})

    def test_tick_in_the_chat_is_not_undone_by_the_file(self):
        data = load()
        text = documents.render_packing(data, labels())  # ID card written unticked
        data["packing"][0]["packed"] = True  # then ticked in the chat
        self.assertEqual(documents.read_ticks(text, data), 0)
        self.assertTrue(data["packing"][0]["packed"])


class BuildTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.trip = Path(self._temp.name) / "Toscana"
        (self.trip / ".triply").mkdir(parents=True)
        data = load()
        data["trip"]["created"] = "2026-01-01"  # check sets the date of the last change to today
        (self.trip / ".triply" / "trip.json").write_text(json.dumps(data), encoding="utf-8")

    def tearDown(self):
        self._temp.cleanup()

    def check(self):
        out = io.StringIO()
        old, sys.stdout = sys.stdout, out
        try:
            triply.main(["check", str(self.trip)])
        finally:
            sys.stdout = old
        return json.loads(out.getvalue())

    def test_check_writes_the_documents(self):
        result = self.check()
        names = sorted(Path(p).name for p in result["documents"]["written"])
        self.assertEqual(names, ["Bagaglio.md", "Itinerario.html", "Itinerario.md", "Scadenze.ics"])

    def test_a_file_of_the_user_is_never_overwritten(self):
        mine = self.trip / "Itinerario.md"
        mine.write_text("my own notes", encoding="utf-8")
        result = self.check()
        self.assertEqual(result["documents"]["skipped"], [str(mine)])
        self.assertEqual(mine.read_text(encoding="utf-8"), "my own notes")

    def test_ticks_reach_the_trip_file(self):
        self.check()
        packing = self.trip / "Bagaglio.md"
        packing.write_text(packing.read_text(encoding="utf-8").replace("- [ ] ID card", "- [x] ID card"), encoding="utf-8")
        result = self.check()
        self.assertEqual(result["documents"]["ticks_read"], 1)
        self.assertEqual(result["documents"]["from_packing_file"], [{"item": "ID card", "change": "packed"}])
        self.assertEqual(result["documents"]["packing"]["packed"], 1)
        data = json.loads((self.trip / ".triply" / "trip.json").read_text(encoding="utf-8"))
        self.assertTrue(data["packing"][0]["packed"])
        self.assertIn("- [x] ID card <!-- triply:id-card:1 -->", packing.read_text(encoding="utf-8"))

    def test_no_documents_before_the_days(self):
        path = self.trip / ".triply" / "trip.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["days"] = []
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertNotIn("documents", self.check())


if __name__ == "__main__":
    unittest.main()
