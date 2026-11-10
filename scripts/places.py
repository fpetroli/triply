"""Points of interest by name — a temple, a museum, a beach — with the user's map service.

Standard library only. Three providers:

- ``osm``: Nominatim, the search service of OpenStreetMap. No account. Its usage
  policy (https://operations.osmfoundation.org/policies/nominatim/) allows at
  most one request per second, with a User-Agent that names the application,
  and asks to credit "© OpenStreetMap contributors".
- ``mapbox``: Mapbox Search Box API, forward search. Needs a public access
  token (``pk.…``).
- ``google``: Google Places API (New), Text Search. Needs an API key. Only the
  fields of the "Pro" tier are asked (no opening hours: they belong to a more
  expensive tier, and the verification phase checks them).

Every place found carries the provider and its id there, so that the
verification phase can look it up again with ``check``: whether the place is
still there, whether it is open for business, and its opening hours. With
Google, ``check`` asks the opening hours, which belong to the "Enterprise"
tier of Place Details (a smaller free monthly quota).
"""

from __future__ import annotations

import json
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

from climate import USER_AGENT, ServiceError

PROVIDERS = ("osm", "mapbox", "google")
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
MAPBOX_URL = "https://api.mapbox.com/search/searchbox/v1/forward"
GOOGLE_URL = "https://places.googleapis.com/v1/places:searchText"
NOMINATIM_LOOKUP_URL = "https://nominatim.openstreetmap.org/lookup"
MAPBOX_RETRIEVE_URL = "https://api.mapbox.com/search/searchbox/v1/retrieve/{id}"
GOOGLE_DETAILS_URL = "https://places.googleapis.com/v1/places/{id}"
GOOGLE_DETAILS_FIELDS = "id,displayName,businessStatus,regularOpeningHours,websiteUri,location"
MAX_LOOKUP_IDS = 50
GOOGLE_FIELDS = "places.id,places.displayName,places.formattedAddress,places.location,places.types,places.googleMapsUri"
NOMINATIM_INTERVAL_S = 1.1
NEAR_BOX_DEG = 0.3  # half side of the area that biases a search "near" a point
NEAR_RADIUS_M = 30000.0

# A request: (url, body or None, headers) -> parsed JSON.
Request = Optional[Callable[[str, Optional[Dict[str, Any]], Dict[str, str]], Any]]


class KeyRefusedError(ServiceError):
    """The provider refused the key: wrong, expired or without the needed service."""


class NotFoundError(ServiceError):
    """The provider has nothing at this address (HTTP 404): for a place id, the place is gone."""


def http_json(url: str, body: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: float = 20.0) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise KeyRefusedError(f"the service refused the request (HTTP {exc.code}): check the key and the services enabled for it") from exc
        if exc.code == 404:
            raise NotFoundError("the service answered HTTP 404") from exc
        raise ServiceError(f"the service answered HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise ServiceError(f"the service is not reachable: {exc}") from exc


def parse_near(text: Optional[str]) -> Optional[Tuple[float, float]]:
    if not text:
        return None
    try:
        lat, lon = (float(part) for part in text.split(","))
    except ValueError as exc:
        raise ValueError(f"--near must be LAT,LON: {text!r}") from exc
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"--near is not a valid point: {text!r}")
    return lat, lon


# ---------------------------------------------------------------- providers


def _osm(query: str, near, country, language, limit, key, request) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"q": query, "format": "jsonv2", "limit": limit, "extratags": 1, "accept-language": language}
    if country:
        params["countrycodes"] = country.lower()
    if near:
        lat, lon = near
        params["viewbox"] = f"{lon - NEAR_BOX_DEG},{lat + NEAR_BOX_DEG},{lon + NEAR_BOX_DEG},{lat - NEAR_BOX_DEG}"
        params["bounded"] = 0
    items = request(NOMINATIM_URL + "?" + urllib.parse.urlencode(params), None, {}) or []
    places = []
    for item in items:
        osm_id = f"{item.get('osm_type')}/{item.get('osm_id')}"
        extra = item.get("extratags") or {}
        place = {
            "name": item.get("name") or (item.get("display_name") or "").split(",")[0],
            "address": item.get("display_name"),
            "lat": round(float(item["lat"]), 6),
            "lon": round(float(item["lon"]), 6),
            "category": f"{item.get('category')}/{item.get('type')}",
            "provider_id": osm_id,
            "url": f"https://www.openstreetmap.org/{osm_id}",
        }
        if extra.get("opening_hours"):
            place["opening_hours"] = extra["opening_hours"]
        places.append(place)
    return places


