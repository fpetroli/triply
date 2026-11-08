"""Places and climate from Open-Meteo, standard library only.

- ``find_places`` looks a place up by name with the Open-Meteo geocoding API.
- ``climate`` averages the weather of the last years over a period of the
  year (for example 1 to 31 August) with the Open-Meteo historical weather
  API: mean daily maximum and minimum temperature, mean precipitation and
  mean number of rainy days in the period.

Open-Meteo needs no account and is free for non-commercial use
(https://open-meteo.com/en/terms). Every result carries its source.
"""

from __future__ import annotations

import datetime
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
USER_AGENT = "triply (https://github.com/fpetroli/triply)"

# A day with at least this much precipitation counts as a rainy day.
RAINY_DAY_MM = 1.0
# The historical archive is complete up to a few days ago.
ARCHIVE_DELAY_DAYS = 7

Fetch = Optional[Callable[[str], Any]]


class ServiceError(Exception):
    """Open-Meteo could not be reached or gave an unusable answer."""


def fetch_json(url: str, timeout: float = 20.0) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ServiceError(f"Open-Meteo is not reachable: {exc}") from exc


def _url(base: str, params: Dict[str, Any]) -> str:
    return base + "?" + urllib.parse.urlencode(params)


# ---------------------------------------------------------------- places


def find_places(
    name: str,
    country: Optional[str] = None,
    language: str = "en",
    count: int = 5,
    fetch: Fetch = None,
) -> List[Dict[str, Any]]:
    fetch = fetch or fetch_json
    params: Dict[str, Any] = {"name": name, "count": count, "language": language, "format": "json"}
    if country:
        params["countryCode"] = country.upper()
    data = fetch(_url(GEOCODING_URL, params))
    places = []
    for item in (data or {}).get("results", []) or []:
        places.append(
            {
                "name": item.get("name"),
                "region": item.get("admin1"),
                "country": item.get("country_code"),
                "country_name": item.get("country"),
                "lat": item.get("latitude"),
                "lon": item.get("longitude"),
                "population": item.get("population"),
            }
        )
    return places


# ---------------------------------------------------------------- climate


def parse_month_day(text: str) -> Tuple[int, int]:
    try:
        month, day = (int(part) for part in text.split("-"))
        datetime.date(2000, month, day)  # 2000 is a leap year: 02-29 is accepted
    except ValueError as exc:
        raise ValueError(f"not a month and day in the form MM-DD: {text!r}") from exc
    return month, day


def _date_in(year: int, month: int, day: int) -> datetime.date:
    if month == 2 and day == 29:
        try:
            return datetime.date(year, 2, 29)
        except ValueError:
            return datetime.date(year, 2, 28)
    return datetime.date(year, month, day)


def periods(
    start: Tuple[int, int], end: Tuple[int, int], years: int, today: datetime.date
) -> List[Tuple[datetime.date, datetime.date]]:
    """The same period of the year in the last ``years`` years that are complete in the archive.

    A period whose end comes before its start in the calendar (for example
    12-20 to 01-10) runs across the new year.
    """
    crosses = end < start
    last_complete = today - datetime.timedelta(days=ARCHIVE_DELAY_DAYS)
    result: List[Tuple[datetime.date, datetime.date]] = []
    year = today.year
    while len(result) < years and year > today.year - years - 3:
        first = _date_in(year, *start)
        last = _date_in(year + 1 if crosses else year, *end)
        if last <= last_complete:
            result.append((first, last))
        year -= 1
    return sorted(result)


def _mean(values: List[float]) -> Optional[float]:
    return round(sum(values) / len(values), 1) if values else None


def climate(
    lat: float,
    lon: float,
    start: str,
    end: str,
    years: int = 5,
    today: Optional[datetime.date] = None,
    fetch: Fetch = None,
) -> Dict[str, Any]:
    fetch = fetch or fetch_json
    today = today or datetime.date.today()
    spans = periods(parse_month_day(start), parse_month_day(end), years, today)
    if not spans:
        raise ValueError("no complete period in the archive")
    url = _url(
        ARCHIVE_URL,
        {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "start_date": spans[0][0].isoformat(),
            "end_date": spans[-1][1].isoformat(),
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "timezone": "auto",
        },
    )
    data = fetch(url)
    try:
        daily = data["daily"]
        rows = list(zip(daily["time"], daily["temperature_2m_max"], daily["temperature_2m_min"], daily["precipitation_sum"]))
    except (KeyError, TypeError) as exc:
        raise ServiceError(f"unexpected answer from Open-Meteo: {exc}") from exc

    by_day = {datetime.date.fromisoformat(day): (tmax, tmin, rain) for day, tmax, tmin, rain in rows}
    maxima: List[float] = []
    minima: List[float] = []
    totals: List[float] = []
    rainy: List[float] = []
    used = []
    for first, last in spans:
        days = [first + datetime.timedelta(days=n) for n in range((last - first).days + 1)]
        values = [by_day.get(day) for day in days]
        rains = [v[2] for v in values if v and v[2] is not None]
        if len(rains) < len(days) * 0.9:
            continue  # too many missing days in this year
        maxima.extend(v[0] for v in values if v and v[0] is not None)
        minima.extend(v[1] for v in values if v and v[1] is not None)
        totals.append(sum(rains))
        rainy.append(sum(1 for r in rains if r >= RAINY_DAY_MM))
        used.append(first.year)
    if not used:
        raise ServiceError("Open-Meteo returned no usable data for this place and period")

    return {
        "lat": round(lat, 4),
        "lon": round(lon, 4),
        "period": {"from": start, "to": end},
        "years": used,
        "temp_max_c": _mean(maxima),
        "temp_min_c": _mean(minima),
        "precipitation_mm": _mean(totals),
        "rain_days": _mean(rainy),
        "source": {
            "provider": "open-meteo",
            "url": url,
            "title": f"Open-Meteo historical weather, average of {len(used)} years",
            "checked_at": today.isoformat(),
        },
    }
