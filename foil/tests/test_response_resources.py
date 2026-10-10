from backend.response_resources import _evacuations, _facilities, _fire_stations, _evacuation_query, distance_km


def test_evacuation_query_uses_25km_radius_around_pin():
    query = _evacuation_query(36.1, -117.5)
    assert query["geometry"] == "-117.5,36.1"
    assert query["distance"] == "25000"
    assert query["geometryType"] == "esriGeometryPoint"


def test_evacuation_feed_keeps_active_orders_and_warnings_only():
    rows = _evacuations({"features": [
        {"attributes": {"STATUS": "NORMAL", "ZONE_NAME": "not active"}},
        {"attributes": {"STATUS": "Evacuation Warning", "COUNTY": "Alpha", "ZONE_NAME": "Zone A"}},
        {"attributes": {"STATUS": "Evacuation Order", "COUNTY": "Beta", "ZONE_NAME": "Zone B", "PUBLIC_INFO": " Leave now\n Check local instructions "}},
    ]})
    assert [row["zone_name"] for row in rows] == ["Zone B", "Zone A"]
    assert rows[0]["public_info"] == "Leave now Check local instructions"


def test_community_shelters_are_sorted_and_include_distance():
    items = _facilities({"elements": [
        {"type": "way", "center": {"lat": 36.2, "lon": -117.5}, "tags": {"amenity": "shelter", "name": "Far shelter"}},
        {"type": "node", "lat": 36.11, "lon": -117.5, "tags": {"amenity": "shelter", "name": "Near shelter", "phone": "555-0100"}},
    ]}, 36.1, -117.5)
    assert [item["name"] for item in items] == ["Near shelter", "Far shelter"]
    assert items[0]["distance_km"] < items[1]["distance_km"]
    assert items[0]["phone"] == "555-0100"
    assert items[0]["kind"] == "shelter"
    assert 10 < distance_km(36.1, -117.5, 36.2, -117.5) < 12


def test_fire_stations_keep_active_facilities_and_sort_nearest_first():
    items = _fire_stations({"features": [
        {"properties": {"FACILITY_STATUS": "Inactive", "NAME": "Old station", "LAT": 36.11, "LON": -117.5}},
        {"geometry": {"coordinates": [-117.5, 36.2]}, "properties": {"FACILITY_STATUS": "Active", "NAME": "Far station", "TYPE": "FSB", "COUNTY": "Alpha"}},
        {"geometry": {"coordinates": [-117.5, 36.11]}, "properties": {"FACILITY_STATUS": "Active", "NAME": "Near station", "TYPE": "FSA", "PHONE_NUM": "555-0100"}},
    ]}, 36.1, -117.5)
    assert [item["name"] for item in items] == ["Near station", "Far station"]
    assert items[0]["status"] == "Active"
    assert items[0]["phone"] == "555-0100"
