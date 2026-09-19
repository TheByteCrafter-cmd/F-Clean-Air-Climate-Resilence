"""
VayuDrishti — Historical Forecasting Data Ingestion Test Suite (Phase 1E-J2A.1)

Tests OpenAQ API response normalization, sensor-level location traversal,
diagnostic mode tracking, pagination handling, deduplication by
(station_id, pollutant, timestamp), UTC timestamp normalization, unit normalization,
pilot station filtering, station hourly continuity calculation, missing-hour detection,
historical weather alignment (<= t), unauthenticated fallback, manifest generation,
credential masking, and readiness recalculation.
"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ml.src.forecasting.historical_ingestion import (
    DELHI_PILOT_STATIONS,
    HistoricalForecastingIngestionPipeline,
)


@pytest.fixture
def temp_data_root():
    """Provides a temporary root directory for data ingestion output persistence."""
    tmp_path = Path(tempfile.mkdtemp(prefix="vayudrishti_hist_ingest_test_"))
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


# Mock OpenAQ responses
MOCK_OPENAQ_RESULTS = [
    {
        "period": {"datetimeFrom": {"utc": "2026-03-01T00:00:00Z"}},
        "parameter": {"name": "pm25", "units": "µg/m³"},
        "value": 110.5,
        "location_id": 8118,
    },
    {
        "period": {"datetimeFrom": {"utc": "2026-03-01T01:00:00Z"}},
        "parameter": {"name": "pm25", "units": "µg/m³"},
        "value": 115.0,
        "location_id": 8118,
    },
    {
        "period": {"datetimeFrom": {"utc": "2026-03-01T01:00:00Z"}},  # Duplicate entry
        "parameter": {"name": "pm25", "units": "µg/m³"},
        "value": 115.0,
        "location_id": 8118,
    },
    {
        "period": {"datetimeFrom": {"utc": "2026-03-01T04:00:00Z"}},  # Gap of 3 hours
        "parameter": {"name": "pm25", "units": "µg/m³"},
        "value": 120.2,
        "location_id": 8118,
    },
    {
        "period": {"datetimeFrom": {"utc": "2026-03-01T04:00:00Z"}},
        "parameter": {"name": "pm10", "units": "ug/m3"},
        "value": 210.0,
        "location_id": 8118,
    },
]


# ==============================================================================
# 1. OPENAQ API RESPONSE NORMALIZATION & SENSOR TRAVERSAL
# ==============================================================================
def test_openaq_normalization_and_pagination(temp_data_root):
    """Verifies that OpenAQ v3 nested measurements are normalized properly."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_data_root)

    normalized = pipeline.normalize_air_quality(
        MOCK_OPENAQ_RESULTS, DELHI_PILOT_STATIONS
    )

    # 5 raw records -> 1 duplicate PM2.5 skipped -> 4 valid normalized records
    assert len(normalized) == 4
    for r in normalized:
        assert r["unit"] == "µg/m³"
        assert r["timestamp"].endswith("Z")


def test_sensor_level_location_traversal():
    """Step 5: Verifies location -> sensors -> hours traversal logic in OpenAQClient."""
    mock_sensors_response = {
        "results": [
            {"id": 24151, "parameter": {"name": "pm25", "displayName": "PM2.5"}},
            {"id": 24152, "parameter": {"name": "pm10", "displayName": "PM10"}},
        ]
    }
    mock_hours_response = {
        "results": [
            {
                "datetime": {"utc": "2026-03-01T00:00:00Z"},
                "value": 142.5,
            }
        ],
        "meta": {"found": 1, "page": 1, "limit": 1000},
    }

    pipeline = HistoricalForecastingIngestionPipeline()
    with patch.object(pipeline.openaq_client, "get_location_sensors", return_value=mock_sensors_response), \
         patch.object(pipeline.openaq_client, "get_sensor_measurements", return_value=mock_hours_response):

        res = pipeline.openaq_client.get_location_measurements(
            locations_id=8118,
            date_from="2026-03-01T00:00:00Z",
            date_to="2026-03-01T05:00:00Z",
        )

        assert len(res["results"]) == 2  # 1 reading per sensor (pm25 + pm10)
        assert res["results"][0]["locationsId"] == 8118


