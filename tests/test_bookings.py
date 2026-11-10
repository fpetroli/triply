"""Tests of the search links, the costs and the checks of the bookings phase.

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import datetime
import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import bookings  # noqa: E402
import triply  # noqa: E402
import validate  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAMILY = [{"age_group": "adult"}, {"age_group": "senior"}, {"age_group": "child"}, {"age_group": "infant"}]


def load():
    return json.loads((FIXTURES / "valid_trip.json").read_text(encoding="utf-8"))


def query(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))


def run(*args):
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        code = triply.main(list(args))
    finally:
        sys.stdout = old
    return code, json.loads(out.getvalue())


class LinksTest(unittest.TestCase):
    def test_travellers(self):
        self.assertEqual(bookings.travellers_count(FAMILY), (2, 1, 1))

    def test_stay(self):
        booking, airbnb = bookings.stay_links("San Gimignano", "2027-06-12", "2027-06-14", FAMILY, "it")
        q = query(booking["url"])
        self.assertTrue(booking["url"].startswith("https://www.booking.com/searchresults.html?"))
        self.assertEqual((q["ss"], q["checkin"], q["checkout"]), ("San Gimignano", "2027-06-12", "2027-06-14"))
        self.assertEqual((q["group_adults"], q["group_children"], q["lang"]), ("2", "2", "it"))
        self.assertTrue(airbnb["url"].startswith("https://www.airbnb.com/s/San%20Gimignano/homes?"))
        self.assertEqual(query(airbnb["url"])["infants"], "1")
        self.assertTrue(booking["generated"])

    def test_flight(self):
        origin, destination = {"name": "Bologna", "iata": "BLQ"}, {"name": "Tokyo", "iata": "TYO"}
        google, skyscanner = bookings.flight_links(origin, destination, "2027-04-03", FAMILY, "it")
        self.assertEqual(query(google["url"])["q"], "Flights to Tokyo from Bologna on 2027-04-03 oneway")
        self.assertTrue(skyscanner["url"].startswith("https://www.skyscanner.net/transport/flights/blq/tyo/270403/?"))
        self.assertEqual(query(skyscanner["url"])["adultsv2"], "2")

    def test_flight_without_codes(self):
        links = bookings.flight_links({"name": "Bologna"}, {"name": "Tokyo"}, "2027-04-03", FAMILY, "it")
        self.assertEqual([link["label"] for link in links], ["Google Flights"])

    def test_train(self):
        (link,) = bookings.ground_links({"name": "Reggio Calabria"}, {"name": "Messina"})
        self.assertEqual(link["url"], "https://www.rome2rio.com/map/Reggio-Calabria/Messina")

    def test_fill_keeps_official_links_and_skips_what_is_booked(self):
        data = load()
        siena = data["stays"][1]["booking"]
        siena["links"] = [{"label": "Old", "url": "https://old.example/", "generated": True},
                          {"label": "Hotel site", "url": "https://hotel.example/"}]
        done = bookings.fill_links(data)
        self.assertEqual([link["label"] for link in siena["links"]], ["Booking.com", "Airbnb", "Hotel site"])
        self.assertNotIn("links", data["stays"][0]["booking"])  # already booked
        self.assertIn({"stay": "stay-siena", "links": ["Booking.com", "Airbnb"]}, done)


class CostsTest(unittest.TestCase):
    def test_no_double_count(self):
        result = bookings.costs(load())
        # 240 booked for Florence (the budget line about it is not counted again), 25 estimated.
        self.assertEqual(result["totals"]["EUR"], {"booked": 240.0, "confirmed": 0.0, "estimated": 25.0})
        self.assertEqual(result["budget"]["left"], 560.0)

    def test_per_person_budget_and_other_currencies(self):
        data = load()
        data["constraints"]["budget"] = {"amount": 100, "currency": "EUR", "scope": "per_person"}
        data["transports"][1]["booking"] = {"status": "booked", "cost": {"amount": 30, "currency": "CHF"}}
        result = bookings.costs(data)
        self.assertEqual(result["budget"]["amount"], 100)
        self.assertEqual(result["budget"]["other_currencies"], ["CHF"])

    def test_booked_without_cost(self):
        data = load()
        data["transports"][1]["booking"] = {"status": "booked"}
        self.assertEqual(bookings.costs(data)["booked_without_cost"], ["train-out", "bus-siena"])


class ChecksTest(unittest.TestCase):
    def setUp(self):
        self.trip = load()
        self.today = datetime.date(2027, 3, 10)

    def text(self):
        return " ".join(f"{i['path']}: {i['message']}" for i in validate.check_trip(self.trip, today=self.today).issues)

    def test_overdue(self):
        self.today = datetime.date(2027, 5, 12)
        self.assertIn("/deadlines/0/due: overdue: Book the stay in Siena", self.text())

    def test_overdue_after_the_trip_is_fine(self):
        self.today = datetime.date(2027, 7, 1)
        self.assertNotIn("overdue", self.text())

    def test_already_booked(self):
        self.trip["stays"][1]["booking"]["status"] = "booked"
        self.assertIn("'stay-siena' is already booked: mark the deadline as done", self.text())

    def test_booked_stop_of_a_day(self):
        self.trip["days"][1]["items"][0]["booking"] = {"status": "booked"}
        self.assertIn("'uffizi' is already booked", self.text())

    def test_cancellation_after_the_start_is_fine(self):
        self.trip["deadlines"].append({"id": "cancel", "title": "Free cancellation", "due": "2027-06-11", "kind": "cancellation", "done": False})
        self.assertNotIn("/deadlines/2/due: falls after", self.text())

    def test_to_book_without_deadline_after_the_bookings(self):
        self.trip["progress"]["phase"] = "weather_packing"
        self.trip["transports"][1]["booking"]["status"] = "to_book"
        self.assertIn("'bus-siena' is still to book and has no booking deadline", self.text())
        self.assertNotIn("'stay-siena' is still to book", self.text())

    def test_over_budget(self):
        self.trip["constraints"]["budget"]["amount"] = 200
        self.assertIn("over budget: 240.0 EUR committed, 200 planned", self.text())


class CommandsTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.trip = Path(self._temp.name) / "Toscana"
        (self.trip / ".triply").mkdir(parents=True)
        shutil.copy(FIXTURES / "valid_trip.json", self.trip / ".triply" / "trip.json")

    def tearDown(self):
        self._temp.cleanup()

    def test_links_are_saved(self):
        code, out = run("links", str(self.trip))
        self.assertEqual(code, 0, out)
        data = json.loads((self.trip / ".triply" / "trip.json").read_text())
        self.assertEqual(data["stays"][1]["booking"]["links"][0]["label"], "Booking.com")
        self.assertEqual(data["transports"][1]["booking"].get("links"), None)  # not to book

    def test_links_refused_on_a_broken_file(self):
        path = self.trip / ".triply" / "trip.json"
        data = json.loads(path.read_text())
        data["stays"][1]["place"] = "nowhere"
        path.write_text(json.dumps(data))
        code, out = run("links", str(self.trip))
        self.assertEqual(code, 1)
        self.assertIn("errors", out["refused"])

    def test_costs(self):
        code, out = run("costs", str(self.trip))
        self.assertEqual(code, 0)
        self.assertEqual(out["budget"]["committed"], 240.0)


if __name__ == "__main__":
    unittest.main()
