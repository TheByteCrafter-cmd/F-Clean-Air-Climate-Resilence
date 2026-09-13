"""
VayuDrishti - Phase 1E-B Open-Meteo Weather Ingestion Tests
Comprehensive unit tests for Open-Meteo client, normalizer, validator, and pipeline.
"""

import json
import math
import pytest
from datetime import datetime, timezone
from pathlib import Path
import httpx

from backend.api.v1.schemas.weather import WeatherObservation
from backend.ingestion import (
    OpenMeteoClient,
    OpenMeteoNormalizer,
    WeatherValidator,
    WeatherQualityReport,
    OpenMeteoIngestionPipeline,
    RateLimitError,
    OpenAQAPIError,  # OpenMeteoAPIError
    NetworkError,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "open_meteo_delhi_sample.json"


# ------------------------------------------------------------------------------
# 1. Open-Meteo Client & Network Failure Tests
# ------------------------------------------------------------------------------

def test_weather_client_mock_http_status_codes():
    """Verify structured exception mapping for Open-Meteo HTTP responses."""
    # Mock 429 Rate Limit
    def mock_handler_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": True, "reason": "Rate limit exceeded"})

    client_429 = OpenMeteoClient(http_client=httpx.Client(transport=httpx.MockTransport(mock_handler_429)))
    with pytest.raises(RateLimitError):
        client_429.fetch_weather()

    # Mock 500 Server Error
    def mock_handler_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client_500 = OpenMeteoClient(max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(mock_handler_500)))
    with pytest.raises(OpenAQAPIError) as exc_500:
        client_500.fetch_weather()
    assert exc_500.value.status_code == 500


# ------------------------------------------------------------------------------
# 2. Weather Normalization Engine Tests
# ------------------------------------------------------------------------------

def test_wind_cartesian_components_meteorological_convention():
    """Verify u (eastward) and v (northward) computation following meteorological convention.
    
    Wind direction theta is direction FROM which wind blows:
    - 0? (North wind, blowing South): u = 0, v = -speed
    - 90? (East wind, blowing West): u = -speed, v = 0
    - 180? (South wind, blowing North): u = 0, v = +speed
    - 270? (West wind, blowing East): u = +speed, v = 0
    """
    normalizer = OpenMeteoNormalizer()
    speed = 10.0

    u_n, v_n = normalizer.compute_wind_components(speed, 0.0)
    assert round(u_n, 1) == 0.0
    assert round(v_n, 1) == -10.0

    u_e, v_e = normalizer.compute_wind_components(speed, 90.0)
    assert round(u_e, 1) == -10.0
    assert round(v_e, 1) == 0.0

    u_s, v_s = normalizer.compute_wind_components(speed, 180.0)
    assert round(u_s, 1) == 0.0
    assert round(v_s, 1) == 10.0

    u_w, v_w = normalizer.compute_wind_components(speed, 270.0)
    assert round(u_w, 1) == 10.0
    assert round(v_w, 1) == 0.0


def test_wind_speed_unit_conversion():
    """Verify deterministic conversion from km/h to m/s when required."""
    normalizer = OpenMeteoNormalizer()

    # m/s preserved
    assert normalizer.normalize_wind_speed(5.0, "m/s") == 5.0

    # 36.0 km/h -> 10.0 m/s
    assert normalizer.normalize_wind_speed(36.0, "km/h") == 10.0
    # 18.0 km/h -> 5.0 m/s
    assert normalizer.normalize_wind_speed(18.0, "km/h") == 5.0


def test_timestamp_parsing_to_utc():
    """Verify ISO timestamps are converted to timezone-aware UTC datetime."""
    normalizer = OpenMeteoNormalizer()

    # Naive ISO string assumed UTC
    dt1 = normalizer.parse_timestamp("2026-09-13T12:00")
    assert dt1.tzinfo is not None
    assert dt1.hour == 12
    assert dt1.utcoffset().total_seconds() == 0

    # Explicit Z
    dt2 = normalizer.parse_timestamp("2026-09-13T12:00:00Z")
    assert dt2.tzinfo is not None
    assert dt2.hour == 12

    # Invalid timestamp
    assert normalizer.parse_timestamp("invalid-date-string") is None


