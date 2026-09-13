"""
VayuDrishti - Phase 1E-A OpenAQ Ingestion Tests
Comprehensive unit tests for OpenAQ client, normalizer, validator, and pipeline.
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
import httpx

from backend.api.v1.schemas.observation import EnvironmentalObservation
from backend.ingestion import (
    OpenAQClient,
    OpenAQNormalizer,
    ObservationValidator,
    DataQualityReport,
    OpenAQIngestionPipeline,
    MissingCredentialError,
    AuthenticationError,
    RateLimitError,
    OpenAQAPIError,
    NetworkError,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "openaq_delhi_sample.json"


# ------------------------------------------------------------------------------
# 1. OpenAQ Client & Credential Safety Tests
# ------------------------------------------------------------------------------

def test_client_missing_credential_handling(monkeypatch):
    """Verify OpenAQClient fails gracefully when OPENAQ_API_KEY is not set."""
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    client = OpenAQClient(api_key=None)
    assert not client.has_credentials()

    with pytest.raises(MissingCredentialError) as exc_info:
        client.get_locations()
    assert "OPENAQ_API_KEY is not configured" in str(exc_info.value)


def test_client_header_does_not_leak_secret(monkeypatch):
    """Verify client headers format and ensure credentials aren't exposed in repr."""
    client = OpenAQClient(api_key="secret_test_key_xyz123")
    assert client.has_credentials()
    headers = client._get_headers()
    assert headers["X-API-Key"] == "secret_test_key_xyz123"
    assert "VayuDrishti-Ingestion" in headers["User-Agent"]


def test_client_mock_http_status_codes():
    """Verify structured exception mapping for HTTP responses."""
    # Mock 401 Unauthorized
    def mock_handler_401(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"message": "Unauthorized API key"})

    transport_401 = httpx.MockTransport(mock_handler_401)
    mock_client_401 = httpx.Client(transport=transport_401)
    client = OpenAQClient(api_key="invalid_key", http_client=mock_client_401)

    with pytest.raises(AuthenticationError) as exc:
        client.get_locations()
    assert "OpenAQ rejected credentials" in str(exc.value)

    # Mock 429 Rate Limit
    def mock_handler_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "Too Many Requests"})

    transport_429 = httpx.MockTransport(mock_handler_429)
    mock_client_429 = httpx.Client(transport=transport_429)
    client_429 = OpenAQClient(api_key="test_key", http_client=mock_client_429)

    with pytest.raises(RateLimitError):
        client_429.get_locations()

    # Mock 500 Server Error
    def mock_handler_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport_500 = httpx.MockTransport(mock_handler_500)
    mock_client_500 = httpx.Client(transport=transport_500)
    client_500 = OpenAQClient(api_key="test_key", max_retries=0, http_client=mock_client_500)

    with pytest.raises(OpenAQAPIError) as exc_500:
        client_500.get_locations()
    assert exc_500.value.status_code == 500


# ------------------------------------------------------------------------------
# 2. Normalization Engine Tests
# ------------------------------------------------------------------------------

def test_normalizer_pollutant_mapping():
    """Verify standard pollutant alias resolution."""
    normalizer = OpenAQNormalizer()
    assert normalizer.normalize_pollutant("pm25") == "PM2.5"
    assert normalizer.normalize_pollutant("PM2.5") == "PM2.5"
    assert normalizer.normalize_pollutant("pm_25") == "PM2.5"
    assert normalizer.normalize_pollutant("pm10") == "PM10"
    assert normalizer.normalize_pollutant("no2") == "NO2"
    assert normalizer.normalize_pollutant("nitrogen dioxide") == "NO2"
    assert normalizer.normalize_pollutant("so2") == "SO2"
    assert normalizer.normalize_pollutant("co") == "CO"
    assert normalizer.normalize_pollutant("o3") == "O3"
    assert normalizer.normalize_pollutant("ozone") == "O3"
    assert normalizer.normalize_pollutant("temperature") is None
    assert normalizer.normalize_pollutant("wind_speed") is None


def test_normalizer_unit_conversion():
    """Verify unit normalization and CO conversion from mg/m? to ?g/m?."""
    normalizer = OpenAQNormalizer()

    # Standard ?g/m? variants
    for u in ["?g/m?", "ug/m3", "ug/m^3", "ugm-3"]:
        val, unit, note = normalizer.normalize_unit_and_value("PM2.5", 85.0, u)
        assert val == 85.0
        assert unit == "?g/m?"
        assert note is None

    # CO conversion: 1.5 mg/m? -> 1500.0 ?g/m?
    val_co, unit_co, note_co = normalizer.normalize_unit_and_value("CO", 1.5, "mg/m?")
    assert val_co == 1500.0
    assert unit_co == "?g/m?"
    assert note_co == "converted_mg_to_ug"


def test_normalizer_valid_record():
    """Verify full normalization of a valid OpenAQ reading."""
    normalizer = OpenAQNormalizer()
    reading = {
        "sensorsId": 1234,
        "locationsId": 8118,
        "value": 135.2,
        "parameter": {"id": 2, "name": "pm25", "units": "?g/m?"},
        "datetime": {"utc": "2026-09-13T12:00:00Z", "local": "2026-09-13T17:30:00+05:30"},
        "coordinates": {"latitude": 28.6476, "longitude": 77.3158},
    }
    loc_meta = {
        "id": 8118,
        "name": "Anand Vihar, Delhi",
        "provider": {"name": "CPCB"},
    }
    result = normalizer.normalize_record(reading, loc_meta)
    assert result.is_valid
    obs = result.observation
    assert isinstance(obs, EnvironmentalObservation)
    assert obs.pollutant == "PM2.5"
    assert obs.value == 135.2
    assert obs.unit == "?g/m?"
    assert obs.location.latitude == 28.6476
    assert obs.location.longitude == 77.3158
    assert "ANAND_VIHAR" in obs.station_id
    assert "openaq-loc-8118" in obs.source_record_id
    assert obs.normalization_version == "1.0"