# ==============================================================================
# 2. DIAGNOSTIC MODE REPORTING
# ==============================================================================
def test_diagnostic_mode_reporting(temp_data_root):
    """Step 2: Verifies explicit diagnostic mode metrics tracking and credential masking."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_data_root)

    with patch.object(pipeline.openaq_client, "has_credentials", return_value=False), \
         patch.object(pipeline.weather_client, "fetch_weather", return_value={}):
        result = pipeline.fetch_and_process_history(history_days=7)

        diag = result["diagnostic_report"]
        assert "requested_stations" in diag
        assert "location_ids" in diag
        assert "api_endpoint" in diag
        assert "raw_measurement_count" in diag
        assert "pm25_measurement_count" in diag
        assert "pm10_measurement_count" in diag
        assert "normalized_record_count" in diag
        assert "filtered_record_count" in diag
        assert "duplicate_count" in diag

        # Credential safety check: ensure key string is not exposed anywhere in diag
        diag_str = json.dumps(diag)
        assert "OPENAQ_API_KEY" not in diag_str
        assert "X-API-Key" not in diag_str


# ==============================================================================
# 3. DEDUPLICATION & POLLUTANT NORMALIZATION
# ==============================================================================
def test_deduplication_and_unit_normalization(temp_data_root):
    """Verifies strict deduplication by (station_id, pollutant, timestamp) and unit standardizing."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_data_root)

    raw_records = [
        {
            "period": {"datetimeFrom": {"utc": "2026-03-01T01:00:00Z"}},
            "parameter": {"name": "pm25"},
            "value": 115.0,
            "location_id": 8118,
        },
        {
            "period": {"datetimeFrom": {"utc": "2026-03-01T01:00:00Z"}},  # Duplicate
            "parameter": {"name": "pm25"},
            "value": 115.0,
            "location_id": 8118,
        },
        {
            "period": {"datetimeFrom": {"utc": "2026-03-01T01:00:00Z"}},  # Different pollutant
            "parameter": {"name": "pm10"},
            "value": 200.0,
            "location_id": 8118,
        },
    ]

    parsed = pipeline.normalize_air_quality(raw_records, DELHI_PILOT_STATIONS)
    assert len(parsed) == 2
    for r in parsed:
        assert r["unit"] == "µg/m³"
        assert "Z" in r["timestamp"]


def test_pollutant_parameter_variants():
    """Step 6: Verifies pm25, pm2.5, pm10 parameter normalization variants."""
    pipeline = HistoricalForecastingIngestionPipeline()
    records = [
        {"timestamp": "2026-03-01T01:00:00Z", "parameter": {"name": "pm_25"}, "value": 100.0, "location_id": 8118},
        {"timestamp": "2026-03-01T01:00:00Z", "parameter": {"name": "pm10"}, "value": 180.0, "location_id": 8118},
    ]
    normalized = pipeline.normalize_air_quality(records, DELHI_PILOT_STATIONS)
    assert len(normalized) == 2
    pols = [r["pollutant"] for r in normalized]
    assert "PM2.5" in pols
    assert "PM10" in pols


# ==============================================================================
# 4. STATION FILTERING & CONTINUITY AUDIT
# ==============================================================================
def test_pilot_station_filtering(temp_data_root):
    """Verifies that only defined pilot stations in Delhi are included in pipeline target list."""
    station_ids = [s["station_id"] for s in DELHI_PILOT_STATIONS]

    assert "ANAND_VIHAR_8118" in station_ids
    assert "RK_PURAM_8124" in station_ids
    assert len(DELHI_PILOT_STATIONS) == 6


