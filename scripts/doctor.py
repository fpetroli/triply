"""Self-test of triply in the environment where it runs.

It answers three questions, so that a new environment (another computer, the
Claude desktop app, a sandbox in the cloud) can be checked in a few seconds:

- **folder**: can the script read and write the folder it works in (the trips
  folder)? It writes a small temporary file there, reads it back and removes it;
- **data**: is the plugin data folder writable, and does it keep what was saved
  in an earlier session? Each run leaves a mark (``doctor.json``) and reports
  the mark of the previous run;
- **network**: does each web service used by the script answer? One small
  request per service. Mapbox and Google are reached without a key (they must
  answer that a key is missing) or, when a key is saved, with that key (they
  must accept it).

Nothing else is changed, and the keys are never printed.
"""

from __future__ import annotations

import datetime
import json
import os
import platform
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from climate import ARCHIVE_URL, FORECAST_URL, GEOCODING_URL, USER_AGENT
from places import GOOGLE_URL as GOOGLE_SEARCH_URL, MAPBOX_URL as MAPBOX_SEARCH_URL, NOMINATIM_URL
from routes import GOOGLE_URL as GOOGLE_ROUTES_URL, OSRM_URL

MARK_FILE = "doctor.json"
TIMEOUT = 10.0

# A place known to every service: the Colosseum, Rome, and a point near it.
LAT, LON = 41.8902, 12.4922
NEAR = (41.8955, 12.4823)

# (status, body), or an exception when no HTTP answer came back.
Probe = Callable[[str, Optional[bytes], Dict[str, str]], Tuple[int, bytes]]


def http_probe(url: str, body: Optional[bytes], headers: Dict[str, str]) -> Tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.status, response.read(65536)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(65536)


def _json(body: bytes) -> Optional[Any]:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _snippet(body: bytes) -> str:
    text = body.decode("utf-8", "replace").strip().replace("\n", " ")
    return text[:160]


def _host(url: str) -> str:
    return urllib.parse.urlsplit(url).hostname or url


def _checks(keys: Dict[str, str], year: int) -> List[Dict[str, Any]]:
    """The requests to make: one per service, with what a good answer is."""
    q = urllib.parse.urlencode
    checks: List[Dict[str, Any]] = [
        {"service": "Open-Meteo geocoding", "used_for": "place, climate, forecast",
         "url": GEOCODING_URL + "?" + q({"name": "Rome", "count": 1})},
        {"service": "Open-Meteo historical weather", "used_for": "climate",
         "url": ARCHIVE_URL + "?" + q({"latitude": LAT, "longitude": LON, "start_date": f"{year - 1}-01-01",
                                        "end_date": f"{year - 1}-01-01", "daily": "temperature_2m_max"})},
        {"service": "Open-Meteo forecast", "used_for": "forecast",
         "url": FORECAST_URL + "?" + q({"latitude": LAT, "longitude": LON, "daily": "temperature_2m_max", "forecast_days": 1})},
        {"service": "OpenStreetMap Nominatim", "used_for": "find-place, check-place (osm)",
         "url": NOMINATIM_URL + "?" + q({"q": "Colosseum, Rome", "format": "jsonv2", "limit": 1})},
        {"service": "OpenStreetMap routing (FOSSGIS)", "used_for": "route (osm)",
         "url": OSRM_URL.format(server="foot", profile="walking", coordinates=f"{LON},{LAT};{NEAR[1]},{NEAR[0]}")},
        {"service": "Nager.Date", "used_for": "calendar",
         "url": f"https://nagerholidays.com/api/v4/Holidays/IT/{year}"},
    ]
    mapbox = keys.get("mapbox")
    checks.append({
        "service": "Mapbox", "used_for": "find-place, check-place, route (mapbox)", "key": bool(mapbox),
        "url": MAPBOX_SEARCH_URL + "?" + q({"q": "Colosseum", "limit": 1, **({"access_token": mapbox} if mapbox else {})}),
    })
    google = keys.get("google")
    google_headers = {"X-Goog-Api-Key": google} if google else {}
    checks.append({
        "service": "Google Places", "used_for": "find-place, check-place (google)", "key": bool(google),
        "url": GOOGLE_SEARCH_URL, "body": json.dumps({"textQuery": "Colosseum, Rome"}).encode("utf-8"),
        # Only the ids: the cheapest kind of request (no cost).
        "headers": {**google_headers, "Content-Type": "application/json", "X-Goog-FieldMask": "places.id"},
    })
    route_body = {
        "origin": {"location": {"latLng": {"latitude": LAT, "longitude": LON}}},
        "destination": {"location": {"latLng": {"latitude": NEAR[0], "longitude": NEAR[1]}}},
        "travelMode": "WALK",
    }
    checks.append({
        "service": "Google Routes", "used_for": "route (google)", "key": bool(google),
        "url": GOOGLE_ROUTES_URL, "body": json.dumps(route_body).encode("utf-8"),
        "headers": {**google_headers, "Content-Type": "application/json", "X-Goog-FieldMask": "routes.duration"},
    })
    return checks


