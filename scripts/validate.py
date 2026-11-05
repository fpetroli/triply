#!/usr/bin/env python3
"""Check a triply trip file or user profile.

Usage:
    python3 validate.py <trip folder | trips folder | file.json> [--kind trip|profile] [--json]

A trip folder contains ``.triply/trip.json``; the trips folder contains
``.triply/profile.json``. Without ``--kind``, a file whose name ends with
``profile.json`` is checked as a user profile, any other file as a trip file.

The check has two layers:

1. the schema (``schemas/trip.schema.json`` or ``schemas/profile.schema.json``):
   fields, types and allowed values;
2. coherence rules that a schema cannot express: references between ids,
   dates, and the rules of the planning flow.

Errors make the file unusable: documents must not be generated from it.
Warnings point at something to review with the user.

Exit status: 0 no errors, 1 errors found, 2 the file could not be read.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))

import schema_check  # noqa: E402

SCHEMAS = Path(__file__).resolve().parent.parent / "schemas"

PHASES = [
    "setup",
    "brief",
    "destination",
    "entry_requirements",
    "route",
    "days",
    "verification",
    "bookings",
    "weather_packing",
    "documents",
]

ERROR = "error"
WARNING = "warning"


class Report:
    def __init__(self) -> None:
        self.issues: List[Dict[str, str]] = []

    def error(self, path: str, message: str) -> None:
        self.issues.append({"level": ERROR, "path": path, "message": message})

    def warning(self, path: str, message: str) -> None:
        self.issues.append({"level": WARNING, "path": path, "message": message})

    def count(self, level: str) -> int:
        return sum(1 for issue in self.issues if issue["level"] == level)

    @property
    def ok(self) -> bool:
        return self.count(ERROR) == 0


def load_schema(name: str) -> Dict[str, Any]:
    with open(SCHEMAS / f"{name}.schema.json", encoding="utf-8") as handle:
        return json.load(handle)


def _date(text: Optional[str]) -> Optional[datetime.date]:
    return datetime.date.fromisoformat(text) if text else None


# ---------------------------------------------------------------- trip file


def check_trip(data: Any) -> Report:
    report = Report()
    for path, message in schema_check.check(data, load_schema("trip")):
        report.error(path, message)
    if not report.ok:
        # Coherence rules assume a structurally valid file.
        return report

    _unique_ids(data, report)
    _references(data, report)
    _trip_dates(data, report)
    _days(data, report)
    _stays_and_transports(data, report)
    _options(data, report)
    _documents(data, report)
    _deadlines(data, report)
    _weather(data, report)
    return report


def _unique_ids(data: Dict[str, Any], report: Report) -> None:
    groups = {
        "/travellers": data["travellers"],
        "/options": data.get("options", []),
        "/stays": data.get("stays", []),
        "/transports": data.get("transports", []),
        "/deadlines": data.get("deadlines", []),
        "/progress/open_points": data["progress"]["open_points"],
    }
    for path, items in groups.items():
        seen: Set[str] = set()
        for index, item in enumerate(items):
            if item["id"] in seen:
                report.error(f"{path}/{index}/id", f"duplicate id '{item['id']}'")
            seen.add(item["id"])


def _references(data: Dict[str, Any], report: Report) -> None:
    places = set(data["places"])
    travellers = {t["id"] for t in data["travellers"]}
    stays = {s["id"] for s in data.get("stays", [])}
    transports = {t["id"] for t in data.get("transports", [])}
    anything = places | travellers | stays | transports

    def need(value: Optional[str], known: Set[str], path: str, what: str) -> None:
        if value is not None and value not in known:
            report.error(path, f"unknown {what} '{value}'")

    origin = data["constraints"].get("origin", {})
    need(origin.get("place"), places, "/constraints/origin/place", "place")
    for i, stay in enumerate(data.get("stays", [])):
        need(stay["place"], places, f"/stays/{i}/place", "place")
    for i, move in enumerate(data.get("transports", [])):
        need(move["from"], places, f"/transports/{i}/from", "place")
        need(move["to"], places, f"/transports/{i}/to", "place")
    for d, day in enumerate(data["days"]):
        need(day.get("base"), stays, f"/days/{d}/base", "stay")
        for c, candidate in enumerate(day.get("candidates", [])):
            need(candidate, places, f"/days/{d}/candidates/{c}", "place")
        for i, item in enumerate(day["items"]):
            need(item["place"], places, f"/days/{d}/items/{i}/place", "place")
    for i, req in enumerate(data.get("entry_requirements", [])):
        need(req["traveller"], travellers, f"/entry_requirements/{i}/traveller", "traveller")
    for i, entry in enumerate(data.get("weather", [])):
        need(entry["place"], places, f"/weather/{i}/place", "place")
    for i, deadline in enumerate(data.get("deadlines", [])):
        need(deadline.get("related"), anything, f"/deadlines/{i}/related", "id")
    for i, line in enumerate(data.get("budget", [])):
        need(line.get("related"), anything, f"/budget/{i}/related", "id")


def _trip_range(data: Dict[str, Any]):
    dates = data["constraints"]["dates"]
    return _date(dates.get("start")), _date(dates.get("end"))


def _trip_dates(data: Dict[str, Any], report: Report) -> None:
    trip = data["trip"]
    if _date(trip["updated"]) < _date(trip["created"]):
        report.error("/trip/updated", "is earlier than the creation date")

    dates = data["constraints"]["dates"]
    path = "/constraints/dates"
    fixed = [k for k in ("start", "end") if k in dates]
    window = [k for k in ("window_start", "window_end", "length_days") if k in dates]

    if fixed and len(fixed) != 2:
        report.error(path, "fixed dates need both 'start' and 'end'")
    if fixed and window:
        report.error(path, "use either fixed dates or a flexible window, not both")
    if len(fixed) == 2 and _date(dates["end"]) < _date(dates["start"]):
        report.error(f"{path}/end", "is earlier than 'start'")
    if window:
        if len(window) != 3:
            report.error(path, "a flexible window needs 'window_start', 'window_end' and 'length_days'")
        else:
            span = (_date(dates["window_end"]) - _date(dates["window_start"])).days + 1
            if span < 1:
                report.error(f"{path}/window_end", "is earlier than 'window_start'")
            elif dates["length_days"] > span:
                report.error(f"{path}/length_days", f"is longer than the window ({span} days)")

    phase = PHASES.index(data["progress"]["phase"])
    if not fixed and not window and phase > PHASES.index("brief"):
        report.warning(path, "no dates yet, but the brief is over")
    if window and phase >= PHASES.index("route"):
        report.warning(path, "the dates are still a flexible window, but the route is being planned")


def _days(data: Dict[str, Any], report: Report) -> None:
    start, end = _trip_range(data)
    stays = {s["id"]: s for s in data.get("stays", [])}
    previous: Optional[datetime.date] = None
    seen: Set[datetime.date] = set()

    for d, day in enumerate(data["days"]):
        path = f"/days/{d}"
        date = _date(day["date"])
        if date in seen:
            report.error(f"{path}/date", f"the day {day['date']} appears twice")
        elif previous and date < previous:
            report.error(f"{path}/date", "days are not in chronological order")
        seen.add(date)
        previous = date
        if start and end and not start <= date <= end:
            report.error(f"{path}/date", f"{day['date']} is outside the trip dates")

        base = stays.get(day.get("base", ""))
        if base and not _date(base["check_in"]) <= date < _date(base["check_out"]):
            report.warning(f"{path}/base", f"the stay '{base['id']}' does not cover the night of {day['date']}")

        mains = [i for i, item in enumerate(day["items"]) if item["role"] == "main"]
        if len(mains) > 1:
            report.warning(f"{path}/items", "more than one main activity in the same day")

        last_start = None
        for i, item in enumerate(day["items"]):
            place = data["places"].get(item["place"], {})
            status = place.get("verification", {}).get("status")
            if status == "failed":
                report.warning(f"{path}/items/{i}/place", f"'{item['place']}' failed its verification")
            if "start" in item:
                if last_start and item["start"] < last_start:
                    report.warning(f"{path}/items/{i}/start", "starts earlier than the previous stop")
                last_start = item["start"]


def _stays_and_transports(data: Dict[str, Any], report: Report) -> None:
    start, end = _trip_range(data)
    stays = sorted(
        enumerate(data.get("stays", [])), key=lambda pair: pair[1]["check_in"]
    )
    for i, stay in stays:
        check_in, check_out = _date(stay["check_in"]), _date(stay["check_out"])
        if check_out <= check_in:
            report.error(f"/stays/{i}/check_out", "must be after 'check_in'")
        if start and end and (check_in < start or check_out > end + datetime.timedelta(days=1)):
            report.warning(f"/stays/{i}", "falls outside the trip dates")
    for (i, a), (j, b) in zip(stays, stays[1:]):
        if _date(b["check_in"]) < _date(a["check_out"]):
            report.warning(f"/stays/{j}", f"overlaps with the stay '{a['id']}'")

    for i, move in enumerate(data.get("transports", [])):
        date = _date(move["date"])
        if start and end and not start <= date <= end:
            report.warning(f"/transports/{i}/date", f"{move['date']} is outside the trip dates")
        if move["from"] == move["to"]:
            report.error(f"/transports/{i}/to", "is the same place as 'from'")


def _options(data: Dict[str, Any], report: Report) -> None:
    for kind in ("destination", "route"):
        chosen = [o["id"] for o in data.get("options", []) if o["kind"] == kind and o["chosen"]]
        if len(chosen) > 1:
            report.error("/options", f"more than one chosen {kind}: {', '.join(chosen)}")


def _documents(data: Dict[str, Any], report: Report) -> None:
    _, end = _trip_range(data)
    if not end:
        return
    for t, traveller in enumerate(data["travellers"]):
        for d, document in enumerate(traveller.get("documents", [])):
            expires = _date(document.get("expires"))
            if expires and expires < end:
                report.warning(
                    f"/travellers/{t}/documents/{d}/expires",
                    f"the {document['type']} of '{traveller['label']}' expires before the end of the trip",
                )


def _deadlines(data: Dict[str, Any], report: Report) -> None:
    start, _ = _trip_range(data)
    if not start:
        return
    for i, deadline in enumerate(data.get("deadlines", [])):
        if not deadline["done"] and _date(deadline["due"]) > start:
            report.warning(f"/deadlines/{i}/due", "falls after the start of the trip")


def _weather(data: Dict[str, Any], report: Report) -> None:
    for i, entry in enumerate(data.get("weather", [])):
        if _date(entry["end"]) < _date(entry["start"]):
            report.error(f"/weather/{i}/end", "is earlier than 'start'")


# ------------------------------------------------------------- user profile


def check_profile(data: Any) -> Report:
    report = Report()
    for path, message in schema_check.check(data, load_schema("profile")):
        report.error(path, message)
    if report.ok:
        seen: Set[str] = set()
        for index, traveller in enumerate(data["travellers"]):
            if traveller["id"] in seen:
                report.error(f"/travellers/{index}/id", f"duplicate id '{traveller['id']}'")
            seen.add(traveller["id"])
    return report


# ---------------------------------------------------------------------- CLI


def resolve(target: Path) -> Path:
    if target.is_dir():
        candidate = target / ".triply" / "trip.json"
        if candidate.is_file():
            return candidate
        candidate = target / ".triply" / "profile.json"
        if candidate.is_file():
            return candidate
        raise FileNotFoundError(f"no .triply/trip.json or .triply/profile.json in {target}")
    return target


def run(target: Path, kind: Optional[str] = None) -> Report:
    path = resolve(target)
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if kind is None:
        kind = "profile" if path.name.endswith("profile.json") else "trip"
    return check_profile(data) if kind == "profile" else check_trip(data)


def _print(report: Report, as_json: bool, out: Any) -> None:
    if as_json:
        json.dump(
            {
                "ok": report.ok,
                "errors": report.count(ERROR),
                "warnings": report.count(WARNING),
                "issues": report.issues,
            },
            out,
            indent=2,
        )
        out.write("\n")
        return
    for issue in report.issues:
        out.write(f"{issue['level']}: {issue['path']}: {issue['message']}\n")
    out.write(f"{report.count(ERROR)} error(s), {report.count(WARNING)} warning(s)\n")


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check a triply trip file or user profile.")
    parser.add_argument("target", type=Path, help="trip folder, trip.json or profile.json")
    parser.add_argument("--kind", choices=["trip", "profile"], help="kind of file (default: from the file name)")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        report = run(args.target, args.kind)
    except (OSError, ValueError) as exc:
        # json.JSONDecodeError is a ValueError.
        sys.stderr.write(f"cannot read {args.target}: {exc}\n")
        return 2
    _print(report, args.json, sys.stdout)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