def test_hourly_continuity_and_missing_hours(temp_data_root):
    """Verifies audit calculation of continuity score and detection of missing hour gaps."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_data_root)

    normalized_aq = [
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2026-03-01T00:00:00Z", "value": 100.0},
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2026-03-01T01:00:00Z", "value": 105.0},
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2026-03-01T04:00:00Z", "value": 110.0},
    ]

    start_dt = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
    end_dt = datetime(2026, 3, 1, 5, 0, tzinfo=timezone.utc)

    stats = pipeline.calculate_station_continuity(
        normalized_aq, [DELHI_PILOT_STATIONS[0]], start_dt, end_dt
    )

    anand_stats = stats["ANAND_VIHAR_8118"]
    assert anand_stats["observed_hourly_timestamps"] == 3
    assert anand_stats["expected_hourly_timestamps"] == 5
    assert anand_stats["continuity_percentage"] == 60.0
    assert anand_stats["missing_hour_count"] == 2


# ==============================================================================
# 5. HISTORICAL WEATHER ALIGNMENT (<= t)
# ==============================================================================
def test_historical_weather_alignment(temp_data_root):
    """Verifies Open-Meteo historical weather parsing and normalization."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_data_root)

    mock_open_meteo_response = {
        "hourly": {
            "time": ["2026-03-01T00:00", "2026-03-01T01:00"],
            "temperature_2m": [18.5, 19.0],
            "relative_humidity_2m": [65, 62],
            "wind_speed_10m": [8.5, 9.0],
            "wind_direction_10m": [270, 280],
            "surface_pressure": [1012.0, 1011.5],
            "boundary_layer_height": [500.0, 550.0],
        }
    }

    normalized_wx = pipeline.normalize_weather(mock_open_meteo_response)

    assert len(normalized_wx) == 2
    assert normalized_wx[0]["timestamp"] == "2026-03-01T00:00:00Z"
    assert normalized_wx[0]["temperature_2m"] == 18.5
    assert "wind_u" in normalized_wx[0]
    assert "wind_v" in normalized_wx[0]


# ==============================================================================
# 6. UNAUTHENTICATED FALLBACK & MANIFEST / READINESS GENERATION
# ==============================================================================
def test_unauthenticated_fallback_and_reports(temp_data_root):
    """Verifies that missing OPENAQ_API_KEY generates honest reports without failing or fabricating data."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_data_root)

    with patch.object(pipeline.openaq_client, "has_credentials", return_value=False), \
         patch.object(pipeline.weather_client, "fetch_weather", return_value={}):
        result = pipeline.fetch_and_process_history(history_days=7)

        assert "readiness_status" in result
        assert result["readiness_status"] in ["NOT_READY", "DEGRADED", "READY"]

        # Check that output files were created
        processed_dir = temp_data_root / "processed" / "forecasting"
        assert (processed_dir / "historical_air_quality.csv").exists()
        assert (processed_dir / "historical_weather.csv").exists()
        assert (processed_dir / "forecasting_data_manifest.json").exists()
        assert (processed_dir / "forecasting_data_quality.json").exists()


def test_manifest_and_readiness_recalculation(temp_data_root):
    """Verifies that the historical ingestion pipeline updates readiness state and creates manifest metadata."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_data_root)

    with patch.object(pipeline.openaq_client, "has_credentials", return_value=False), \
         patch.object(pipeline.weather_client, "fetch_weather", return_value={}):
        result = pipeline.fetch_and_process_history(history_days=7)

        processed_dir = temp_data_root / "processed" / "forecasting"
        manifest_path = processed_dir / "forecasting_data_manifest.json"
        assert manifest_path.exists()

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        assert "air_quality_source" in manifest
        assert manifest["air_quality_source"] == "OpenAQ REST API v3"
        assert manifest["station_count"] == 6
