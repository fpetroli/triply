#!/usr/bin/env python3
"""Manage the trips folder: find it, create it, create trips, check files.

Usage:
    python3 trips.py locate [--start DIR] [--data DIR]
    python3 trips.py init FOLDER [--data DIR]
    python3 trips.py new-trip TRIPS_FOLDER --title TITLE [--travellers ID,ID] [--currency CODE]
    python3 trips.py check PATH
    python3 trips.py guide TOPIC

Every command prints JSON on standard output.

locate
    Finds the trips folder and the current trip. It looks first in ``--start``
    (default: the current folder) and in the folders above it, then in the
    folder remembered in ``--data/config.json``. The trips folder is the one
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

check
    Checks a trip folder, a trips folder (its profile) or a JSON file. When a
    trip file has no errors, it sets ``trip.updated`` to today and rewrites the
    file in a stable format.

guide
    Prints the instructions of the planning skill on TOPIC (a file in
    ``skills/plan-trip/references``). Claude reads them this way because the
    plugin folder is often outside the folders it may read without asking.

Exit status: 0 done, 1 refused or errors found, 2 a file could not be read.
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

import validate  # noqa: E402

TRIPLY = ".triply"
TRIP_FILE = "trip.json"
PROFILE_FILE = "profile.json"
CONFIG_FILE = "config.json"
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
    parser = argparse.ArgumentParser(description="Manage the triply trips folder.")
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
        else:
            result = cmd_check(args.target)
            code = 0 if result["ok"] else 1
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
