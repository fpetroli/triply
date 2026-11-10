"""Tests of the forecast and of the checks of weather and packing.

Run from the repository root with:
    python3 -m unittest discover -s tests
"""

from __future__ import annotations

import datetime
import json
import sys
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import climate  # noqa: E402
import validate  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TODAY = datetime.date(2027, 6, 1)


def answer(days):
    return {"daily": {
        "time": [d for d, *_ in days],
        "temperature_2m_max": [r[1] for r in days],
        "temperature_2m_min": [r[2] for r in days],
        "precipitation_sum": [r[3] for r in days],
        "precipitation_probability_max": [r[4] for r in days],
        "weather_code": [r[5] for r in days],
    }}


class ForecastTest(unittest.TestCase):
    def test_days(self):
        seen = []

        def fake(url):
            seen.append(dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)))
            return answer([("2027-06-10", 29.1, 16.2, 0.0, 10, 1), ("2027-06-11", 25.0, 15.0, 8.4, 80, 63)])

        result = climate.forecast(43.77, 11.25, "2027-06-10", "2027-06-11", today=TODAY, fetch=fake)
        self.assertEqual(seen[0]["start_date"], "2027-06-10")
        self.assertEqual(result["days"][1], {"date": "2027-06-11", "temp_max_c": 25.0, "temp_min_c": 15.0,
                                             "precipitation_mm": 8.4, "rain_probability_pct": 80, "weather": "rain"})
        self.assertEqual(result["source"]["checked_at"], "2027-06-01")
        self.assertNotIn("available_until", result)

    def test_too_far(self):
        with self.assertRaises(ValueError) as caught:
            climate.forecast(1, 1, "2027-06-20", "2027-06-25", today=TODAY, fetch=lambda u: self.fail("no request"))
        self.assertIn("available from 2027-06-05", str(caught.exception))

    def test_cut_at_the_horizon(self):
        seen = []

        def fake(url):
            seen.append(dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)))
            return answer([])

        result = climate.forecast(1, 1, "2027-06-14", "2027-06-20", today=TODAY, fetch=fake)
        self.assertEqual(seen[0]["end_date"], "2027-06-16")
        self.assertEqual(result["available_until"], "2027-06-16")

    def test_weather_text(self):
        self.assertEqual(climate.weather_text(95), "thunderstorm")
        self.assertIsNone(climate.weather_text(None))


class ChecksTest(unittest.TestCase):
    def setUp(self):
        self.trip = json.loads((FIXTURES / "valid_trip.json").read_text(encoding="utf-8"))
        self.today = datetime.date(2027, 3, 10)

    def text(self):
        report = validate.check_trip(self.trip, today=self.today)
        return " ".join(f"{i['level']} {i['path']}: {i['message']}" for i in report.issues)

    def forecast(self, checked_at):
        return {"place": "florence", "start": "2027-06-10", "end": "2027-06-12", "kind": "forecast",
                "rain_probability_pct": 40, "source": {"provider": "open-meteo", "checked_at": checked_at}}

    def test_forecast_available(self):
        self.today = datetime.date(2027, 5, 30)
        self.assertIn("the forecast is available now", self.text())

    def test_not_yet(self):
        self.assertNotIn("forecast", self.text())

    def test_old_forecast(self):
        self.today = datetime.date(2027, 6, 5)
        self.trip["weather"].append(self.forecast("2027-06-01"))
        self.assertIn("more than two days old", self.text())

    def test_fresh_forecast(self):
        self.today = datetime.date(2027, 6, 5)
        self.trip["weather"].append(self.forecast("2027-06-04"))
        self.assertNotIn("forecast", self.text())

    def test_forecast_too_far_from_the_day_asked(self):
        self.trip["weather"].append(self.forecast("2027-05-20"))
        self.assertIn("error /weather/1/end: a forecast reaches at most 15 days", self.text())

    def test_after_the_trip_nothing_to_update(self):
        self.today = datetime.date(2027, 7, 1)
        self.assertNotIn("forecast", self.text())

    def test_packing_for_one_traveller(self):
        self.trip["packing"].append({"item": "Medicines", "category": "health", "traveller": "anna", "packed": False})
        self.assertTrue(validate.check_trip(self.trip, today=self.today).ok)
        self.trip["packing"][-1]["traveller"] = "nobody"
        self.assertIn("unknown traveller 'nobody'", self.text())


if __name__ == "__main__":
    unittest.main()
