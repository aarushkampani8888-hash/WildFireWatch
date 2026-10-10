"""Live public fire/weather corroboration around one submitted observation."""
import asyncio
import csv
import io
import json
import math
import os
import re
from datetime import datetime, timezone

import httpx


EARTH_KM = 6371.0088
NIFC_LAYER = "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/WFIGS_Interagency_Perimeters_Current/FeatureServer/0"
NWS_AGENT = "WildfireWatch/0.3 (research prototype; public-data corroboration)"


def _project(lon, lat, origin_lon, origin_lat):
    x = math.radians(lon-origin_lon)*EARTH_KM*math.cos(math.radians(origin_lat))
    y = math.radians(lat-origin_lat)*EARTH_KM
    return x, y


def _ring_contains(point, ring):
    x, y = point
    inside = False
    previous = ring[-1]
    for current in ring:
        x1, y1 = current[:2]
        x2, y2 = previous[:2]
        if ((y1 > y) != (y2 > y)) and x < (x2-x1)*(y-y1)/(y2-y1 or 1e-12)+x1:
            inside = not inside
        previous = current
    return inside


def _segment_distance(point, first, second):
    px, py = point
    ax, ay = first
    bx, by = second
    dx, dy = bx-ax, by-ay
    length = dx*dx+dy*dy
    t = 0 if not length else max(0, min(1, ((px-ax)*dx+(py-ay)*dy)/length))
    return math.hypot(px-(ax+t*dx), py-(ay+t*dy))


def perimeter_distance_km(geometry, longitude, latitude):
    """Approximate local point-to-polygon distance; zero if inside a ring."""
    polygons = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        polygons = [polygons]
    origin = (longitude, latitude)
    point = (0.0, 0.0)
    closest = float("inf")
    for polygon in polygons:
        projected = [[_project(p[0], p[1], *origin) for p in ring if len(p) >= 2] for ring in polygon]
        if not projected or not projected[0]:
            continue
        inside_outer = _ring_contains(point, projected[0])
        inside_hole = any(_ring_contains(point, ring) for ring in projected[1:] if ring)
        if inside_outer and not inside_hole:
            return 0.0
        for ring in projected:
            for index, first in enumerate(ring):
                second = ring[(index+1) % len(ring)]
                closest = min(closest, _segment_distance(point, first, second))
    return closest


def _timestamp(epoch_ms):
    if not epoch_ms:
        return None
    try:
        return datetime.fromtimestamp(float(epoch_ms)/1000, timezone.utc).isoformat()
    except (ValueError, TypeError, OSError):
        return None


async def _perimeters(client, latitude, longitude):
    lat_delta = 75/EARTH_KM*180/math.pi
    lon_delta = lat_delta/max(0.2, math.cos(math.radians(latitude)))
    params = {
        "where": "1=1",
        "geometry": json.dumps({"xmin":longitude-lon_delta,"ymin":latitude-lat_delta,"xmax":longitude+lon_delta,"ymax":latitude+lat_delta}),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "inSR": "4326", "outSR": "4326",
        "outFields": "poly_IncidentName,poly_DateCurrent,poly_PolygonDateTime,poly_GISAcres,poly_MapMethod,poly_Source",
        "returnGeometry": "true", "maxAllowableOffset": "0.002", "geometryPrecision": "5",
        "resultRecordCount": "100", "f": "geojson",
    }
    response = await client.get(NIFC_LAYER+"/query", params=params)
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError("NIFC query failed")
    features = []
    for feature in data.get("features", []):
        geometry = feature.get("geometry")
        if not geometry:
            continue
        distance = perimeter_distance_km(geometry, longitude, latitude)
        if distance > 75:
            continue
        attrs = feature.get("properties", {})
        name = attrs.get("poly_IncidentName") or "Unnamed incident"
        features.append({
            "type": "Feature", "geometry": geometry,
            "properties": {"kind":"official-perimeter","name":name,"distance_km":round(distance,1)},
            "name": name, "distance_km": round(distance,1),
            "acres": attrs.get("poly_GISAcres"),
            "last_updated": _timestamp(attrs.get("poly_DateCurrent")),
            "perimeter_observed_at": _timestamp(attrs.get("poly_PolygonDateTime")),
            "map_method": attrs.get("poly_MapMethod"), "source": attrs.get("poly_Source"),
        })
    features.sort(key=lambda feature: feature["distance_km"])
    return {"status":"loaded","refreshed_at":datetime.now(timezone.utc).isoformat(),"count":len(features),"features":features[:8],"attribution":"NIFC / WFIGS current interagency fire perimeters","limitations":"Only approved, public, current perimeters are included; many incidents have no published perimeter. Distance is from the observer coordinate, not the fire edge inferred from the image."}


async def _weather_alerts(client, latitude, longitude):
    response = await client.get(
        "https://api.weather.gov/alerts/active",
        params={"point":f"{latitude},{longitude}"},
        headers={"User-Agent":NWS_AGENT,"Accept":"application/geo+json"},
    )
    response.raise_for_status()
    payload = response.json()
    if "features" not in payload:
        raise RuntimeError("NWS alert response was incomplete")
    features = payload.get("features", [])
    alerts = []
    for feature in features:
        if len(alerts) >= 12:
            break
        item = feature.get("properties", {})
        event = str(item.get("event") or "Weather alert")[:120]
        if not re.search(r"fire|smoke|red flag|wind|heat", event, re.I):
            continue
        alerts.append({"event":event,"headline":str(item.get("headline") or "")[:280],
            "severity":item.get("severity"),"urgency":item.get("urgency"),
            "effective":item.get("effective"),"expires":item.get("expires"),
            "url":item.get("@id")})
    return {"status":"loaded","checked_at":datetime.now(timezone.utc).isoformat(),"alerts":alerts,"attribution":"NOAA National Weather Service active alerts","limitations":"Current alerts at the observer coordinate; they are not incident-specific and may not describe weather at the observation time."}


