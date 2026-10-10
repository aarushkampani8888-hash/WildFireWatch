import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.regional_evidence import perimeter_distance_km, _thermal, regional_map


def test_perimeter_distance_is_zero_inside_polygon():
    polygon = {"type": "Polygon", "coordinates": [[
        [-120.1, 38.9], [-119.9, 38.9], [-119.9, 39.1],
        [-120.1, 39.1], [-120.1, 38.9],
    ]]}
    assert perimeter_distance_km(polygon, -120, 39) == 0


def test_perimeter_distance_is_local_distance_to_edge():
    polygon = {"type": "Polygon", "coordinates": [[
        [-120.1, 38.9], [-119.9, 38.9], [-119.9, 39.1],
        [-120.1, 39.1], [-120.1, 38.9],
    ]]}
    distance = perimeter_distance_km(polygon, -120.2, 39)
    assert 8 < distance < 10


def test_latest_satellite_feed_is_not_matched_to_old_observation(monkeypatch):
    monkeypatch.setenv("FIRMS_MAP_KEY", "configured-for-test")

    class NoNetwork:
        def __init__(self, *args, **kwargs):
            raise AssertionError("A stale report must not trigger a FIRMS request")

    import backend.regional_evidence as module
    monkeypatch.setattr(module.httpx, "AsyncClient", NoNetwork)
    stale = (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    result = asyncio.run(_thermal(None, 39, -120, stale))
    assert result["status"] == "time_mismatch"
    assert result["detections"] == []


def test_regional_map_includes_loaded_nasa_thermal_pixels_and_perimeters():
    perimeter = {"features": [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-120.1, 39.2]},
        "properties": {"kind": "official-perimeter", "name": "Example"},
    }]}
    thermal = {"status": "loaded", "detections": [{
        "latitude": 39.25,
        "longitude": -120.2,
        "observed_at": "2026-10-10T12:00:00+00:00",
        "source": "NASA FIRMS / VIIRS NOAA-20 NRT",
        "confidence": "nominal",
        "distance_km": 8.2,
        "hours_from_observation": 1.5,
        "frp": "4.2",
    }]}

    result = regional_map(perimeter, thermal)

    assert len(result["features"]) == 2
    hotspot = result["features"][1]
    assert hotspot["geometry"] == {"type": "Point", "coordinates": [-120.2, 39.25]}
    assert hotspot["properties"]["kind"] == "thermal-anomaly"
    assert hotspot["properties"]["source"].startswith("NASA FIRMS")
