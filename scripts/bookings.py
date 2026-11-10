"""Search links already filled in, and the costs of a trip.

Standard library only. triply never queries the booking sites: it only builds
links that open their search page with places, dates and travellers already
set. These sites do not document the format of their links: when one
changes, the link still opens the site, perhaps without the data filled in.
No link ever carries an affiliate code.

Links by kind:

- stays: Booking.com and Airbnb (place name, dates, travellers);
- flights: Google Flights (place names and date) and Skyscanner (with the
  IATA codes of the places, when the trip file has them);
- trains, buses and ferries: Rome2rio (place names), next to the official
  site of the operator, which Claude adds from the verification phase.
"""

from __future__ import annotations

import datetime
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

ADULTS = ("adult", "senior")
CHILDREN = ("child", "teen")
INFANTS = ("infant",)


def travellers_count(travellers: List[Dict[str, Any]]) -> Tuple[int, int, int]:
    groups = [t.get("age_group") for t in travellers]
    return (
        sum(g in ADULTS for g in groups),
        sum(g in CHILDREN for g in groups),
        sum(g in INFANTS for g in groups),
    )


def _link(label: str, base: str, params: Dict[str, Any]) -> Dict[str, Any]:
    return {"label": label, "url": base + "?" + urllib.parse.urlencode(params), "generated": True}


def stay_links(place: str, check_in: str, check_out: str, travellers: List[Dict[str, Any]], language: str) -> List[Dict[str, Any]]:
    adults, children, infants = travellers_count(travellers)
    lang = language.split("-")[0]
    booking = {
        "ss": place,
        "checkin": check_in,
        "checkout": check_out,
        "group_adults": adults,
        "group_children": children + infants,
        "no_rooms": 1,
        "lang": lang,
    }
    airbnb = {"checkin": check_in, "checkout": check_out, "adults": adults}
    if children:
        airbnb["children"] = children
    if infants:
        airbnb["infants"] = infants
    return [
        _link("Booking.com", "https://www.booking.com/searchresults.html", booking),
        _link("Airbnb", f"https://www.airbnb.com/s/{urllib.parse.quote(place)}/homes", airbnb),
    ]


def flight_links(
    origin: Dict[str, Any], destination: Dict[str, Any], date: str, travellers: List[Dict[str, Any]], language: str
) -> List[Dict[str, Any]]:
    adults, _, _ = travellers_count(travellers)
    lang = language.split("-")[0]
    query = f"Flights to {destination['name']} from {origin['name']} on {date} oneway"
    links = [_link("Google Flights", "https://www.google.com/travel/flights", {"q": query, "hl": lang})]
    if origin.get("iata") and destination.get("iata"):
        day = datetime.date.fromisoformat(date).strftime("%y%m%d")
        path = f"https://www.skyscanner.net/transport/flights/{origin['iata'].lower()}/{destination['iata'].lower()}/{day}/"
        links.append(_link("Skyscanner", path, {"adultsv2": adults, "rtn": 0}))
    return links


def ground_links(origin: Dict[str, Any], destination: Dict[str, Any]) -> List[Dict[str, Any]]:
    def name(place: Dict[str, Any]) -> str:
        return urllib.parse.quote(place["name"].replace(" ", "-"))

    return [{"label": "Rome2rio", "url": f"https://www.rome2rio.com/map/{name(origin)}/{name(destination)}", "generated": True}]


def _merge(booking: Dict[str, Any], links: List[Dict[str, Any]]) -> None:
    """Replace the links made by triply; keep the ones added by hand (official sites)."""
    kept = [link for link in booking.get("links", []) if not link.get("generated")]
    booking["links"] = links + kept


def fill_links(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Add the search links to every stay and transport still to book. Returns what was done."""
    places = data["places"]
    travellers = data["travellers"]
    language = data["trip"]["language"]
    done = []
    for stay in data.get("stays", []):
        if stay["booking"]["status"] != "to_book":
            continue
        place = places[stay["place"]]
        links = stay_links(place["name"], stay["check_in"], stay["check_out"], travellers, language)
        _merge(stay["booking"], links)
        done.append({"stay": stay["id"], "links": [link["label"] for link in links]})
    for move in data.get("transports", []):
        if move["booking"]["status"] != "to_book":
            continue
        origin, destination = places[move["from"]], places[move["to"]]
        if move["mode"] == "flight":
            links = flight_links(origin, destination, move["date"], travellers, language)
        elif move["mode"] in ("train", "bus", "ferry"):
            links = ground_links(origin, destination)
        else:
            done.append({"transport": move["id"], "links": [], "note": f"no search link for mode '{move['mode']}'"})
            continue
        _merge(move["booking"], links)
        entry: Dict[str, Any] = {"transport": move["id"], "links": [link["label"] for link in links]}
        if move["mode"] == "flight" and len(links) == 1:
            entry["note"] = "no Skyscanner link: add the IATA codes of the two places (iata)"
        done.append(entry)
    return done


# ---------------------------------------------------------------- costs


def _bookings(data: Dict[str, Any]):
    for stay in data.get("stays", []):
        yield stay["id"], stay["booking"]
    for move in data.get("transports", []):
        yield move["id"], move["booking"]
    for day in data["days"]:
        for item in day["items"]:
            if "booking" in item:
                yield f"{day['date']}/{item['place']}", item["booking"]


def costs(data: Dict[str, Any]) -> Dict[str, Any]:
    """Totals per currency: booked (costs of the bookings), other confirmed and estimated costs; the budget."""
    totals: Dict[str, Dict[str, float]] = {}

    def add(currency: str, kind: str, amount: float) -> None:
        line = totals.setdefault(currency, {"booked": 0.0, "confirmed": 0.0, "estimated": 0.0})
        line[kind] = round(line[kind] + amount, 2)

    without_cost = []
    with_cost = set()
    for ref, booking in _bookings(data):
        if "cost" in booking:
            add(booking["cost"]["currency"], "booked", booking["cost"]["amount"])
            with_cost.add(ref.split("/")[-1])
        elif booking["status"] == "booked":
            without_cost.append(ref)
    for line in data.get("budget", []):
        # A line about something whose booking has its cost is not counted twice.
        if line["status"] in ("confirmed", "estimated") and line.get("related") not in with_cost:
            add(line["currency"], line["status"], line["amount"])

    result: Dict[str, Any] = {"totals": totals, "booked_without_cost": without_cost}
    budget = data["constraints"].get("budget")
    if budget:
        amount = budget["amount"] * (len(data["travellers"]) if budget["scope"] == "per_person" else 1)
        spent = totals.get(budget["currency"], {})
        committed = round(spent.get("booked", 0) + spent.get("confirmed", 0), 2)
        result["budget"] = {
            "currency": budget["currency"],
            "amount": round(amount, 2),
            "committed": committed,
            "estimated": spent.get("estimated", 0.0),
            "left": round(amount - committed, 2),
        }
        others = sorted(c for c in totals if c != budget["currency"])
        if others:
            result["budget"]["other_currencies"] = others
    return result
