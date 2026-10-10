from backend.landscape_risk import _score, _slope_degrees, _within_california


def test_screening_combines_weather_terrain_vegetation_and_alert_without_claiming_probability():
    weather = {
        "relative_humidity_2m": 18,
        "precipitation_7d_mm": 0.5,
        "wind_gusts_10m": 40,
        "temperature_2m": 32,
    }
    result = _score(weather, 24, ["forest"], True)
    assert result["index"] == 91
    assert result["coverage_percent"] == 100
    assert {factor["name"] for factor in result["factors"]} == {
        "Relative humidity", "7-day precipitation", "Wind", "Air temperature",
        "Terrain slope", "Mapped vegetation", "Official fire-weather alert",
    }
    assert "probability" not in result


def test_missing_factors_reduce_coverage_not_get_filled_with_assumptions():
    result = _score(None, None, None, None)
    assert result["index"] is None
    assert result["coverage_percent"] == 0
    assert all(not factor["available"] and factor["points"] is None for factor in result["factors"])


def test_slope_from_flat_dem_is_zero_and_tiger_state_fields_identify_california():
    assert _slope_degrees([500] * 9) == 0
    assert _within_california({"STATE": "06"})
    assert _within_california({"STUSAB": "CA"})
    assert not _within_california({"STATE": "32", "NAME": "Nevada"})
