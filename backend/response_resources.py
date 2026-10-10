"""In-app response context from public California evacuation and OSM feeds."""
import asyncio
import math
from datetime import datetime, timezone

import httpx

CAL_OES_LAYER = "https://services.arcgis.com/BLN4oKB0N1YSgvY8/arcgis/rest/services/CA_EVACUATIONS_CalOESHosted_view/FeatureServer/0/query"
CAL_FIRE_STATIONS = "https://services8.arcgis.com/Xr1lDrwMv89PhjD9/ArcGIS/rest/services/Facilities_for_Wildland_Fire_Protection_VCP/FeatureServer/2/query"
OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "WildfireWatch research prototype / public data viewer"
RADIUS_M = 25_000
STATION_RADIUS_M = 75_000


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance used only to sort nearby mapped facilities."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2-lat1), math.radians(lon2-lon1)
    value = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(value)))


def _clean(value, limit=600):
    if value is None:
        return ""
    return " ".join(str(value).split())[:limit]


def _evacuation_query(latitude, longitude):
    return {
        "where": "1=1",
        "geometry": f"{longitude},{latitude}",
        "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects",
        "distance": str(RADIUS_M),
        "units": "esriSRUnit_Meter",
        "inSR": "4326",
        "outSR": "4326",
        "outFields": "COUNTY,CITY,ZONE_NAME,ZONE_ID,STATUS,EVENT_TYPE,CRITICAL_INFO,PUBLIC_INFO,STATEWIDE_LAST_UPDATED,EDIT_DATE",
        "returnGeometry": "false",
        "resultRecordCount": "100",
        "f": "json",
    }


def _overpass_query(latitude, longitude):
    return f"""[out:json][timeout:15];
(
  node["emergency"="shelter"](around:20000,{latitude},{longitude});
  way["emergency"="shelter"](around:20000,{latitude},{longitude});
  node["amenity"="shelter"](around:20000,{latitude},{longitude});
  way["amenity"="shelter"](around:20000,{latitude},{longitude});
);
out center tags 100;"""