def _judge(check: Dict[str, Any], status: int, body: bytes) -> Tuple[bool, str]:
    data = _json(body)
    if data is None:
        # Proxies and firewalls answer with a page of their own, not with the
        # JSON of the service.
        return False, f"HTTP {status}, not an answer of the service (blocked on the way?): {_snippet(body)}"
    if "key" not in check:
        if status == 200:
            return True, "answers"
        return False, f"HTTP {status}: {_snippet(body)}"
    if check["key"]:
        if status == 200:
            return True, "answers, and the saved key is accepted"
        if status in (401, 403):
            return False, f"answers, but the saved key is refused (HTTP {status}): {_snippet(body)}"
        return False, f"HTTP {status}: {_snippet(body)}"
    if status in (400, 401, 403):
        return True, "answers (no key saved, so the service asks for one)"
    return False, f"HTTP {status}: {_snippet(body)}"


def network(keys: Dict[str, str], year: int, probe: Probe) -> List[Dict[str, Any]]:
    results = []
    for check in _checks(keys, year):
        entry = {"service": check["service"], "host": _host(check["url"]), "used_for": check["used_for"]}
        try:
            status, body = probe(check["url"], check.get("body"), check.get("headers", {}))
            entry["ok"], entry["detail"] = _judge(check, status, body)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            entry["ok"], entry["detail"] = False, f"no answer: {exc}"
        results.append(entry)
    return results


def folder_check(folder: Path) -> Dict[str, Any]:
    result: Dict[str, Any] = {"path": str(folder), "exists": folder.is_dir()}
    if not result["exists"]:
        result.update(writable=False, detail="the folder does not exist or cannot be seen")
        return result
    try:
        result["entries"] = sum(1 for _ in folder.iterdir())
        fd, temp = tempfile.mkstemp(dir=str(folder), prefix=".triply-doctor-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write("triply")
            result["writable"] = Path(temp).read_text(encoding="utf-8") == "triply"
        finally:
            os.remove(temp)
        result["detail"] = "read and write work"
    except OSError as exc:
        result.update(writable=False, detail=f"cannot read or write: {exc}")
    return result


def data_check(data_dir: Optional[Path], now: datetime.datetime, saved_keys: Dict[str, str]) -> Dict[str, Any]:
    if data_dir is None:
        return {"path": None, "writable": False, "previous_run": None,
                "detail": "no plugin data folder given: keys and the trips folder cannot be remembered"}
    result: Dict[str, Any] = {"path": str(data_dir), "keys": {p: p in saved_keys for p in ("mapbox", "google")}}
    mark = data_dir / MARK_FILE
    previous = None
    try:
        previous = json.loads(mark.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = None
    result["previous_run"] = previous.get("last_run") if isinstance(previous, dict) else None
    runs = previous.get("runs", 0) if isinstance(previous, dict) and isinstance(previous.get("runs"), int) else 0
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        mark.write_text(json.dumps({"last_run": now.isoformat(timespec="seconds"), "runs": runs + 1}) + "\n", encoding="utf-8")
        result["writable"] = True
        result["detail"] = ("a mark of an earlier run is there: the folder keeps its data"
                            if result["previous_run"] else
                            "first run here: run the self-test again in a new session to see whether the data is kept")
    except OSError as exc:
        result.update(writable=False, detail=f"cannot write: {exc}")
    return result


def run(folder: Path, data_dir: Optional[Path], keys: Dict[str, str], now: Optional[datetime.datetime] = None,
        probe: Optional[Probe] = None) -> Dict[str, Any]:
    now = now or datetime.datetime.now().astimezone()
    probe = probe or http_probe
    report: Dict[str, Any] = {
        "python": platform.python_version(),
        "system": f"{platform.system()} {platform.release()}".strip(),
        "folder": folder_check(folder),
        "data": data_check(data_dir, now, keys),
        "network": network(keys, now.year, probe),
    }
    problems = []
    if sys.version_info < (3, 9):
        problems.append(f"Python {report['python']} is too old: triply needs 3.9 or later")
    if not report["folder"].get("writable"):
        problems.append(f"the folder {folder} cannot be read and written")
    if not report["data"].get("writable"):
        problems.append("the plugin data folder cannot be written: keys and the trips folder are not remembered")
    blocked = [entry for entry in report["network"] if not entry["ok"]]
    for entry in blocked:
        problems.append(f"{entry['service']} ({entry['host']}): {entry['detail']}")
    report["blocked_hosts"] = sorted({entry["host"] for entry in blocked})
    report["problems"] = problems
    report["ok"] = not problems
    return report