def test_normalize_valid_step():
    """Verify normalization of a complete valid hourly step."""
    normalizer = OpenMeteoNormalizer()
    step_data = {
        "temperature_2m": 28.5,
        "relative_humidity_2m": 75.0,
        "surface_pressure": 992.4,
        "wind_speed_10m": 3.2,
        "wind_direction_10m": 120.0,
        "precipitation": 0.0,
        "boundary_layer_height": 450.0,
    }
    loc_meta = {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "city": "Delhi NCR Pilot",
    }
    units = {"wind_speed_10m": "m/s"}

    res = normalizer.normalize_hourly_step(
        time_str="2026-09-13T15:00",
        step_data=step_data,
        location_meta=loc_meta,
        units_meta=units,
    )

    assert res.is_valid
    obs = res.observation
    assert isinstance(obs, WeatherObservation)
    assert obs.temperature_c == 28.5
    assert obs.relative_humidity_pct == 75.0
    assert obs.surface_pressure_hpa == 992.4
    assert obs.wind_speed_ms == 3.2
    assert obs.wind_direction_deg == 120.0
    assert obs.boundary_layer_height_m == 450.0
    assert obs.wind_u_ms is not None
    assert obs.wind_v_ms is not None
    assert "weather-om-28.6139-77.2090" in obs.weather_id
    assert obs.source == "Open-Meteo"


def test_missing_values_preserved_not_zeroed():
    """Verify that null boundary layer height is preserved as None and never replaced with 0.0."""
    normalizer = OpenMeteoNormalizer()
    step_data = {
        "temperature_2m": 24.0,
        "relative_humidity_2m": 80.0,
        "surface_pressure": 995.0,
        "wind_speed_10m": 2.0,
        "wind_direction_10m": 90.0,
        "precipitation": 0.0,
        "boundary_layer_height": None,  # Null BLH
    }
    loc_meta = {"latitude": 28.6139, "longitude": 77.2090}

    res = normalizer.normalize_hourly_step(
        time_str="2026-09-13T04:00",
        step_data=step_data,
        location_meta=loc_meta,
    )
    assert res.is_valid
    assert res.observation.boundary_layer_height_m is None


def test_missing_required_field_rejected():
    """Verify that missing required variables (e.g. temperature) cause record rejection."""
    normalizer = OpenMeteoNormalizer()
    step_data = {
        "temperature_2m": None,  # Missing required field
        "relative_humidity_2m": 80.0,
        "surface_pressure": 995.0,
        "wind_speed_10m": 2.0,
        "wind_direction_10m": 90.0,
    }
    loc_meta = {"latitude": 28.6139, "longitude": 77.2090}

    res = normalizer.normalize_hourly_step(
        time_str="2026-09-13T04:00",
        step_data=step_data,
        location_meta=loc_meta,
    )
    assert not res.is_valid
    assert "missing_required_variable: 'temperature_2m'" in res.rejection_reason


# ------------------------------------------------------------------------------
# 3. Weather Validation & Quality Engine Tests
# ------------------------------------------------------------------------------

