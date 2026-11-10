#!/usr/bin/env python3
"""triply's single entry point: everything the planning skill does on files and services.

One script, so that the user approves it once.

Usage:
    python3 triply.py locate [--start DIR] [--data DIR]
    python3 triply.py init FOLDER [--data DIR]
    python3 triply.py new-trip TRIPS_FOLDER --title TITLE [--travellers ID,ID] [--currency CODE]
    python3 triply.py rename-trip TRIP_FOLDER --title TITLE
    python3 triply.py check PATH
    python3 triply.py place NAME [--country CODE] [--language CODE]
    python3 triply.py climate (--place NAME [--country CODE] | --lat LAT --lon LON) --from MM-DD --to MM-DD [--years N]
    python3 triply.py find-place QUERY [QUERY ...] --provider osm|mapbox|google [--near LAT,LON] [--country CODE] [--language CODE] [--limit N] [--data DIR]
    python3 triply.py check-place ID [ID ...] --provider osm|mapbox|google [--trip FOLDER] [--language CODE] [--data DIR]
    python3 triply.py route POINT POINT [POINT ...] --provider osm|mapbox|google --mode walk|bike|car|public_transport [--depart TIME] [--trip FOLDER] [--data DIR]
    python3 triply.py calendar --from DATE --to DATE [--country CODE]
    python3 triply.py links TRIP_FOLDER
    python3 triply.py costs TRIP_FOLDER
    python3 triply.py keys --data DIR
    python3 triply.py set-key mapbox|google KEY --data DIR
    python3 triply.py forget-key mapbox|google --data DIR
    python3 triply.py guide TOPIC

Every command prints JSON on standard output.

locate
    Finds the trips folder and the current trip. It looks first in ``--start``
    (default: the current folder) and in the folders above it, then in the
    folders right inside ``--start`` (where triply proposes to create it), then
    in the folder remembered in ``--data/config.json``. The trips folder is the one
    whose ``.triply`` folder holds the user profile (or no trip file); a trip
    folder is one whose ``.triply`` folder holds ``trip.json``.

init
    Creates the trips folder and its ``.triply`` folder, and remembers it in
    ``--data/config.json``. Existing files are never touched.

new-trip
    Creates ``TRIPS_FOLDER/<title>/.triply/trip.json`` with the minimum content
    of a new trip, taking language, map service, currency and travellers from
    the profile (``--travellers`` picks some of them; default: all). It refuses
    to overwrite an existing folder.

rename-trip
    Renames a trip folder after a new title, with everything inside it, and
    updates the title in the trip file. The id of the trip does not change.

check
    Checks a trip folder, a trips folder (its profile) or a JSON file. When a
    trip file has no errors, it sets ``trip.updated`` to today and rewrites the
    file in a stable format.

place
    Looks a place up by name (Open-Meteo geocoding): name, region, country,
    coordinates of the best matches.

climate
    The typical weather of a period of the year at a place, averaged over the
    last years (Open-Meteo historical weather), with its source.

find-place
    Looks points of interest up by name (a temple, a museum, a beach) with a
    map service: OpenStreetMap (no account), Mapbox or Google (with the key
    saved by ``set-key``). Up to ten queries per call. For each one, the best
    matches with address, coordinates, category and the id at the provider.

check-place
    Looks places up again by their id at the map service: whether they are
    still there, whether they are open for business (Google, Mapbox), their
    opening hours and website. With ``--trip``, the ids are those of the places
    of the trip, and the id at the provider is taken from the trip file.

route
    Travel time and distance between consecutive points, on foot, by bike, by
    car or (Google only) by public transport. A point is LAT,LON or, with
    ``--trip``, the id of a place of the trip. ``--depart`` (RFC 3339, for
    example 2027-04-12T09:30:00+09:00) is used by Google for public transport
    and car.

calendar
    The days of a period with their weekday and, with ``--country``, the public
    holidays of that country (Nager.Date).

links
    Adds to every stay and transport still to book the search links already
    filled in (Booking.com and Airbnb; Google Flights and Skyscanner; Rome2rio),
    and saves the trip file. Links added by hand, such as official sites, are
    kept. triply never queries these sites.

costs
    Totals of the costs entered by the user, per currency: booked, other
    confirmed, estimated; and what is left of the budget.

keys, set-key, forget-key
    The keys of Mapbox and Google live in ``--data/keys.json``, readable only
    by the user, outside the trips folder: they never end up in a trip that is
    shared. ``keys`` says which keys are saved and where the file is (the user
    can also write it by hand); ``set-key`` saves a key after a check of its
    form; ``forget-key`` removes it. A key is never printed.

guide
    Prints the instructions of the planning skill on TOPIC (a file in
    ``skills/plan-trip/references``). Claude reads them this way because the
    plugin folder is often outside the folders it may read without asking.

Exit status: 0 done, 1 refused, errors found or service unavailable, 2 a file
could not be read.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bookings  # noqa: E402
import calendar_days  # noqa: E402
import climate  # noqa: E402
import places  # noqa: E402
import routes  # noqa: E402
import validate  # noqa: E402

TRIPLY = ".triply"
TRIP_FILE = "trip.json"
PROFILE_FILE = "profile.json"
CONFIG_FILE = "config.json"
KEYS_FILE = "keys.json"
KEY_PROVIDERS = ("mapbox", "google")
MAX_QUERIES = 10
GUIDES = Path(__file__).resolve().parent.parent / "skills" / "plan-trip" / "references"

# Characters that are not allowed in folder names on Windows, macOS or Linux.
_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


def today() -> str:
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- helpers


def read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    """Write ``data`` to ``path`` atomically, in a stable, readable format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp, path)
    except BaseException:
        if os.path.exists(temp):
            os.remove(temp)
        raise