def _mapbox(query: str, near, country, language, limit, key, request) -> List[Dict[str, Any]]:
    params: Dict[str, Any] = {"q": query, "access_token": key, "language": language, "limit": limit}
    if country:
        params["country"] = country.lower()
    if near:
        params["proximity"] = f"{near[1]},{near[0]}"
    data = request(MAPBOX_URL + "?" + urllib.parse.urlencode(params), None, {}) or {}
    places = []
    for feature in data.get("features", []) or []:
        props = feature.get("properties") or {}
        coords = props.get("coordinates") or {}
        lon_lat = (feature.get("geometry") or {}).get("coordinates") or [None, None]
        lat = coords.get("latitude", lon_lat[1])
        lon = coords.get("longitude", lon_lat[0])
        if lat is None or lon is None:
            continue
        categories = props.get("poi_category") or []
        places.append(
            {
                "name": props.get("name"),
                "address": props.get("full_address") or props.get("place_formatted"),
                "lat": round(float(lat), 6),
                "lon": round(float(lon), 6),
                "category": ", ".join(categories) if categories else props.get("feature_type"),
                "provider_id": props.get("mapbox_id"),
            }
        )
    return places


def _google(query: str, near, country, language, limit, key, request) -> List[Dict[str, Any]]:
    body: Dict[str, Any] = {"textQuery": query, "languageCode": language, "pageSize": limit}
    if country:
        body["regionCode"] = country.upper()
    if near:
        body["locationBias"] = {"circle": {"center": {"latitude": near[0], "longitude": near[1]}, "radius": NEAR_RADIUS_M}}
    data = request(GOOGLE_URL, body, {"X-Goog-Api-Key": key, "X-Goog-FieldMask": GOOGLE_FIELDS}) or {}
    places = []
    for item in data.get("places", []) or []:
        location = item.get("location") or {}
        if "latitude" not in location or "longitude" not in location:
            continue
        places.append(
            {
                "name": (item.get("displayName") or {}).get("text"),
                "address": item.get("formattedAddress"),
                "lat": round(float(location["latitude"]), 6),
                "lon": round(float(location["longitude"]), 6),
                "category": ", ".join((item.get("types") or [])[:3]),
                "provider_id": item.get("id"),
                "url": item.get("googleMapsUri"),
            }
        )
    return places


_SEARCH = {"osm": _osm, "mapbox": _mapbox, "google": _google}
_SOURCE = {
    "osm": ("osm", "https://nominatim.openstreetmap.org/", "OpenStreetMap (Nominatim) — © OpenStreetMap contributors"),
    "mapbox": ("mapbox", "https://docs.mapbox.com/api/search/search-box/", "Mapbox Search Box"),
    "google": ("google", "https://developers.google.com/maps/documentation/places/web-service/text-search", "Google Places"),
}


def find(
    provider: str,
    queries: List[str],
    near: Optional[Tuple[float, float]] = None,
    country: Optional[str] = None,
    language: str = "en",
    limit: int = 3,
    key: Optional[str] = None,
    today: str = "",
    request: Request = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict[str, Any]:
    """Search each query; a query that fails does not stop the others, except a refused key."""
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}: {', '.join(PROVIDERS)}")
    request = request or http_json
    search = _SEARCH[provider]
    results = []
    for n, query in enumerate(queries):
        if provider == "osm" and n:
            sleep(NOMINATIM_INTERVAL_S)
        try:
            results.append({"query": query, "places": search(query, near, country, language, limit, key, request)})
        except KeyRefusedError:
            raise
        except ServiceError as exc:
            results.append({"query": query, "places": [], "error": str(exc)})
    name, url, title = _SOURCE[provider]
    if all("error" in r for r in results):
        raise ServiceError(results[0]["error"])
    return {
        "provider": provider,
        "results": results,
        "source": {"provider": name, "url": url, "title": title, "checked_at": today},
    }


# ---------------------------------------------------------------- check by id

_OSM_TYPES = {"node": "N", "way": "W", "relation": "R"}
_GOOGLE_STATUS = {
    "OPERATIONAL": "open",
    "CLOSED_TEMPORARILY": "closed_temporarily",
    "CLOSED_PERMANENTLY": "closed_permanently",
    "FUTURE_OPENING": "future_opening",
}
_MAPBOX_STATUS = {"active": "open", "closed": "closed_permanently"}


def _osm_lookup_id(provider_id: str) -> str:
    kind, _, number = provider_id.partition("/")
    if kind not in _OSM_TYPES or not number.isdigit():
        raise ValueError(f"not an OpenStreetMap id (node/…, way/… or relation/…): {provider_id!r}")
    return _OSM_TYPES[kind] + number


def _check_osm(ids: List[str], language, key, request) -> List[Dict[str, Any]]:
    params = {"osm_ids": ",".join(_osm_lookup_id(i) for i in ids), "format": "jsonv2", "extratags": 1, "accept-language": language}
    items = request(NOMINATIM_LOOKUP_URL + "?" + urllib.parse.urlencode(params), None, {}) or []
    found = {f"{item.get('osm_type')}/{item.get('osm_id')}": item for item in items}
    results = []
    for provider_id in ids:
        item = found.get(provider_id)
        if item is None:
            results.append({"provider_id": provider_id, "found": False})
            continue
        extra = item.get("extratags") or {}
        result: Dict[str, Any] = {
            "provider_id": provider_id,
            "found": True,
            "name": item.get("name"),
            "lat": round(float(item["lat"]), 6),
            "lon": round(float(item["lon"]), 6),
            "url": f"https://www.openstreetmap.org/{provider_id}",
        }
        for tag, field in (("opening_hours", "opening_hours"), ("website", "website"), ("contact:website", "website")):
            if extra.get(tag) and field not in result:
                result[field] = extra[tag]
        results.append(result)
    return results


