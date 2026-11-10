"""Tests of the tools of the verification phase: routes, place checks, calendar.

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import calendar_days  # noqa: E402
import climate  # noqa: E402
import places  # noqa: E402
import routes  # noqa: E402
import triply  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
GOOGLE_KEY = "AIzaSyA-abcdefghijklmnopqrstuvwxyz12345"
MAPBOX_KEY = "pk.eyJ1IjoidGVzdCIsImEiOiJjbGV4YW1wbGUifQ.abcdefghij"


def run(*args):
    out = io.StringIO()
    old = sys.stdout
    sys.stdout = out
    try:
        code = triply.main(list(args))
    finally:
        sys.stdout = old
    return code, json.loads(out.getvalue())


def osrm(*legs):
    return {"code": "Ok", "routes": [{"legs": [{"duration": s, "distance": m} for s, m in legs]}]}


class RoutesTest(unittest.TestCase):
    def test_osm_walk(self):
        seen = []

        def fake(url, body, headers):
            seen.append(url)
            return osrm((1919.1, 2392.2), (7652.4, 9566.7))

        result = routes.route("osm", "walk", [(35.71, 139.79), (35.71, 139.77), (35.67, 139.70)], today="2026-11-08", request=fake)
        self.assertEqual(len(seen), 1)  # one request for the whole day
        self.assertIn("/routed-foot/route/v1/walking/139.79,35.71;139.77,35.71;139.7,35.67", seen[0])
        self.assertEqual(result["legs"][0], {"from": 0, "to": 1, "minutes": 32, "distance_km": 2.4})
        self.assertEqual(result["total_minutes"], 32 + 128)
        self.assertIn("OpenStreetMap", result["source"]["title"])

    def test_osm_has_no_public_transport(self):
        with self.assertRaises(routes.UnsupportedError):
            routes.route("osm", "public_transport", [(1, 1), (2, 2)], request=lambda u, b, h: {})

    def test_no_route(self):
        with self.assertRaises(routes.NoRouteError):
            routes.route("osm", "car", [(1, 1), (2, 2)], request=lambda u, b, h: {"code": "NoRoute"})

    def test_mapbox(self):
        def fake(url, body, headers):
            self.assertIn("/directions/v5/mapbox/cycling/", url)
            self.assertEqual(dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))["access_token"], MAPBOX_KEY)
            return osrm((600, 2500))

        result = routes.route("mapbox", "bike", [(1, 1), (2, 2)], MAPBOX_KEY, request=fake)
        self.assertEqual(result["legs"][0]["minutes"], 10)

    def test_google_transit_one_request_per_leg(self):
        bodies = []

        def fake(url, body, headers):
            self.assertEqual(headers["X-Goog-FieldMask"], "routes.duration,routes.distanceMeters")
            bodies.append(body)
            return {"routes": [{"duration": "1500s", "distanceMeters": 12000}]}

        result = routes.route("google", "public_transport", [(1, 1), (2, 2), (3, 3)], GOOGLE_KEY, "2027-04-12T09:30:00+09:00", request=fake)
        self.assertEqual(len(bodies), 2)
        self.assertEqual(bodies[0]["travelMode"], "TRANSIT")
        self.assertEqual(bodies[0]["departureTime"], "2027-04-12T09:30:00+09:00")
        self.assertEqual(bodies[1]["origin"]["location"]["latLng"], {"latitude": 2, "longitude": 2})
        self.assertEqual(result["legs"][1], {"from": 1, "to": 2, "minutes": 25, "distance_km": 12.0})

    def test_google_walk_has_no_departure_time(self):
        def fake(url, body, headers):
            self.assertNotIn("departureTime", body)
            return {"routes": [{"duration": "300s", "distanceMeters": 400}]}

        routes.route("google", "walk", [(1, 1), (2, 2)], GOOGLE_KEY, "2027-04-12T09:30:00+09:00", request=fake)

    def test_points(self):
        with self.assertRaises(ValueError):
            routes.route("osm", "walk", [(1, 1)])
        with self.assertRaises(ValueError):
            routes.parse_point("35.7")


class CheckPlaceTest(unittest.TestCase):
    def test_osm_lookup(self):
        def fake(url, body, headers):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
            self.assertEqual(query["osm_ids"], "W7836744,N123")
            return [{"osm_type": "way", "osm_id": 7836744, "name": "Hama-rikyu", "lat": "35.66", "lon": "139.76",
                     "extratags": {"opening_hours": "Mo-Su 09:00-17:00; Dec 29-Jan 01 off", "website": "https://www.tokyo-park.or.jp/"}}]

        result = places.check("osm", ["way/7836744", "node/123"], request=fake)
        first, second = result["places"]
        self.assertTrue(first["found"])
        self.assertEqual(first["opening_hours"], "Mo-Su 09:00-17:00; Dec 29-Jan 01 off")
        self.assertEqual(first["website"], "https://www.tokyo-park.or.jp/")
        self.assertEqual(second, {"provider_id": "node/123", "found": False})

    def test_bad_osm_id(self):
        with self.assertRaises(ValueError):
            places.check("osm", ["123"], request=lambda u, b, h: [])

    def test_google_details_ask_the_hours(self):
        def fake(url, body, headers):
            self.assertIn("regularOpeningHours", headers["X-Goog-FieldMask"])
            if url.startswith(places.GOOGLE_DETAILS_URL.format(id="gone")):
                raise places.NotFoundError("HTTP 404")
            return {"id": "ChIJ1", "displayName": {"text": "Uffizi"}, "businessStatus": "OPERATIONAL",
                    "regularOpeningHours": {"weekdayDescriptions": ["Monday: Closed", "Tuesday: 8:15 AM – 6:30 PM"]},
                    "websiteUri": "https://www.uffizi.it/", "location": {"latitude": 43.7678, "longitude": 11.2553}}

        result = places.check("google", ["ChIJ1", "gone"], key=GOOGLE_KEY, request=fake)
        first, second = result["places"]
        self.assertEqual(first["status"], "open")
        self.assertEqual(first["opening_hours"], "Monday: Closed; Tuesday: 8:15 AM – 6:30 PM")
        self.assertEqual(second, {"provider_id": "gone", "found": False})

    def test_google_closed_permanently(self):
        fake = lambda u, b, h: {"id": "x", "businessStatus": "CLOSED_PERMANENTLY"}  # noqa: E731
        self.assertEqual(places.check("google", ["x"], key=GOOGLE_KEY, request=fake)["places"][0]["status"], "closed_permanently")

    def test_mapbox_retrieve(self):
        def fake(url, body, headers):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
            self.assertIn("session_token", query)
            return {"features": [{"properties": {"name": "Teatro Massimo", "operational_status": "active",
                                                 "coordinates": {"latitude": 38.12, "longitude": 13.357},
                                                 "metadata": {"open_hours": {"periods": [{"open": {"day": 1, "time": "0930"}, "close": {"day": 1, "time": "1800"}}]}}}}]}

        place = places.check("mapbox", ["dXJu"], key=MAPBOX_KEY, request=fake)["places"][0]
        self.assertEqual(place["status"], "open")
        self.assertEqual(place["opening_periods"][0]["open"]["time"], "0930")

    def test_service_error_is_not_a_missing_place(self):
        def fake(url, body, headers):
            if "bad" in url:
                raise climate.ServiceError("HTTP 500")
            return {"id": "ok"}

        result = places.check("google", ["bad", "ok"], key=GOOGLE_KEY, request=fake)
        self.assertIn("error", result["places"][0])
        self.assertNotIn("found", result["places"][0])


class CalendarTest(unittest.TestCase):
    def test_weekdays_and_holidays(self):
        def fake(url, body, headers):
            self.assertEqual(url, "https://nagerholidays.com/api/v4/Holidays/JP/2027")
            return [
                {"date": "2027-04-29", "name": "Shōwa Day", "nationalHoliday": True, "holidayTypes": ["Public"]},
                {"date": "2027-04-30", "name": "Bank day", "nationalHoliday": True, "holidayTypes": ["Bank"]},
            ]

        result = calendar_days.calendar("jp", "2027-04-28", "2027-04-30", request=fake)
        self.assertEqual([d["weekday"] for d in result["days"]], ["Wednesday", "Thursday", "Friday"])
        self.assertEqual(result["days"][1]["holidays"], [{"name": "Shōwa Day", "national": True}])
        self.assertNotIn("holidays", result["days"][2])  # only public holidays
        self.assertEqual(result["source"]["provider"], "nager-date")

    def test_without_country(self):
        result = calendar_days.calendar(None, "2027-12-31", "2028-01-01", request=lambda u, b, h: self.fail("no request"))
        self.assertEqual(result["days"][1], {"date": "2028-01-01", "weekday": "Saturday"})

    def test_limits(self):
        with self.assertRaises(ValueError):
            calendar_days.calendar(None, "2027-05-02", "2027-05-01")
        with self.assertRaises(ValueError):
            calendar_days.calendar(None, "2027-01-01", "2027-12-31")


class CommandsTest(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.trip = Path(self._temp.name) / "Toscana"
        (self.trip / ".triply").mkdir(parents=True)
        shutil.copy(FIXTURES / "valid_trip.json", self.trip / ".triply" / "trip.json")
        self.data = Path(self._temp.name) / "data"

    def tearDown(self):
        self._temp.cleanup()

    def test_route_with_places_of_the_trip(self):
        with mock.patch.object(places, "http_json", side_effect=lambda u, b, h: osrm((600, 800))) as fake, \
                mock.patch.object(routes, "http_json", fake):
            code, out = run("route", "ponte-vecchio", "boboli", "--provider", "osm", "--mode", "walk", "--trip", str(self.trip))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["legs"][0]["from"], "ponte-vecchio")
        self.assertEqual(out["legs"][0]["to"], "boboli")

    def test_route_unknown_point(self):
        code, out = run("route", "nowhere", "boboli", "--provider", "osm", "--mode", "walk", "--trip", str(self.trip))
        self.assertEqual(code, 1)
        self.assertIn("nowhere", out["refused"])

    def test_route_public_transport_needs_google(self):
        code, out = run("route", "1,1", "2,2", "--provider", "osm", "--mode", "public_transport")
        self.assertEqual(code, 1)
        self.assertEqual(out["issues"], [{"mode": "unsupported", "provider": "osm"}])

    def test_route_bad_departure(self):
        code, out = run("route", "1,1", "2,2", "--provider", "osm", "--mode", "car", "--depart", "tomorrow")
        self.assertEqual(code, 1)
        self.assertIn("--depart", out["refused"])

    def test_route_needs_the_key(self):
        code, out = run("route", "1,1", "2,2", "--provider", "google", "--mode", "walk", "--data", str(self.data))
        self.assertEqual(code, 1)
        self.assertEqual(out["issues"], [{"key": "missing", "provider": "google"}])

    def test_check_place_with_places_of_the_trip(self):
        trip_file = self.trip / ".triply" / "trip.json"
        data = json.loads(trip_file.read_text())
        data["places"]["uffizi"]["provider_ids"] = {"osm": "way/42"}
        trip_file.write_text(json.dumps(data))

        def fake(url, body, headers):
            return [{"osm_type": "way", "osm_id": 42, "name": "Uffizi", "lat": "43.76", "lon": "11.25"}]

        with mock.patch.object(places, "http_json", side_effect=fake):
            code, out = run("check-place", "uffizi", "boboli", "--provider", "osm", "--trip", str(self.trip))
        self.assertEqual(code, 0, out)
        self.assertEqual(out["places"][0]["place"], "uffizi")
        self.assertEqual(out["without_id"], ["boboli"])

    def test_calendar(self):
        code, out = run("calendar", "--from", "2027-06-10", "--to", "2027-06-12")
        self.assertEqual(code, 0)
        self.assertEqual(out["days"][0]["weekday"], "Thursday")


if __name__ == "__main__":
    unittest.main()