def _firms_box(latitude, longitude):
    lat_delta = 25/EARTH_KM*180/math.pi
    lon_delta = lat_delta/max(0.2, math.cos(math.radians(latitude)))
    return (longitude-lon_delta, latitude-lat_delta, longitude+lon_delta, latitude+lat_delta)


def regional_map(perimeter, thermal):
    """Build the map overlay from the same dated regional results shown in Investigation."""
    features = list(perimeter.get("features", []))
    if thermal.get("status") == "loaded":
        for detection in thermal.get("detections", []):
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [detection["longitude"], detection["latitude"]]},
                "properties": {
                    "kind": "thermal-anomaly",
                    "source": detection.get("source", "NASA FIRMS / VIIRS"),
                    "observed_at": detection.get("observed_at"),
                    "satellite": detection.get("satellite"),
                    "confidence": detection.get("confidence"),
                    "distance_km": detection.get("distance_km"),
                    "hours_from_observation": detection.get("hours_from_observation"),
                    "frp": detection.get("frp"),
                },
            })
    return {"type": "FeatureCollection", "features": features}


async def _thermal(client, latitude, longitude, observed_at):
    key = os.environ.get("FIRMS_MAP_KEY")
    if not key:
        return {"status":"not_configured","detections":[],"attribution":"NASA FIRMS / VIIRS NOAA-20","limitations":"Set FIRMS_MAP_KEY on the backend for live satellite thermal detections."}
    try:
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        if abs((datetime.now(timezone.utc)-observed).total_seconds()) > 36*3600:
            return {"status":"time_mismatch","detections":[],"attribution":"NASA FIRMS / VIIRS NOAA-20","limitations":"Latest satellite detections are not time-aligned to this observation, so they were not compared."}
        west, south, east, north = _firms_box(latitude, longitude)
        url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/VIIRS_NOAA20_NRT/{west:.4f},{south:.4f},{east:.4f},{north:.4f}/1"
        response = await client.get(url)
        response.raise_for_status()
        if not response.text.strip() or "latitude" not in response.text.splitlines()[0].lower():
            raise ValueError("Unexpected NASA FIRMS response")
        rows = list(csv.DictReader(io.StringIO(response.text)))
        detections = []
        for row in rows[:1000]:
            try:
                lat, lon = float(row["latitude"]), float(row["longitude"])
                stamp = datetime.fromisoformat(row["acq_date"]+"T"+row["acq_time"].zfill(4)[:2]+":"+row["acq_time"].zfill(4)[2:]+":00+00:00")
            except (KeyError, ValueError):
                continue
            km = 2*EARTH_KM*math.asin(min(1, math.sqrt(
                math.sin(math.radians(lat-latitude)/2)**2+
                math.cos(math.radians(latitude))*math.cos(math.radians(lat))*math.sin(math.radians(lon-longitude)/2)**2)))
            hours = abs((observed-stamp).total_seconds())/3600
            if km > 25 or hours > 24:
                continue
            detections.append({"latitude":lat,"longitude":lon,"distance_km":round(km,1),"hours_from_observation":round(hours,1),"observed_at":stamp.isoformat(),"confidence":row.get("confidence"),"frp":row.get("frp"),"satellite":row.get("satellite","NOAA-20"),"source":"NASA FIRMS / VIIRS NOAA-20 NRT"})
        detections.sort(key=lambda item:(item["distance_km"],item["hours_from_observation"]))
        return {"status":"loaded","checked_at":datetime.now(timezone.utc).isoformat(),"detections":detections[:10],"attribution":"NASA FIRMS / VIIRS NOAA-20 Near Real-Time","limitations":"Thermal pixels are not fire confirmations; cloud cover, overpass timing, pixel footprint, and non-fire heat sources affect detections."}
    except Exception:
        return {"status":"unavailable","detections":[],"attribution":"NASA FIRMS / VIIRS NOAA-20","limitations":"NASA FIRMS could not be reached. No substitute data was used."}


async def regional_evidence(latitude, longitude, observed_at):
    """Fetch independent federal signals concurrently; keep per-source failures visible."""
    async with httpx.AsyncClient(timeout=22, headers={"User-Agent":NWS_AGENT}) as client:
        perimeter_task = asyncio.create_task(_perimeters(client, latitude, longitude))
        alerts_task = asyncio.create_task(_weather_alerts(client, latitude, longitude))
        thermal_task = asyncio.create_task(_thermal(client, latitude, longitude, observed_at))
        perimeter, alerts, thermal = await asyncio.gather(perimeter_task, alerts_task, thermal_task, return_exceptions=True)
    def source(result, fallback, field, attribution):
        if isinstance(result, Exception):
            return {"status":"unavailable",field:[],"attribution":attribution,"limitations":fallback}
        return result
    perimeter = source(perimeter,"NIFC current perimeter service could not be reached; no substitute data was used.","features","NIFC / WFIGS")
    alerts = source(alerts,"NWS alerts could not be reached; no substitute data was used.","alerts","NOAA National Weather Service")
    # Keep NASA thermal detections and NIFC perimeters in one sourced map overlay.
    geojson = regional_map(perimeter, thermal)
    return {"generated_at":datetime.now(timezone.utc).isoformat(),
        "subject":{"latitude":latitude,"longitude":longitude,"role":"observer coordinate, not inferred fire location"},
        "sources":{"nifc":perimeter,"firms":thermal,"nws":alerts},"map":geojson,
        "interpretation":"Independent sources are displayed separately; no weighted or calibrated fire probability is computed. A missing match does not rule out a fire."}