def _check_mapbox(ids: List[str], language, key, request) -> List[Dict[str, Any]]:
    results = []
    for provider_id in ids:
        params = {"session_token": str(uuid.uuid4()), "access_token": key, "language": language}
        url = MAPBOX_RETRIEVE_URL.format(id=urllib.parse.quote(provider_id, safe="")) + "?" + urllib.parse.urlencode(params)
        try:
            features = (request(url, None, {}) or {}).get("features") or []
        except NotFoundError:
            features = []
        except KeyRefusedError:
            raise
        except ServiceError as exc:
            results.append({"provider_id": provider_id, "error": str(exc)})
            continue
        if not features:
            results.append({"provider_id": provider_id, "found": False})
            continue
        props = features[0].get("properties") or {}
        coords = props.get("coordinates") or {}
        metadata = props.get("metadata") or {}
        result: Dict[str, Any] = {"provider_id": provider_id, "found": True, "name": props.get("name")}
        if "latitude" in coords and "longitude" in coords:
            result.update(lat=round(float(coords["latitude"]), 6), lon=round(float(coords["longitude"]), 6))
        status = _MAPBOX_STATUS.get(props.get("operational_status") or "")
        if status:
            result["status"] = status
        if (metadata.get("open_hours") or {}).get("periods"):
            result["opening_periods"] = metadata["open_hours"]["periods"]
        if metadata.get("website"):
            result["website"] = metadata["website"]
        results.append(result)
    return results


def _check_google(ids: List[str], language, key, request) -> List[Dict[str, Any]]:
    results = []
    for provider_id in ids:
        url = GOOGLE_DETAILS_URL.format(id=urllib.parse.quote(provider_id, safe="")) + "?" + urllib.parse.urlencode({"languageCode": language})
        try:
            item = request(url, None, {"X-Goog-Api-Key": key, "X-Goog-FieldMask": GOOGLE_DETAILS_FIELDS}) or {}
        except NotFoundError:
            item = {}
        except KeyRefusedError:
            raise
        except ServiceError as exc:
            results.append({"provider_id": provider_id, "error": str(exc)})
            continue
        if not item.get("id"):
            results.append({"provider_id": provider_id, "found": False})
            continue
        location = item.get("location") or {}
        hours = item.get("regularOpeningHours") or {}
        result: Dict[str, Any] = {"provider_id": provider_id, "found": True, "name": (item.get("displayName") or {}).get("text")}
        if "latitude" in location and "longitude" in location:
            result.update(lat=round(float(location["latitude"]), 6), lon=round(float(location["longitude"]), 6))
        status = _GOOGLE_STATUS.get(item.get("businessStatus") or "")
        if status:
            result["status"] = status
        if hours.get("weekdayDescriptions"):
            result["opening_hours"] = "; ".join(hours["weekdayDescriptions"])
        elif "periods" in hours and not hours["periods"]:
            result["opening_hours"] = "never open"
        if item.get("websiteUri"):
            result["website"] = item["websiteUri"]
        results.append(result)
    return results


_CHECK = {"osm": _check_osm, "mapbox": _check_mapbox, "google": _check_google}
_CHECK_SOURCE = {
    "osm": ("osm", "https://nominatim.openstreetmap.org/", "OpenStreetMap (Nominatim) — © OpenStreetMap contributors"),
    "mapbox": ("mapbox", "https://docs.mapbox.com/api/search/search-box/", "Mapbox Search Box"),
    "google": ("google", "https://developers.google.com/maps/documentation/places/web-service/place-details", "Google Places"),
}


def check(
    provider: str,
    ids: List[str],
    language: str = "en",
    key: Optional[str] = None,
    today: str = "",
    request: Request = None,
) -> Dict[str, Any]:
    """Look places up again by their id: found or not, status, opening hours, website."""
    if provider not in PROVIDERS:
        raise ValueError(f"unknown provider {provider!r}: {', '.join(PROVIDERS)}")
    if not 1 <= len(ids) <= MAX_LOOKUP_IDS:
        raise ValueError(f"give from 1 to {MAX_LOOKUP_IDS} ids")
    results = _CHECK[provider](ids, language, key, request or http_json)
    if all("error" in r for r in results):
        raise ServiceError(results[0]["error"])
    name, url, title = _CHECK_SOURCE[provider]
    return {"provider": provider, "places": results, "source": {"provider": name, "url": url, "title": title, "checked_at": today}}
