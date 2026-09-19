"""
VayuDrishti — OpenAQ AWS S3 Historical Archive Acquisition Test Suite (Phase 1E-J2A.3)

Validates OpenAQAWSArchiveClient and AWS archive integration path in HistoricalForecastingIngestionPipeline
using controlled offline fixtures/mocks without requiring network access.
"""

import gzip
import io
import csv
import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.ingestion.openaq_aws_archive import OpenAQAWSArchiveClient, S3_BASE_URL
from ml.src.forecasting.historical_ingestion import HistoricalForecastingIngestionPipeline


@pytest.fixture
def aws_client():
    return OpenAQAWSArchiveClient()


@pytest.fixture
def sample_csv_gz_bytes():
    """Generates synthetic in-memory CSV.gz bytes for testing."""
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="w") as gz:
        wrapper = io.TextIOWrapper(gz, encoding="utf-8")
        writer = csv.writer(wrapper)
        writer.writerow(["location_id", "sensors_id", "location", "datetime", "lat", "lon", "parameter", "units", "value"])
        writer.writerow(["8118", "23534", "Anand Vihar-8118", "2025-01-01T01:00:00+05:30", "28.6476", "77.3158", "pm25", "µg/m³", "150.0"])
        writer.writerow(["8118", "23534", "Anand Vihar-8118", "2025-01-01T02:00:00+05:30", "28.6476", "77.3158", "pm10", "µg/m³", "280.0"])
        writer.writerow(["8118", "23534", "Anand Vihar-8118", "2025-01-01T03:00:00+05:30", "28.6476", "77.3158", "so2", "ppb", "12.5"])
        wrapper.flush()
    return out.getvalue()


def make_mock_urlopen(status=200, data=b""):
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.read.return_value = data
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_resp
    return mock_cm


def test_aws_archive_object_key_generation(aws_client):
    """Test 1 & 2: AWS archive object path generation and location/year/month partition parsing."""
    key = aws_client.generate_object_key(8118, "2025-01-15")
    assert key == "records/csv.gz/locationid=8118/year=2025/month=01/location-8118-20250115.csv.gz"

    url = aws_client.generate_object_url(8118, "2025-01-15")
    assert url == f"{S3_BASE_URL}/records/csv.gz/locationid=8118/year=2025/month=01/location-8118-20250115.csv.gz"


def test_single_object_validation_and_schema_detection(aws_client, sample_csv_gz_bytes):
    """Test 3 & 4: CSV.gz reading and schema detection."""
    mock_cm = make_mock_urlopen(200, sample_csv_gz_bytes)

    with patch("urllib.request.urlopen", return_value=mock_cm):
        is_valid, meta = aws_client.validate_single_object(8118, "2025-01-01")
        assert is_valid is True
        assert meta["http_status"] == 200
        assert meta["schema_valid"] is True
        assert "pm25" in meta["parameters_found"]
        assert meta["total_records"] == 3


def test_daily_archive_fetch_and_pollutant_filtering(aws_client, sample_csv_gz_bytes):
    """Test 5 & 6: PM2.5 and PM10 filtering."""
    mock_cm = make_mock_urlopen(200, sample_csv_gz_bytes)

    with patch("urllib.request.urlopen", return_value=mock_cm):
        res = aws_client.fetch_date_range(8118, "2025-01-01", "2025-01-01", pollutants=["pm25", "pm10"])
        assert res["downloaded_files_count"] == 1
        raw_rows = res["raw_rows"]
        assert len(raw_rows) == 2
        params = [r["parameter"] for r in raw_rows]
        assert "pm25" in params
        assert "pm10" in params
        assert "so2" not in params


def test_timestamp_normalization_and_deduplication(tmp_path):
    """Test 7 & 8: Timestamp UTC normalization and duplicate handling."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=tmp_path)
    raw_records = [
        {
            "location_id": "8118",
            "sensors_id": "23534",
            "location": "Anand Vihar",
            "datetime": "2025-01-01T01:00:00+05:30",
            "lat": "28.6476",
            "lon": "77.3158",
            "parameter": "pm25",
            "units": "µg/m³",
            "value": "150.0",
        },
        # Duplicate record
        {
            "location_id": "8118",
            "sensors_id": "23534",
            "location": "Anand Vihar",
            "datetime": "2025-01-01T01:00:00+05:30",
            "lat": "28.6476",
            "lon": "77.3158",
            "parameter": "pm25",
            "units": "µg/m³",
            "value": "150.0",
        },
    ]

    pilot_stations = [
        {"station_id": "ANAND_VIHAR_8118", "location_id": 8118, "latitude": 28.6476, "longitude": 77.3158, "name": "Anand Vihar"}
    ]

    norm, diag = pipeline.normalize_air_quality_with_diagnostics(raw_records, pilot_stations)
    assert len(norm) == 1
    assert diag["duplicates"] == 1
    assert norm[0]["timestamp"] == "2024-12-31T19:30:00Z"
    assert norm[0]["pollutant"] == "PM2.5"
    assert norm[0]["value"] == 150.0


def test_station_sensor_lineage_preservation(tmp_path):
    """Test 9: Station/sensor lineage preservation."""
    pipeline = HistoricalForecastingIngestionPipeline(data_root=tmp_path)
    raw_records = [
        {
            "location_id": "8118",
            "sensors_id": "23534",
            "location": "Anand Vihar",
            "datetime": "2025-01-01T01:00:00+05:30",
            "lat": "28.6476",
            "lon": "77.3158",
            "parameter": "pm25",
            "units": "µg/m³",
            "value": "150.0",
        }
    ]
    pilot_stations = [
        {"station_id": "ANAND_VIHAR_8118", "location_id": 8118, "latitude": 28.6476, "longitude": 77.3158, "name": "Anand Vihar"}
    ]

    norm = pipeline.normalize_air_quality(raw_records, pilot_stations)
    assert len(norm) == 1
    assert norm[0]["location_id"] == 8118
    assert norm[0]["sensor_id"] == 23534
    assert norm[0]["station_id"] == "ANAND_VIHAR_8118"


def test_bounded_date_acquisition_and_manifest_generation(aws_client, sample_csv_gz_bytes):
    """Test 10 & 11: Bounded date acquisition and manifest generation."""
    mock_cm = make_mock_urlopen(200, sample_csv_gz_bytes)

    with patch("urllib.request.urlopen", return_value=mock_cm):
        res = aws_client.fetch_date_range(8118, "2025-01-01", "2025-01-03")
        assert res["attempted_files_count"] == 3
        assert len(res["download_manifests"]) == 3
        m0 = res["download_manifests"][0]
        assert m0["source"] == "openaq_aws"
        assert m0["bucket"] == "openaq-data-archive"
        assert m0["status"] == "SUCCESS"


def test_archive_failure_handling(aws_client):
    """Test 12: Archive HTTP failure handling."""
    with patch("urllib.request.urlopen", side_effect=Exception("HTTP 404 Not Found")):
        is_valid, meta = aws_client.validate_single_object(8118, "2025-01-01")
        assert is_valid is False
        assert meta["schema_valid"] is False
        assert "404" in meta.get("error", "")