def _facilities(payload, latitude, longitude):
    items = []
    seen = set()
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        point = element.get("center") or element
        try:
            lat, lon = float(point["lat"]), float(point["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        kind = "shelter"
        name = _clean(tags.get("name") or tags.get("operator") or "Mapped shelter", 160)
        key = (kind, round(lat, 4), round(lon, 4), name.lower())
        if key in seen:
            continue
        seen.add(key)
        address = ", ".join(filter(None, [
            _clean(tags.get("addr:housenumber"), 20),
            _clean(tags.get("addr:street"), 100),
            _clean(tags.get("addr:city"), 100),
        ]))
        items.append({
            "kind": kind, "name": name, "latitude": lat, "longitude": lon,
            "distance_km": round(distance_km(latitude, longitude, lat, lon), 1),
            "address": address, "phone": _clean(tags.get("phone") or tags.get("contact:phone"), 80),
            "operator": _clean(tags.get("operator"), 120),
            "opening_hours": _clean(tags.get("opening_hours"), 120),
        })
    items.sort(key=lambda item: item["distance_km"])
    return items[:30]


def _fire_stations(payload, latitude, longitude):
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("Incomplete CAL FIRE facilities response")
    items = []
    for feature in features:
        props = feature.get("properties") or {}
        if props.get("FACILITY_STATUS") != "Active":
            continue
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        try:
            lon, lat = float(coordinates[0]), float(coordinates[1])
        except (IndexError, TypeError, ValueError):
            try:
                lat, lon = float(props["LAT"]), float(props["LON"])
            except (KeyError, TypeError, ValueError):
                continue
        address = ", ".join(filter(None, [
            _clean(props.get("ADDRESS"), 100), _clean(props.get("CITY"), 80),
            _clean(props.get("ZIP"), 16),
        ]))
        items.append({
            "name": _clean(props.get("NAME") or "Fire station", 160),
            "type": _clean(props.get("TYPE"), 20), "status": "Active",
            "county": _clean(props.get("COUNTY"), 80),
            "latitude": lat, "longitude": lon,
            "distance_km": round(distance_km(latitude, longitude, lat, lon), 1),
            "address": address, "phone": _clean(props.get("PHONE_NUM"), 40),
        })
    items.sort(key=lambda item: item["distance_km"])
    return items[:40]


def _evacuations(payload):
    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("Incomplete California evacuation feed")
    rows = []
    for feature in features:
        p = feature.get("attributes") or feature.get("properties") or {}
        status = _clean(p.get("STATUS"), 60)
        if not status or status.strip().upper() in {"NORMAL", "NONE", "INACTIVE"}:
            continue
        rows.append({
            "county": _clean(p.get("COUNTY"), 80), "city": _clean(p.get("CITY"), 100),
            "zone_name": _clean(p.get("ZONE_NAME"), 180), "zone_id": _clean(p.get("ZONE_ID"), 80),
            "status": status, "event_type": _clean(p.get("EVENT_TYPE"), 100),
            "critical_info": _clean(p.get("CRITICAL_INFO")), "public_info": _clean(p.get("PUBLIC_INFO")),
            "updated_at": p.get("STATEWIDE_LAST_UPDATED") or p.get("EDIT_DATE"),
        })
    rows.sort(key=lambda row: (0 if "order" in row["status"].lower() else 1, row["county"], row["zone_name"]))
    return rows


async def response_resources(latitude: float, longitude: float):
    """Fetch official aggregated evacuation zones and mapped nearby facilities."""
    checked_at = datetime.now(timezone.utc).isoformat()
    headers = {"User-Agent": USER_AGENT}
    station_params = {
        "where": "FACILITY_STATUS = 'Active' AND TYPE IN ('FSB','FSA','FSAB','FSL','FSCC','FSO')",
        "geometry": f"{longitude},{latitude}", "geometryType": "esriGeometryPoint",
        "spatialRel": "esriSpatialRelIntersects", "distance": str(STATION_RADIUS_M),
        "units": "esriSRUnit_Meter", "inSR": "4326", "outSR": "4326",
        "outFields": "NAME,TYPE,FACILITY_STATUS,COUNTY,ADDRESS,CITY,ZIP,PHONE_NUM,LAT,LON",
        "returnGeometry": "true", "resultRecordCount": "100", "f": "geojson",
    }
    async with httpx.AsyncClient(timeout=18, headers=headers) as client:
        evac_task = asyncio.create_task(client.get(CAL_OES_LAYER, params=_evacuation_query(latitude, longitude)))
        station_task = asyncio.create_task(client.get(CAL_FIRE_STATIONS, params=station_params))
        shelter_task = asyncio.create_task(client.post(OVERPASS, data={"data": _overpass_query(latitude, longitude)}))
        evac_response, station_response, shelter_response = await asyncio.gather(evac_task, station_task, shelter_task, return_exceptions=True)

    if isinstance(evac_response, Exception):
        evacuations = {"status": "unavailable", "zones": [], "checked_at": checked_at, "coverage_radius_km": 25}
    else:
        try:
            evac_response.raise_for_status()
            evacuations = {"status": "loaded", "zones": _evacuations(evac_response.json()), "checked_at": checked_at, "coverage_radius_km": 25}
        except (httpx.HTTPError, ValueError):
            evacuations = {"status": "unavailable", "zones": [], "checked_at": checked_at, "coverage_radius_km": 25}

    if isinstance(station_response, Exception):
        stations = {"status": "unavailable", "items": [], "checked_at": checked_at, "search_radius_km": STATION_RADIUS_M // 1000}
    else:
        try:
            station_response.raise_for_status()
            station_data = station_response.json()
            if station_data.get("error"):
                raise ValueError("CAL FIRE facilities service returned an error")
            stations = {"status": "loaded", "items": _fire_stations(station_data, latitude, longitude), "checked_at": checked_at, "search_radius_km": STATION_RADIUS_M // 1000}
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            stations = {"status": "unavailable", "items": [], "checked_at": checked_at, "search_radius_km": STATION_RADIUS_M // 1000}
    if isinstance(shelter_response, Exception):
        shelters = {"status": "unavailable", "items": [], "checked_at": checked_at, "search_radius_km": 20}
    else:
        try:
            shelter_response.raise_for_status()
            shelter_data = shelter_response.json()
            if not isinstance(shelter_data, dict) or "elements" not in shelter_data or shelter_data.get("remark"):
                raise ValueError("Incomplete OpenStreetMap response")
            shelters = {"status": "loaded", "items": _facilities(shelter_data, latitude, longitude), "checked_at": checked_at, "search_radius_km": 20}
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            shelters = {"status": "unavailable", "items": [], "checked_at": checked_at, "search_radius_km": 20}
    return {
        "checked_at": checked_at,
        "location": {"latitude": latitude, "longitude": longitude},
        "sources": {
            "evacuations": {**evacuations, "attribution": "California Office of Emergency Services · statewide county evacuation aggregation"},
            "fire_stations": {**stations, "attribution": "CAL FIRE and contract counties · Facilities for Wildland Fire Protection (active state, local, and contract fire stations; annual data release)"},
            "shelters": {**shelters, "attribution": "OpenStreetMap contributors · community-mapped shelter listings"},
        },
        "limitations": "The California evacuation feed covers jurisdictions that share public zone data; an empty result does not establish that no local order exists. OpenStreetMap facility listings may be incomplete or stale. No route is represented as safe or officially designated.",
    }