def folder_name(title: str) -> str:
    """Turn a trip title into a folder name that works on every system."""
    name = _FORBIDDEN.sub(" ", title)
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    if not name or name.lower() in _RESERVED:
        raise ValueError(f"the title {title!r} cannot be used as a folder name")
    return name


def slug(text: str) -> str:
    """Turn a text into an id: lower-case letters, digits and hyphens."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    result = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return result or "trip"


def is_trip_folder(folder: Path) -> bool:
    return (folder / TRIPLY / TRIP_FILE).is_file()


def is_trips_folder(folder: Path) -> bool:
    return (folder / TRIPLY).is_dir() and not is_trip_folder(folder)


def _find_up(start: Path, test) -> Optional[Path]:
    for folder in [start, *start.parents]:
        if test(folder):
            return folder
    return None


def _trips_folders_inside(folder: Path) -> List[Path]:
    """Trips folders (with a user profile) right inside ``folder``."""
    try:
        children = sorted(p for p in folder.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError:
        return []
    return [p for p in children if (p / TRIPLY / PROFILE_FILE).is_file()]


def remembered(data_dir: Optional[Path]) -> Optional[Path]:
    if data_dir is None:
        return None
    try:
        value = read_json(data_dir / CONFIG_FILE).get("trips_folder")
    except (OSError, ValueError, AttributeError):
        return None
    return Path(value) if value else None


def remember(data_dir: Optional[Path], trips_folder: Path) -> None:
    if data_dir is None:
        return
    path = data_dir / CONFIG_FILE
    try:
        config = read_json(path)
        if not isinstance(config, dict):
            config = {}
    except (OSError, ValueError):
        config = {}
    config["trips_folder"] = str(trips_folder)
    write_json(path, config)


def list_trips(trips_folder: Path) -> List[Dict[str, Any]]:
    trips = []
    for folder in sorted(p for p in trips_folder.iterdir() if p.is_dir() and is_trip_folder(p)):
        entry: Dict[str, Any] = {"folder": str(folder)}
        try:
            data = read_json(folder / TRIPLY / TRIP_FILE)
            entry.update(
                title=data["trip"]["title"],
                status=data["trip"]["status"],
                phase=data["progress"]["phase"],
                next_step=data["progress"]["next_step"],
                updated=data["trip"]["updated"],
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            entry["error"] = f"cannot read the trip file: {exc}"
        trips.append(entry)
    return trips


# ---------------------------------------------------------------- commands


def cmd_locate(start: Path, data_dir: Optional[Path]) -> Dict[str, Any]:
    start = start.resolve()
    current_trip = _find_up(start, is_trip_folder)
    trips_folder = _find_up(start, is_trips_folder)
    found_by = "folder" if trips_folder else None
    if trips_folder is None:
        inside = _trips_folders_inside(start)
        if len(inside) == 1:
            trips_folder, found_by = inside[0], "folder"
    if trips_folder is None:
        candidate = remembered(data_dir)
        if candidate is not None and is_trips_folder(candidate):
            trips_folder, found_by = candidate, "remembered"
    result: Dict[str, Any] = {
        "trips_folder": str(trips_folder) if trips_folder else None,
        "found_by": found_by,
        "profile": bool(trips_folder and (trips_folder / TRIPLY / PROFILE_FILE).is_file()),
        "current_trip": str(current_trip) if current_trip else None,
        "trips": list_trips(trips_folder) if trips_folder else [],
    }
    if trips_folder is not None and found_by == "folder":
        remember(data_dir, trips_folder)
    return result


def cmd_init(folder: Path, data_dir: Optional[Path]) -> Dict[str, Any]:
    folder = folder.expanduser().resolve()
    if is_trip_folder(folder):
        raise RefusedError(f"{folder} is a trip folder, not a trips folder")
    (folder / TRIPLY).mkdir(parents=True, exist_ok=True)
    remember(data_dir, folder)
    return {
        "trips_folder": str(folder),
        "profile": (folder / TRIPLY / PROFILE_FILE).is_file(),
    }


def cmd_new_trip(
    trips_folder: Path, title: str, currency: Optional[str], traveller_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    trips_folder = trips_folder.expanduser().resolve()
    profile_path = trips_folder / TRIPLY / PROFILE_FILE
    if not profile_path.is_file():
        raise RefusedError(f"no user profile in {trips_folder}: complete the first setup before creating a trip")
    profile = read_json(profile_path)
    currency = currency or profile.get("currency")
    if not currency:
        raise RefusedError("no currency: give --currency or add it to the user profile")
    known = {t.get("id"): t for t in profile.get("travellers", [])}
    if traveller_ids:
        unknown = [i for i in traveller_ids if i not in known]
        if unknown:
            raise RefusedError(f"travellers not in the user profile: {', '.join(unknown)}")
        travellers = [known[i] for i in traveller_ids]
    else:
        travellers = list(known.values())
    if not travellers:
        raise RefusedError("no travellers: add at least one traveller to the user profile")

    folder = trips_folder / folder_name(title)
    if folder.exists():
        raise RefusedError(f"the folder {folder} already exists: choose another title")

    date = today()
    data = {
        "schema_version": 1,
        "trip": {
            "id": slug(title),
            "title": title.strip(),
            "status": "idea",
            "language": profile.get("language"),
            "map_provider": profile.get("map_provider"),
            "currency": currency,
            "created": date,
            "updated": date,
        },
        "progress": {"phase": "brief", "next_step": "", "open_points": [], "log": []},
        "travellers": travellers,
        "constraints": {"dates": {}},
        "places": {},
        "days": [],
    }
    report = validate.check_trip(data)
    if not report.ok:
        raise RefusedError("the new trip file would not be valid", report.issues)
    write_json(folder / TRIPLY / TRIP_FILE, data)
    return {"trip_folder": str(folder), "trip_file": str(folder / TRIPLY / TRIP_FILE)}


def cmd_rename_trip(trip_folder: Path, title: str) -> Dict[str, Any]:
    trip_folder = trip_folder.expanduser().resolve()
    if not is_trip_folder(trip_folder):
        raise RefusedError(f"{trip_folder} is not a trip folder")
    target = trip_folder.parent / folder_name(title)
    trip_file = trip_folder / TRIPLY / TRIP_FILE
    data = read_json(trip_file)
    if target != trip_folder:
        if target.exists():
            raise RefusedError(f"the folder {target} already exists: choose another title")
        trip_folder.rename(target)
    data["trip"]["title"] = title.strip()
    data["trip"]["updated"] = today()
    write_json(target / TRIPLY / TRIP_FILE, data)
    return {"trip_folder": str(target), "trip_file": str(target / TRIPLY / TRIP_FILE)}


def cmd_place(name: str, country: Optional[str], language: str) -> Dict[str, Any]:
    places = climate.find_places(name, country, language)
    if not places:
        raise RefusedError(f"no place found for {name!r}: try a nearby town or another spelling")
    return {"places": places}


def cmd_climate(
    place: Optional[str],
    country: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    start: str,
    end: str,
    years: int,
) -> Dict[str, Any]:
    found = None
    if lat is None or lon is None:
        if not place:
            raise RefusedError("give --place, or both --lat and --lon")
        found = cmd_place(place, country, "en")["places"][0]
        lat, lon = found["lat"], found["lon"]
    result = climate.climate(lat, lon, start, end, years)
    if found:
        result["place"] = found
    return result


def cmd_check(target: Path) -> Dict[str, Any]:
    path = validate.resolve(target)
    data = read_json(path)
    kind = "profile" if path.name.endswith(PROFILE_FILE) else "trip"
    report = validate.check_profile(data) if kind == "profile" else validate.check_trip(data)
    if kind == "trip" and report.ok:
        data["trip"]["updated"] = today()
        write_json(path, data)
    return {
        "file": str(path),
        "kind": kind,
        "ok": report.ok,
        "errors": report.count(validate.ERROR),
        "warnings": report.count(validate.WARNING),
        "issues": report.issues,
    }


def _need_data(data_dir: Optional[Path]) -> Path:
    if data_dir is None:
        raise RefusedError("give --data, the folder where the plugin keeps its own data")
    return data_dir


def load_keys(data_dir: Path) -> Dict[str, str]:
    try:
        keys = read_json(data_dir / KEYS_FILE)
    except FileNotFoundError:
        return {}
    except ValueError as exc:
        raise RefusedError(f"the keys file {data_dir / KEYS_FILE} is not valid JSON: {exc}") from exc
    if not isinstance(keys, dict):
        raise RefusedError(f"the keys file {data_dir / KEYS_FILE} must be an object, for example {{\"mapbox\": \"pk....\"}}")
    return {k: v.strip() for k, v in keys.items() if k in KEY_PROVIDERS and isinstance(v, str) and v.strip()}


def check_key(provider: str, key: str) -> None:
    if provider == "mapbox":
        if key.startswith("sk."):
            raise RefusedError("this is a secret Mapbox token: use a public token (it starts with 'pk.')")
        if not re.fullmatch(r"pk\.[A-Za-z0-9_.\-]{20,}", key):
            raise RefusedError("this does not look like a Mapbox public token (it starts with 'pk.')")
    elif not re.fullmatch(r"[A-Za-z0-9_\-]{30,}", key):
        raise RefusedError("this does not look like a Google API key (usually 39 characters, starting with 'AIza')")


def cmd_keys(data_dir: Optional[Path]) -> Dict[str, Any]:
    data_dir = _need_data(data_dir)
    keys = load_keys(data_dir)
    return {"file": str(data_dir / KEYS_FILE), "keys": {p: p in keys for p in KEY_PROVIDERS}}


def cmd_set_key(provider: str, key: str, data_dir: Optional[Path]) -> Dict[str, Any]:
    data_dir = _need_data(data_dir)
    key = key.strip()
    check_key(provider, key)
    keys = load_keys(data_dir)
    keys[provider] = key
    write_json(data_dir / KEYS_FILE, keys)  # created readable only by the user
    os.chmod(data_dir / KEYS_FILE, 0o600)
    return {"saved": provider, "file": str(data_dir / KEYS_FILE)}


def cmd_forget_key(provider: str, data_dir: Optional[Path]) -> Dict[str, Any]:
    data_dir = _need_data(data_dir)
    keys = load_keys(data_dir)
    removed = keys.pop(provider, None) is not None
    if removed:
        write_json(data_dir / KEYS_FILE, keys)
    return {"removed": removed, "provider": provider}


def _key_for(provider: str, data_dir: Optional[Path]) -> Optional[str]:
    if provider not in KEY_PROVIDERS:
        return None
    key = load_keys(_need_data(data_dir)).get(provider)
    if not key:
        raise RefusedError(f"no {provider} key saved: ask the user for it, or use osm", [{"key": "missing", "provider": provider}])
    return key


def _with_key(provider: str, call):
    try:
        return call()
    except places.KeyRefusedError as exc:
        raise RefusedError(f"{provider}: {exc}", [{"key": "refused", "provider": provider}]) from exc


def _trip_places(trip_folder: Optional[Path]) -> Optional[Dict[str, Any]]:
    if trip_folder is None:
        return None
    return read_json(validate.resolve(trip_folder.expanduser())).get("places", {})


def cmd_find_place(
    queries: List[str],
    provider: str,
    near: Optional[str],
    country: Optional[str],
    language: str,
    limit: int,
    data_dir: Optional[Path],
) -> Dict[str, Any]:
    if not 1 <= len(queries) <= MAX_QUERIES:
        raise RefusedError(f"give from 1 to {MAX_QUERIES} queries per call")
    key = _key_for(provider, data_dir)
    near_point = places.parse_near(near)
    return _with_key(provider, lambda: places.find(provider, queries, near_point, country, language, max(1, min(limit, 10)), key, today()))


def cmd_check_place(
    ids: List[str], provider: str, trip_folder: Optional[Path], language: str, data_dir: Optional[Path]
) -> Dict[str, Any]:
    trip_places = _trip_places(trip_folder)
    lookup: List[str] = []
    place_of: Dict[str, str] = {}
    without_id: List[str] = []
    for given in ids:
        if trip_places is None:
            lookup.append(given)
            continue
        if given not in trip_places:
            raise RefusedError(f"no place '{given}' in the trip")
        provider_id = (trip_places[given].get("provider_ids") or {}).get(provider)
        if provider_id:
            lookup.append(provider_id)
            place_of[provider_id] = given
        else:
            without_id.append(given)
    result: Dict[str, Any] = {"provider": provider, "places": []}
    if lookup:
        key = _key_for(provider, data_dir)
        result = _with_key(provider, lambda: places.check(provider, lookup, language, key, today()))
        for entry in result["places"]:
            if entry["provider_id"] in place_of:
                entry["place"] = place_of[entry["provider_id"]]
    if without_id:
        result["without_id"] = without_id
    return result


def cmd_route(
    points: List[str],
    provider: str,
    mode: str,
    depart: Optional[str],
    trip_folder: Optional[Path],
    data_dir: Optional[Path],
) -> Dict[str, Any]:
    trip_places = _trip_places(trip_folder)
    coordinates = []
    for point in points:
        if trip_places is not None and point in trip_places:
            coordinates.append((trip_places[point]["lat"], trip_places[point]["lon"]))
        elif "," in point:
            coordinates.append(routes.parse_point(point))
        else:
            raise RefusedError(f"'{point}' is neither LAT,LON nor a place of the trip" + ("" if trip_places is not None else " (give --trip)"))
    if depart:
        try:
            datetime.datetime.fromisoformat(depart.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RefusedError(f"--depart must be a date and time with its offset, for example 2027-04-12T09:30:00+09:00: {depart!r}") from exc
    key = _key_for(provider, data_dir)
    try:
        result = _with_key(provider, lambda: routes.route(provider, mode, coordinates, key, depart, today()))
    except routes.UnsupportedError as exc:
        raise RefusedError(str(exc), [{"mode": "unsupported", "provider": provider}]) from exc
    except routes.NoRouteError as exc:
        raise RefusedError(str(exc), [{"route": "none"}]) from exc
    for leg in result["legs"]:
        leg["from"], leg["to"] = points[leg["from"]], points[leg["to"]]
    return result


def _trip_file(trip_folder: Path) -> Path:
    path = validate.resolve(trip_folder.expanduser())
    if path.name != TRIP_FILE:
        raise RefusedError(f"{trip_folder} is not a trip folder")
    return path


def cmd_links(trip_folder: Path) -> Dict[str, Any]:
    path = _trip_file(trip_folder)
    data = read_json(path)
    if not validate.check_trip(data).ok:
        raise RefusedError("the trip file has errors: run check and fix them first")
    done = bookings.fill_links(data)
    data["trip"]["updated"] = today()
    write_json(path, data)
    return {"trip_file": str(path), "done": done}


def cmd_costs(trip_folder: Path) -> Dict[str, Any]:
    data = read_json(_trip_file(trip_folder))
    if not validate.check_trip(data).ok:
        raise RefusedError("the trip file has errors: run check and fix them first")
    return bookings.costs(data)


def cmd_calendar(start: str, end: str, country: Optional[str]) -> Dict[str, Any]:
    return calendar_days.calendar(country, start, end, today())


def guide_topics() -> List[str]:
    return sorted(p.stem for p in GUIDES.glob("*.md"))


def cmd_guide(topic: str) -> str:
    if topic not in guide_topics():
        raise RefusedError(f"unknown topic {topic!r}; topics: {', '.join(guide_topics())}")
    return (GUIDES / f"{topic}.md").read_text(encoding="utf-8")


class RefusedError(Exception):
    def __init__(self, message: str, issues: Optional[List[Dict[str, str]]] = None) -> None:
        super().__init__(message)
        self.issues = issues or []


# ---------------------------------------------------------------- command line


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="triply: trips folder, trip files, places, routes, calendar, climate, bookings and map service keys.")
    commands = parser.add_subparsers(dest="command", required=True)

    locate = commands.add_parser("locate", help="find the trips folder and the current trip")
    locate.add_argument("--start", type=Path, default=Path.cwd(), help="folder to start from (default: current)")
    locate.add_argument("--data", type=Path, help="folder where the plugin keeps its own data")

    init = commands.add_parser("init", help="create the trips folder")
    init.add_argument("folder", type=Path)
    init.add_argument("--data", type=Path, help="folder where the plugin keeps its own data")

    new_trip = commands.add_parser("new-trip", help="create a trip folder and its trip file")
    new_trip.add_argument("trips_folder", type=Path)
    new_trip.add_argument("--title", required=True, help="title of the trip, also the name of its folder")
    new_trip.add_argument("--travellers", help="comma-separated ids of travellers from the profile (default: all)")
    new_trip.add_argument("--currency", help="currency code, if the profile has none")

    check = commands.add_parser("check", help="check a trip file or the user profile")
    check.add_argument("target", type=Path, help="trip folder, trips folder or JSON file")

    rename = commands.add_parser("rename-trip", help="rename a trip folder after a new title")
    rename.add_argument("trip_folder", type=Path)
    rename.add_argument("--title", required=True)

    place = commands.add_parser("place", help="look a place up by name")
    place.add_argument("name")
    place.add_argument("--country", help="two-letter country code, to narrow the search")
    place.add_argument("--language", default="en", help="language of the names (default: en)")

    weather = commands.add_parser("climate", help="typical weather of a period of the year at a place")
    weather.add_argument("--place", help="name of the place (the best match is used)")
    weather.add_argument("--country", help="two-letter country code, with --place")
    weather.add_argument("--lat", type=float)
    weather.add_argument("--lon", type=float)
    weather.add_argument("--from", dest="start", required=True, help="first day, MM-DD")
    weather.add_argument("--to", dest="end", required=True, help="last day, MM-DD")
    weather.add_argument("--years", type=int, default=5, help="years to average (default: 5)")

    find = commands.add_parser("find-place", help="look points of interest up by name with a map service")
    find.add_argument("queries", nargs="+", help="what to look for, for example 'Senso-ji, Tokyo'")
    find.add_argument("--provider", choices=places.PROVIDERS, required=True)
    find.add_argument("--near", help="LAT,LON to prefer results near this point")
    find.add_argument("--country", help="two-letter country code, to narrow the search")
    find.add_argument("--language", default="en", help="language of the names (default: en)")
    find.add_argument("--limit", type=int, default=3, help="matches per query (default: 3)")
    find.add_argument("--data", type=Path, help="folder where the plugin keeps its own data")

    check_place = commands.add_parser("check-place", help="look places up again by their id at the map service")
    check_place.add_argument("ids", nargs="+", help="ids at the provider, or ids of places of the trip with --trip")
    check_place.add_argument("--provider", choices=places.PROVIDERS, required=True)
    check_place.add_argument("--trip", type=Path, help="trip folder: the ids are those of its places")
    check_place.add_argument("--language", default="en", help="language of the names and hours (default: en)")
    check_place.add_argument("--data", type=Path, help="folder where the plugin keeps its own data")

    route = commands.add_parser("route", help="travel times between consecutive points")
    route.add_argument("points", nargs="+", help="LAT,LON, or ids of places of the trip with --trip")
    route.add_argument("--provider", choices=routes.PROVIDERS, required=True)
    route.add_argument("--mode", choices=routes.MODES, required=True)
    route.add_argument("--depart", help="departure, RFC 3339 with offset (Google: public transport and car)")
    route.add_argument("--trip", type=Path, help="trip folder, to give points as ids of its places")
    route.add_argument("--data", type=Path, help="folder where the plugin keeps its own data")

    days = commands.add_parser("calendar", help="weekdays and public holidays of a period")
    days.add_argument("--from", dest="start", required=True, help="first day, YYYY-MM-DD")
    days.add_argument("--to", dest="end", required=True, help="last day, YYYY-MM-DD")
    days.add_argument("--country", help="two-letter country code, for its public holidays")

    links = commands.add_parser("links", help="add the search links to what is still to book")
    links.add_argument("trip_folder", type=Path)
    costs = commands.add_parser("costs", help="totals of the costs and what is left of the budget")
    costs.add_argument("trip_folder", type=Path)

    keys = commands.add_parser("keys", help="which map service keys are saved, and where")
    keys.add_argument("--data", type=Path, required=True)
    set_key = commands.add_parser("set-key", help="save the key of a map service")
    set_key.add_argument("provider", choices=KEY_PROVIDERS)
    set_key.add_argument("key")
    set_key.add_argument("--data", type=Path, required=True)
    forget_key = commands.add_parser("forget-key", help="remove the key of a map service")
    forget_key.add_argument("provider", choices=KEY_PROVIDERS)
    forget_key.add_argument("--data", type=Path, required=True)

    guide = commands.add_parser("guide", help="print the instructions of the planning skill on a topic")
    guide.add_argument("topic")

    args = parser.parse_args(argv)
    if args.command == "guide":
        try:
            sys.stdout.write(cmd_guide(args.topic))
            return 0
        except RefusedError as exc:
            sys.stderr.write(f"{exc}\n")
            return 1
    try:
        if args.command == "locate":
            result = cmd_locate(args.start, args.data)
            code = 0
        elif args.command == "init":
            result = cmd_init(args.folder, args.data)
            code = 0
        elif args.command == "new-trip":
            ids = [i.strip() for i in args.travellers.split(",") if i.strip()] if args.travellers else None
            result = cmd_new_trip(args.trips_folder, args.title, args.currency, ids)
            code = 0
        elif args.command == "rename-trip":
            result = cmd_rename_trip(args.trip_folder, args.title)
            code = 0
        elif args.command == "place":
            result = cmd_place(args.name, args.country, args.language)
            code = 0
        elif args.command == "find-place":
            result = cmd_find_place(args.queries, args.provider, args.near, args.country, args.language, args.limit, args.data)
            code = 0
        elif args.command == "check-place":
            result = cmd_check_place(args.ids, args.provider, args.trip, args.language, args.data)
            code = 0
        elif args.command == "route":
            result = cmd_route(args.points, args.provider, args.mode, args.depart, args.trip, args.data)
            code = 0
        elif args.command == "calendar":
            result = cmd_calendar(args.start, args.end, args.country)
            code = 0
        elif args.command == "links":
            result = cmd_links(args.trip_folder)
            code = 0
        elif args.command == "costs":
            result = cmd_costs(args.trip_folder)
            code = 0
        elif args.command == "keys":
            result = cmd_keys(args.data)
            code = 0
        elif args.command == "set-key":
            result = cmd_set_key(args.provider, args.key, args.data)
            code = 0
        elif args.command == "forget-key":
            result = cmd_forget_key(args.provider, args.data)
            code = 0
        elif args.command == "climate":
            result = cmd_climate(args.place, args.country, args.lat, args.lon, args.start, args.end, args.years)
            code = 0
        else:
            result = cmd_check(args.target)
            code = 0 if result["ok"] else 1
    except climate.ServiceError as exc:
        result, code = {"unavailable": str(exc)}, 1
    except RefusedError as exc:
        result, code = {"refused": str(exc), "issues": exc.issues}, 1
    except ValueError as exc:
        # json.JSONDecodeError is a ValueError, and so are invalid titles.
        result, code = {"refused": str(exc)}, 2 if isinstance(exc, json.JSONDecodeError) else 1
    except OSError as exc:
        result, code = {"refused": f"cannot read or write: {exc}"}, 2
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