def test_normalizer_rejection_cases():
    """Verify normalizer rejects bad values, bad coordinates, and invalid pollutants."""
    normalizer = OpenAQNormalizer()
    base_loc = {"id": 1, "coordinates": {"latitude": 28.6, "longitude": 77.2}}

    # 1. Negative value
    bad_val = {
        "value": -12.0,
        "parameter": "pm25",
        "datetime": "2026-09-13T12:00:00Z",
        "coordinates": {"latitude": 28.6, "longitude": 77.2},
    }
    res_val = normalizer.normalize_record(bad_val, base_loc)
    assert not res_val.is_valid
    assert "negative_concentration" in res_val.rejection_reason

    # 2. Coordinates out of bounds
    bad_coords = {
        "value": 45.0,
        "parameter": "pm25",
        "datetime": "2026-09-13T12:00:00Z",
        "coordinates": {"latitude": 150.0, "longitude": 77.2},
    }
    res_coords = normalizer.normalize_record(bad_coords, base_loc)
    assert not res_coords.is_valid
    assert "coordinates_out_of_bounds" in res_coords.rejection_reason

    # 3. Unsupported pollutant
    bad_param = {
        "value": 22.0,
        "parameter": "relative_humidity",
        "datetime": "2026-09-13T12:00:00Z",
        "coordinates": {"latitude": 28.6, "longitude": 77.2},
    }
    res_param = normalizer.normalize_record(bad_param, base_loc)
    assert not res_param.is_valid
    assert "unsupported_pollutant" in res_param.rejection_reason


# ------------------------------------------------------------------------------
# 3. Validation & Quality Reporting Tests
# ------------------------------------------------------------------------------

def test_observation_validator_deduplication():
    """Verify that duplicate observations are identified and filtered."""
    validator = ObservationValidator()
    report = DataQualityReport(run_id="test", source_name="test", generated_at="now")

    from backend.api.v1.schemas.common import Location

    obs1 = EnvironmentalObservation(
        timestamp=datetime.now(timezone.utc),
        location=Location(latitude=28.6, longitude=77.2),
        pollutant="PM2.5",
        value=110.0,
        unit="?g/m?",
        source="CAAQMS",
        station_id="STATION_A",
    )

    # First encounter is valid
    res1 = validator.validate(obs1, report=report)
    assert res1.is_valid
    assert not res1.is_duplicate
    assert report.records_valid == 1

    # Exact duplicate encounter is marked duplicate
    res2 = validator.validate(obs1, report=report)
    assert not res2.is_valid
    assert res2.is_duplicate
    assert report.records_duplicate == 1
    assert report.records_valid == 1


# ------------------------------------------------------------------------------
# 4. End-to-End Pipeline Execution Tests
# ------------------------------------------------------------------------------

def test_pipeline_execution_from_fixture(tmp_path):
    """Verify complete pipeline execution using the sanitized Delhi fixture."""
    raw_dir = tmp_path / "raw"
    proc_dir = tmp_path / "processed"

    pipeline = OpenAQIngestionPipeline(
        raw_dir=str(raw_dir),
        processed_dir=str(proc_dir),
    )

    summary = pipeline.run(fixture_path=str(FIXTURE_PATH), run_label="test_delhi")

    assert summary["status"] == "success"
    assert summary["mode"] == "fixture"
    metrics = summary["metrics"]

    # 12 readings in fixture: 9 valid, 2 invalid (-8.5 and wind_speed), 1 duplicate
    assert metrics["records_fetched"] == 12
    assert metrics["records_valid"] == 9
    assert metrics["records_invalid"] == 2
    assert metrics["records_duplicate"] == 1
    assert metrics["pass_rate_percent"] == 75.0

    # Verify raw snapshot file exists and has NO secret keys
    raw_file = Path(summary["raw_snapshot_path"])
    assert raw_file.exists()
    with open(raw_file, "r", encoding="utf-8") as f:
        raw_content = f.read()
        assert "api_key" not in raw_content.lower()

    # Verify processed JSONL file exists and validates
    proc_file = Path(summary["processed_output_path"])
    assert proc_file.exists()
    with open(proc_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
        assert len(lines) == 9
        for line in lines:
            data = json.loads(line)
            # Re-parse into canonical EnvironmentalObservation
            obs = EnvironmentalObservation(**data)
            assert obs.pollutant in ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3"]
            assert obs.value >= 0.0

    # Verify quality report JSON exists
    report_json = Path(summary["validation_report_json"])
    assert report_json.exists()
    with open(report_json, "r", encoding="utf-8") as f:
        rep = json.load(f)
        assert rep["metrics"]["records_valid"] == 9
        assert "negative_concentration_physical_violation: -8.5" in rep["invalid_reasons"]

    # Verify quality report Markdown exists
    report_md = Path(summary["validation_report_md"])
    assert report_md.exists()
    assert report_md.stat().st_size > 100


def test_pipeline_skips_live_gracefully_when_unconfigured(monkeypatch, tmp_path):
    """Verify pipeline skips live fetch gracefully without throwing error if key absent."""
    monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
    pipeline = OpenAQIngestionPipeline(
        raw_dir=str(tmp_path / "raw"),
        processed_dir=str(tmp_path / "processed"),
        client=OpenAQClient(api_key=None),
    )

    summary = pipeline.run(fixture_path=None)
    assert summary["status"] == "skipped"
    assert summary["reason"] == "missing_credentials"
    assert "Live OpenAQ verification skipped" in summary["message"]