def test_weather_validator_physical_boundaries():
    """Verify physical boundary audits on WeatherObservation."""
    validator = WeatherValidator()
    from backend.api.v1.schemas.common import Location

    base_loc = Location(latitude=28.6139, longitude=77.2090)
    now = datetime.now(timezone.utc)

    # 1. Negative humidity
    obs_bad_rh = WeatherObservation(
        timestamp=now,
        location=base_loc,
        temperature_c=25.0,
        relative_humidity_pct=0.0,  # Valid boundary
        surface_pressure_hpa=1000.0,
        wind_speed_ms=2.0,
        wind_direction_deg=90.0,
    )
    assert validator.validate(obs_bad_rh).is_valid

    # Pydantic schema validation rejects negative humidity (<0)
    with pytest.raises(Exception):
        WeatherObservation(
            timestamp=now,
            location=base_loc,
            temperature_c=25.0,
            relative_humidity_pct=-5.0,
            surface_pressure_hpa=1000.0,
            wind_speed_ms=2.0,
            wind_direction_deg=90.0,
        )

    # 2. Extreme pressure (< 800 or > 1100 hPa)
    with pytest.raises(Exception):
        WeatherObservation(
            timestamp=now,
            location=base_loc,
            temperature_c=25.0,
            relative_humidity_pct=50.0,
            surface_pressure_hpa=1450.0,
            wind_speed_ms=2.0,
            wind_direction_deg=90.0,
        )


def test_weather_validator_deduplication():
    """Verify duplicate hourly steps are detected and excluded."""
    validator = WeatherValidator()
    report = WeatherQualityReport(run_id="test", source_name="test", generated_at="now")
    from backend.api.v1.schemas.common import Location

    obs1 = WeatherObservation(
        timestamp=datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc),
        location=Location(latitude=28.6139, longitude=77.2090),
        temperature_c=30.0,
        relative_humidity_pct=60.0,
        surface_pressure_hpa=990.0,
        wind_speed_ms=3.0,
        wind_direction_deg=180.0,
    )

    # First encounter
    res1 = validator.validate(obs1, report=report)
    assert res1.is_valid
    assert not res1.is_duplicate
    assert report.records_valid == 1

    # Second encounter (exact duplicate)
    res2 = validator.validate(obs1, report=report)
    assert not res2.is_valid
    assert res2.is_duplicate
    assert report.records_duplicate == 1
    assert report.records_valid == 1


# ------------------------------------------------------------------------------
# 4. End-to-End Pipeline Execution Tests
# ------------------------------------------------------------------------------

def test_weather_pipeline_execution_from_fixture(tmp_path):
    """Verify full execution of OpenMeteoIngestionPipeline using sanitized fixture."""
    raw_dir = tmp_path / "raw"
    proc_dir = tmp_path / "processed"

    pipeline = OpenMeteoIngestionPipeline(
        raw_dir=str(raw_dir),
        processed_dir=str(proc_dir),
    )

    summary = pipeline.run(fixture_path=str(FIXTURE_PATH), run_label="test_delhi")

    assert summary["status"] == "success"
    assert summary["mode"] == "fixture"
    metrics = summary["metrics"]

    # 27 steps total in fixture: 24 valid diurnal, 2 physical violations (rh & pressure), 1 duplicate
    assert metrics["records_fetched"] == 27
    assert metrics["records_valid"] == 24
    assert metrics["records_invalid"] == 2
    assert metrics["records_duplicate"] == 1
    assert metrics["pass_rate_percent"] == 88.89

    # Verify raw snapshot file exists
    raw_file = Path(summary["raw_snapshot_path"])
    assert raw_file.exists()

    # Verify processed JSONL file exists and validates
    proc_file = Path(summary["processed_output_path"])
    assert proc_file.exists()
    with open(proc_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == 24
        # Verify chronological order
        prev_dt = None
        for line in lines:
            data = json.loads(line)
            obs = WeatherObservation(**data)
            if prev_dt:
                assert obs.timestamp >= prev_dt
            prev_dt = obs.timestamp
            assert obs.source == "Open-Meteo"

    # Verify quality report JSON & Markdown exist
    report_json = Path(summary["validation_report_json"])
    assert report_json.exists()
    with open(report_json, "r", encoding="utf-8") as f:
        rep = json.load(f)
        assert rep["metrics"]["records_valid"] == 24
        assert rep["physical_summary"]["boundary_layer_height_range_m"][0] >= 0

    report_md = Path(summary["validation_report_md"])
    assert report_md.exists()
    assert report_md.stat().st_size > 100
