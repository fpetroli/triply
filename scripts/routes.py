"""Travel times between points, with the user's map service.

Standard library only. Three providers:

- ``osm``: the OSRM routing servers of FOSSGIS (https://routing.openstreetmap.de/),
  built on OpenStreetMap data, for car, bike and foot. No account. Usage policy
  (https://routing.openstreetmap.de/about.html): at most one request per second,
  a valid User-Agent, no heavy use, and the credit to OpenStreetMap. Car times
  do not include traffic.
- ``mapbox``: Mapbox Directions API, with the public token.
- ``google``: Google Routes API (computeRoutes), with the API key; the only one
  that computes public transport. Only duration and distance are asked, which
  keeps driving, walking and cycling requests in the "Essentials" tier.

All points of a call are visited in order: the result has one leg per pair of
consecutive points. With ``osm`` and ``mapbox`` a call is one request; with
``google``, one request per leg.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from climate import ServiceError
from places import Request, http_json

PROVIDERS = ("osm", "mapbox", "google")
MODES = ("walk", "bike", "car", "public_transport")
MAX_POINTS = 10
OSRM_URL = "https://routing.openstreetmap.de/routed-{server}/route/v1/{profile}/{coordinates}?overview=false"
OSRM_PROFILES = {"walk": ("foot", "walking"), "bike": ("bike", "cycling"), "car": ("car", "driving")}
MAPBOX_URL = "https://api.mapbox.com/directions/v5/mapbox/{profile}/{coordinates}"
MAPBOX_PROFILES = {"walk": "walking", "bike": "cycling", "car": "driving"}
GOOGLE_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
GOOGLE_FIELDS = "routes.duration,routes.distanceMeters"
GOOGLE_MODES = {"walk": "WALK", "bike": "BICYCLE", "car": "DRIVE", "public_transport": "TRANSIT"}

Point = Tuple[float, float]


class UnsupportedError(ServiceError):
    """The provider cannot compute this mode (public transport outside Google)."""


class NoRouteError(ServiceError):
    """The provider found no route between two points."""


def _coordinates(points: List[Point]) -> str:
    return ";".join(f"{lon},{lat}" for lat, lon in points)


def _leg(index: int, seconds: float, meters: float) -> Dict[str, Any]:
    return {"from": index, "to": index + 1, "minutes": max(1, round(seconds / 60)), "distance_km": round(meters / 1000, 1)}


def _osrm_legs(data: Dict[str, Any], points: List[Point]) -> List[Dict[str, Any]]:
    if data.get("code") != "Ok" or not data.get("routes"):
        raise NoRouteError(f"no route found ({data.get('code') or 'empty answer'})")
    legs = data["routes"][0].get("legs") or []
    if len(legs) != len(points) - 1:
        raise ServiceError("the answer does not have one leg per pair of points")
    return [_leg(i, leg["duration"], leg["distance"]) for i, leg in enumerate(legs)]


def _osm(mode, points, key, depart, request) -> List[Dict[str, Any]]:
    server, profile = OSRM_PROFILES[mode]
    url = OSRM_URL.format(server=server, profile=profile, coordinates=_coordinates(points))
    return _osrm_legs(request(url, None, {}) or {}, points)


def _mapbox(mode, points, key, depart, request) -> List[Dict[str, Any]]:
    url = MAPBOX_URL.format(profile=MAPBOX_PROFILES[mode], coordinates=_coordinates(points))
    url += "?" + urllib.parse.urlencode({"access_token": key, "overview": "false"})
    return _osrm_legs(request(url, None, {}) or {}, points)


def _seconds(text: str) -> float:
    if not isinstance(text, str) or not text.endswith("s"):
        raise ServiceError(f"unexpected duration {text!r}")
    return float(text[:-1])


def _google(mode, points, key, depart, request) -> List[Dict[str, Any]]:
    legs = []
    for i, (a, b) in enumerate(zip(points, points[1:])):
        body: Dict[str, Any] = {
            "origin": {"location": {"latLng": {"latitude": a[0], "longitude": a[1]}}},
            "destination": {"location": {"latLng": {"latitude": b[0], "longitude": b[1]}}},
            "travelMode": GOOGLE_MODES[mode],
        }
        if depart and mode in ("public_transport", "car"):
            body["departureTime"] = depart
        data = request(GOOGLE_URL, body, {"X-Goog-Api-Key": key, "X-Goog-FieldMask": GOOGLE_FIELDS}) or {}
        routes = data.get("routes") or []
        if not routes:
            raise NoRouteError(f"no route found from point {i + 1} to point {i + 2}")
        legs.append(_leg(i, _seconds(routes[0].get("duration")), routes[0].get("distanceMeters") or 0))
    return legs


_ROUTE = {"osm": _osm, "mapbox": _mapbox, "google": _google}
_SOURCE = {
    "osm": ("osm", "https://routing.openstreetmap.de/", "OSRM on OpenStreetMap data (FOSSGIS) — © OpenStreetMap contributors"),
    "mapbox": ("mapbox", "https://docs.mapbox.com/api/navigation/directions/", "Mapbox Directions"),
    "google": ("google", "https://developers.google.com/maps/documentation/routes", "Google Routes"),
}


def parse_point(text: str) -> Point:
    try:
        lat, lon = (float(part) for part in text.split(","))
    except ValueError as exc:
        raise ValueError(f"a point must be LAT,LON: {text!r}") from exc
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"not a valid point: {text!r}")
    return lat, lon


def route(
    provider: str,
    mode: str,
    points: List[Point],
    key: Optional[str] = None,
    depart: Optional[str] = None,
    today: str = "",
    request: Request = None,
) -> Dict[str, Any]:
    """Travel time and distance of each leg between consecutive points."""
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}: {', '.join(PROVIDERS)}")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}: {', '.join(MODES)}")
    if not 2 <= len(points) <= MAX_POINTS:
        raise ValueError(f"give from 2 to {MAX_POINTS} points")
    if mode == "public_transport" and provider != "google":
        raise UnsupportedError(f"{provider} does not compute public transport: only Google does")
    legs = _ROUTE[provider](mode, points, key, depart, request or http_json)
    name, url, title = _SOURCE[provider]
    return {
        "provider": provider,
        "mode": mode,
        "legs": legs,
        "total_minutes": sum(leg["minutes"] for leg in legs),
        "source": {"provider": name, "url": url, "title": title, "checked_at": today},
    }
