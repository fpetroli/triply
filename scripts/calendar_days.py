"""The days of a period with their weekday and the public holidays of a country.

Standard library only. Holidays come from Nager.Date
(https://nagerholidays.com/Api), an open-source dataset with no account: a
convenience, not an official source. Regional holidays are listed with their
regions. Weekdays are computed here, so that they are never guessed.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from climate import ServiceError
from places import Request, http_json

HOLIDAYS_URL = "https://nagerholidays.com/api/v4/Holidays/{country}/{year}"
MAX_DAYS = 120
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def calendar(
    country: Optional[str],
    start: str,
    end: str,
    today: str = "",
    request: Request = None,
) -> Dict[str, Any]:
    first, last = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
    if last < first:
        raise ValueError("--to is earlier than --from")
    if (last - first).days + 1 > MAX_DAYS:
        raise ValueError(f"give at most {MAX_DAYS} days")
    holidays: Dict[str, List[Dict[str, Any]]] = {}
    result: Dict[str, Any] = {}
    if country:
        request = request or http_json
        for year in range(first.year, last.year + 1):
            url = HOLIDAYS_URL.format(country=country.upper(), year=year)
            try:
                items = request(url, None, {}) or []
            except ServiceError as exc:
                raise ServiceError(f"public holidays not available for {country.upper()} {year}: {exc}") from exc
            for item in items:
                if "Public" not in (item.get("holidayTypes") or []):
                    continue
                entry: Dict[str, Any] = {"name": item.get("name"), "national": bool(item.get("nationalHoliday"))}
                if item.get("subdivisionCodes"):
                    entry["regions"] = item["subdivisionCodes"]
                holidays.setdefault(item.get("date"), []).append(entry)
        result["country"] = country.upper()
        result["source"] = {
            "provider": "nager-date",
            "url": "https://nagerholidays.com/",
            "title": "Nager.Date public holidays",
            "checked_at": today,
        }
    days = []
    day = first
    while day <= last:
        entry = {"date": day.isoformat(), "weekday": WEEKDAYS[day.weekday()]}
        if holidays.get(day.isoformat()):
            entry["holidays"] = holidays[day.isoformat()]
        days.append(entry)
        day += datetime.timedelta(days=1)
    result["days"] = days
    return result
