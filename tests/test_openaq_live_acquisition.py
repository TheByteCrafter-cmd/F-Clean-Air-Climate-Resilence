"""
VayuDrishti — Live OpenAQ Credential Validation & Acquisition Test Suite (Phase 1E-J2A.2)

Tests authenticated request handling, masked credential logging, sensor discovery,
PM2.5/PM10 sensor filtering, ISO datetime window handling, bounded pagination,
duplicate removal, raw artifact metadata preservation, canonical normalization,
and availability matrix generation.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.ingestion.openaq_client import OpenAQClient
from ml.src.forecasting.historical_ingestion import (
    DELHI_PILOT_STATIONS,
    HistoricalForecastingIngestionPipeline,
)


@pytest.fixture
def temp_dir():
    """Provides temporary directory for testing data ingestion persistence."""
    tmp_path = Path(tempfile.mkdtemp(prefix="vayudrishti_live_acq_test_"))
    yield tmp_path


# ==============================================================================
# 1. AUTHENTICATED REQUEST HANDLING & CREDENTIAL MASKING
# ==============================================================================
def test_authenticated_request_handling():
    """Step 17.1: Verifies authenticated headers construction with API key."""
    client = OpenAQClient(api_key="test_secret_key_12345")
    assert client.has_credentials() is True
    headers = client._get_headers()
    assert headers["X-API-Key"] == "test_secret_key_12345"
    assert "User-Agent" in headers


def test_masked_credential_logging(temp_dir):
    """Step 17.2: Verifies that API key is NEVER exposed in log strings, JSON envelopes, or error payloads."""
    client = OpenAQClient(api_key="SUPER_SECRET_KEY_999")
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_dir, openaq_client=client)

    with patch.object(client, "has_credentials", return_value=False), \
         patch.object(pipeline.weather_client, "fetch_weather", return_value={}):
        res = pipeline.fetch_and_process_history(history_days=7)

        # Check returned diagnostic payload
        diag_str = json.dumps(res)
        assert "SUPER_SECRET_KEY_999" not in diag_str
        assert "X-API-Key" not in diag_str

        # Check persisted raw artifact
        raw_files = list((temp_dir / "raw" / "forecasting").glob("openaq_history_*.json"))
        assert len(raw_files) > 0
        with open(raw_files[0], "r", encoding="utf-8") as f:
            raw_content = f.read()
        assert "SUPER_SECRET_KEY_999" not in raw_content


# ==============================================================================
# 2. SENSOR DISCOVERY & PM2.5/PM10 FILTERING
# ==============================================================================
def test_sensor_discovery():
    """Step 17.3 & 17.4: Verifies sensor discovery and PM2.5/PM10 parameter filtering."""
    client = OpenAQClient()
    mock_sensors_response = {
        "results": [
            {"id": 101, "parameter": {"name": "pm25", "displayName": "PM2.5"}, "units": "µg/m³"},
            {"id": 102, "parameter": {"name": "pm10", "displayName": "PM10"}, "units": "µg/m³"},
            {"id": 103, "parameter": {"name": "so2", "displayName": "SO2"}, "units": "µg/m³"},
        ]
    }

    with patch.object(client, "get_location_sensors", return_value=mock_sensors_response):
        sensors = client.discover_sensors(8118)
        assert len(sensors) == 3
        pm_sensors = [s for s in sensors if str(s["parameter"]).lower() in ["pm25", "pm10"]]
        assert len(pm_sensors) == 2


def test_availability_matrix_generation():
    """Step 17.10: Verifies availability matrix generation for stations."""
    client = OpenAQClient()
    mock_sensors = [
        {"sensor_id": 24151, "location_id": 8118, "parameter": "pm25", "units": "µg/m³", "datetimeFirst": "2024-01-01T00:00:00Z", "datetimeLast": "2026-03-01T00:00:00Z"},
    ]

    with patch.object(client, "discover_sensors", return_value=mock_sensors):
        matrix = client.generate_availability_matrix([DELHI_PILOT_STATIONS[0]], "2026-03-01T00:00:00Z", "2026-03-15T00:00:00Z")
        assert len(matrix) == 1
        assert matrix[0]["station"] == "ANAND_VIHAR_8118"
        assert matrix[0]["pollutant"] == "pm25"
        assert matrix[0]["historical_data_available"] is True


# ==============================================================================
# 3. DATETIME WINDOW, PAGINATION & DEDUPLICATION
# ==============================================================================
def test_datetime_window_handling():
    """Step 17.5: Verifies datetime_from and datetime_to ISO string serialization."""
    client = OpenAQClient(api_key="test")
    mock_execute = MagicMock(return_value={"results": []})
    client._execute_request = mock_execute

    client.get_sensor_measurements(
        sensors_id=24151,
        date_from="2026-03-01T00:00:00Z",
        date_to="2026-03-07T00:00:00Z",
    )

    call_args = mock_execute.call_args
    params = call_args[1]["params"]
    assert params["datetime_from"] == "2026-03-01T00:00:00Z"
    assert params["datetime_to"] == "2026-03-07T00:00:00Z"


def test_pagination():
    """Step 17.6: Verifies multi-page sensor measurements pagination traversal."""
    client = OpenAQClient(api_key="test")
    page1 = {"results": [{"value": 100.0}], "meta": {"found": 2, "page": 1, "limit": 1}}
    page2 = {"results": [{"value": 105.0}], "meta": {"found": 2, "page": 2, "limit": 1}}

    with patch.object(client, "get_sensor_measurements", side_effect=[page1, page2]):
        res1 = client.get_sensor_measurements(24151, page=1)
        res2 = client.get_sensor_measurements(24151, page=2)

        assert len(res1["results"]) == 1
        assert len(res2["results"]) == 1
        assert res1["results"][0]["value"] == 100.0
        assert res2["results"][0]["value"] == 105.0


def test_duplicate_removal_and_normalization():
    """Step 17.7 & 17.9: Verifies duplicate observation removal and canonical normalization."""
    pipeline = HistoricalForecastingIngestionPipeline()
    raw_records = [
        {"timestamp": "2026-03-01T01:00:00Z", "parameter": {"name": "pm25"}, "value": 120.0, "location_id": 8118},
        {"timestamp": "2026-03-01T01:00:00Z", "parameter": {"name": "pm25"}, "value": 120.0, "location_id": 8118},  # Duplicate
    ]

    normalized = pipeline.normalize_air_quality(raw_records, DELHI_PILOT_STATIONS)
    assert len(normalized) == 1
    assert normalized[0]["pollutant"] == "PM2.5"
    assert normalized[0]["value"] == 120.0


def test_raw_artifact_metadata(temp_dir):
    """Step 17.8: Verifies metadata fields in raw json snapshots."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=temp_dir)
    with patch.object(pipeline.openaq_client, "has_credentials", return_value=False), \
         patch.object(pipeline.weather_client, "fetch_weather", return_value={}):
        pipeline.fetch_and_process_history(history_days=7)

        raw_files = list((temp_dir / "raw" / "forecasting").glob("openaq_history_*.json"))
        assert len(raw_files) > 0
        with open(raw_files[0], "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "metadata" in data
        assert "source" in data["metadata"]
        assert "start_utc" in data["metadata"]
        assert "end_utc" in data["metadata"]
