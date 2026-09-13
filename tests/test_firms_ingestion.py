"""
VayuDrishti - Phase 1E-C NASA FIRMS Thermal Anomaly Ingestion Tests
Comprehensive unit tests for FIRMS client, normalizer, validator, and pipeline.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
import httpx

from backend.api.v1.schemas.satellite import FireSignal, SatelliteSignal
from backend.ingestion import (
    DELHI_NCR_BBOX,
    FIRMSClient,
    FIRMSNormalizer,
    FIRMSValidator,
    FIRMSQualityReport,
    FIRMSIngestionPipeline,
    FIRMSAPIError,
    FIRMSParsingError,
    RateLimitError,
    NetworkError,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "firms_delhi_sample.csv"


# ------------------------------------------------------------------------------
# 1. FIRMS Client & HTTP Error Handling Tests
# ------------------------------------------------------------------------------

def test_firms_client_bounded_http_error_handling():
    """Verify structured exception mapping for NASA FIRMS HTTP responses."""
    # Mock 429 Rate Limit
    def mock_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Rate limit exceeded")

    client_429 = FIRMSClient(http_client=httpx.Client(transport=httpx.MockTransport(mock_429)))
    with pytest.raises(RateLimitError):
        client_429.fetch_regional_feed()

    # Mock 401/403 Authentication Error
    def mock_401(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="Unauthorized / MAP_KEY invalid")

    client_401 = FIRMSClient(http_client=httpx.Client(transport=httpx.MockTransport(mock_401)))
    with pytest.raises(FIRMSAPIError) as exc_401:
        client_401.fetch_regional_feed()
    assert exc_401.value.status_code == 401

    # Mock 500 Server Error
    def mock_500(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    client_500 = FIRMSClient(max_retries=0, http_client=httpx.Client(transport=httpx.MockTransport(mock_500)))
    with pytest.raises(FIRMSAPIError) as exc_500:
        client_500.fetch_regional_feed()
    assert exc_500.value.status_code == 500


def test_firms_client_csv_parsing():
    """Verify parsing of raw CSV text into row dictionaries."""
    sample_csv = (
        "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,confidence,version,bright_ti5,frp,daynight\n"
        "28.7124,77.1045,342.5,0.42,0.38,2026-09-12,0814,N,nominal,2.0NRT,298.2,14.8,D\n"
    )
    rows = FIRMSClient.parse_csv(sample_csv)
    assert len(rows) == 1
    assert rows[0]["latitude"] == "28.7124"
    assert rows[0]["longitude"] == "77.1045"
    assert rows[0]["satellite"] == "N"
    assert rows[0]["confidence"] == "nominal"

    # Empty parsing test
    assert FIRMSClient.parse_csv("") == []
    assert FIRMSClient.parse_csv("   \n  ") == []


# ------------------------------------------------------------------------------
# 2. FIRMS Normalization Engine Tests
# ------------------------------------------------------------------------------

def test_firms_normalizer_field_mapping():
    """Verify raw field mapping to canonical FireSignal schema."""
    normalizer = FIRMSNormalizer()
    row = {
        "latitude": "28.7124",
        "longitude": "77.1045",
        "bright_ti4": "342.50",
        "scan": "0.42",
        "track": "0.38",
        "acq_date": "2026-09-12",
        "acq_time": "0814",
        "satellite": "N",
        "confidence": "nominal",
        "version": "2.0NRT",
        "bright_ti5": "298.20",
        "frp": "14.80",
        "daynight": "D",
    }
    result = normalizer.normalize_row(row)
    assert result.is_valid is True
    signal = result.signal
    assert signal is not None
    assert isinstance(signal, FireSignal)
    assert isinstance(signal, SatelliteSignal)  # Inheritance contract check

    assert signal.latitude == 28.7124
    assert signal.longitude == 77.1045
    assert signal.satellite == "Suomi-NPP"
    assert signal.instrument == "VIIRS"
    assert signal.signal_type == "THERMAL_FIRE_PIXEL"
    assert signal.unit == "MW"
    assert signal.value == 14.80
    assert signal.frp_mw == 14.80
    assert signal.bright_ti4_k == 342.50
    assert signal.bright_ti5_k == 298.20
    assert signal.daynight == "D"
    assert signal.scan == 0.42
    assert signal.track == 0.38
    assert signal.confidence == "nominal"
    assert signal.raw_confidence == "nominal"
    assert signal.quality_indicator == "NOMINAL"
    assert signal.geometry["coordinates"] == [77.1045, 28.7124]


def test_firms_normalizer_timestamp_construction():
    """Verify UTC timestamp normalization from acq_date and acq_time."""
    normalizer = FIRMSNormalizer()

    # Standard 4-digit HHMM
    row1 = {
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "2014",
    }
    res1 = normalizer.normalize_row(row1)
    assert res1.is_valid is True
    assert res1.signal.acquisition_time == datetime(2026, 9, 12, 20, 14, 0, tzinfo=timezone.utc)
    assert res1.signal.acquisition_time.tzinfo == timezone.utc

    # 3-digit morning time (e.g. 603 -> 06:03 UTC)
    row2 = {
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "603",
    }
    res2 = normalizer.normalize_row(row2)
    assert res2.is_valid is True
    assert res2.signal.acquisition_time == datetime(2026, 9, 12, 6, 3, 0, tzinfo=timezone.utc)


def test_firms_normalizer_confidence_preservation():
    """Verify categorical confidence is preserved without fake numeric probability."""
    normalizer = FIRMSNormalizer()

    # Categorical VIIRS Nominal
    res_nom = normalizer.normalize_row({
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "1200",
        "confidence": "nominal",
    })
    assert res_nom.signal.confidence == "nominal"
    assert res_nom.signal.quality_indicator == "NOMINAL"

    # Categorical VIIRS High
    res_hi = normalizer.normalize_row({
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "1200",
        "confidence": "high",
    })
    assert res_hi.signal.confidence == "high"
    assert res_hi.signal.quality_indicator == "HIGH"

    # Categorical VIIRS Low
    res_lo = normalizer.normalize_row({
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "1200",
        "confidence": "low",
    })
    assert res_lo.signal.confidence == "low"
    assert res_lo.signal.quality_indicator == "LOW"

    # MODIS numeric 85%
    res_modis = normalizer.normalize_row({
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "1200",
        "confidence": "85",
    })
    assert res_modis.signal.raw_confidence == "85"
    assert res_modis.signal.quality_indicator == "HIGH"


def test_firms_normalizer_frp_handling():
    """Verify Fire Radiative Power (MW) handling and scientific isolation from PM2.5."""
    normalizer = FIRMSNormalizer()

    # Valid positive FRP
    res = normalizer.normalize_row({
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "1200",
        "frp": "25.4",
    })
    assert res.is_valid is True
    assert res.signal.frp_mw == 25.4
    assert res.signal.value == 25.4
    assert res.signal.unit == "MW"
    # Ensure no direct PM2.5 field or attribution is present in the signal schema
    assert not hasattr(res.signal, "pm25_ugm3")
    assert not hasattr(res.signal, "exposure_level")

    # Negative FRP rejection
    res_neg = normalizer.normalize_row({
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "1200",
        "frp": "-4.5",
    })
    assert res_neg.is_valid is False
    assert "Negative FRP" in res_neg.rejection_reason


def test_firms_normalizer_rejection_cases():
    """Verify rejection of malformed records."""
    normalizer = FIRMSNormalizer()

    # Missing coordinates
    assert normalizer.normalize_row({}).is_valid is False
    assert normalizer.normalize_row({"latitude": "", "longitude": "77.2"}).is_valid is False

    # Out of range coordinates
    res_coord = normalizer.normalize_row({
        "latitude": "95.5", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "1200",
    })
    assert res_coord.is_valid is False
    assert "out of bounds" in res_coord.rejection_reason

    # Invalid acquisition time
    res_time = normalizer.normalize_row({
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "2599",
    })
    assert res_time.is_valid is False
    assert "Out-of-range" in res_time.rejection_reason

    # Unphysical brightness temperature
    res_bt = normalizer.normalize_row({
        "latitude": "28.6", "longitude": "77.2",
        "acq_date": "2026-09-12", "acq_time": "1200",
        "bright_ti4": "850.0",
    })
    assert res_bt.is_valid is False
    assert "Brightness temperature" in res_bt.rejection_reason


# ------------------------------------------------------------------------------
# 3. FIRMS Validator & Quality Report Tests
# ------------------------------------------------------------------------------

def test_firms_validator_spatial_filtering():
    """Verify spatial bounding box filtering."""
    normalizer = FIRMSNormalizer()
    validator = FIRMSValidator()

    # In Delhi NCR
    sig_delhi = normalizer.normalize_row({
        "latitude": "28.6139", "longitude": "77.2090",
        "acq_date": "2026-09-12", "acq_time": "1200",
    }).signal

    # Far away in Thailand/Mekong
    sig_distant = normalizer.normalize_row({
        "latitude": "14.1296", "longitude": "100.4916",
        "acq_date": "2026-09-12", "acq_time": "1200",
    }).signal

    retained, report = validator.validate_dataset(
        [sig_delhi, sig_distant], bbox=DELHI_NCR_BBOX
    )
    assert len(retained) == 1
    assert retained[0].latitude == 28.6139
    assert report.rows_retained == 1
    assert report.out_of_bounds_count == 1


def test_firms_validator_deduplication():
    """Verify deterministic deduplication using signal_id."""
    normalizer = FIRMSNormalizer()
    validator = FIRMSValidator()

    row = {
        "latitude": "28.7124", "longitude": "77.1045",
        "acq_date": "2026-09-12", "acq_time": "0814",
        "satellite": "N",
    }
    sig1 = normalizer.normalize_row(row).signal
    sig2 = normalizer.normalize_row(row).signal  # Identical

    assert sig1.signal_id == sig2.signal_id

    retained, report = validator.validate_dataset([sig1, sig2], bbox=None)
    assert len(retained) == 1
    assert report.duplicate_count == 1
    assert report.rows_retained == 1


def test_firms_quality_report_serialization():
    """Verify JSON and Markdown rendering of FIRMSQualityReport."""
    normalizer = FIRMSNormalizer()
    validator = FIRMSValidator()

    sig = normalizer.normalize_row({
        "latitude": "28.7124", "longitude": "77.1045",
        "acq_date": "2026-09-12", "acq_time": "0814",
        "satellite": "N", "frp": "15.0", "confidence": "nominal", "daynight": "D",
    }).signal

    _, report = validator.validate_dataset([sig], bbox=DELHI_NCR_BBOX)
    report_dict = report.model_dump()
    assert report_dict["source"] == "NASA_FIRMS"
    assert report_dict["rows_retained"] == 1
    assert report_dict["frp_summary"]["mean_mw"] == 15.0

    md = report.to_markdown()
    assert "# NASA FIRMS Thermal Anomaly Ingestion Quality Report" in md
    assert "Suomi-NPP" in md
    assert "15.00 MW" in md


# ------------------------------------------------------------------------------
# 4. Pipeline Execution from Fixture
# ------------------------------------------------------------------------------

def test_firms_pipeline_execution_from_fixture(tmp_path):
    """Verify end-to-end pipeline execution using the offline test fixture."""
    pipeline = FIRMSIngestionPipeline(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    signals, report, files = pipeline.run_pipeline(
        fixture_path=FIXTURE_PATH,
        bbox=DELHI_NCR_BBOX,
        save_raw=True,
    )

    # From our fixture of 11 rows:
    # 4 valid in Delhi NCR
    # 7 rejected (1 out of bbox, 1 duplicate, 5 syntax/physical failures)
    assert len(signals) == 4
    assert report.total_rows_received == 11
    assert report.rows_retained == 4
    assert report.rows_rejected == 7
    assert report.duplicate_count == 1
    assert report.out_of_bounds_count == 1

    # Verify generated files exist on disk
    assert "raw_csv" in files and files["raw_csv"].exists()
    assert "processed_jsonl" in files and files["processed_jsonl"].exists()
    assert "report_json" in files and files["report_json"].exists()
    assert "report_md" in files and files["report_md"].exists()

    # Verify JSONL lines correspond to valid FireSignal JSON
    lines = files["processed_jsonl"].read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 4
    for line in lines:
        data = json.loads(line)
        assert data["signal_type"] == "THERMAL_FIRE_PIXEL"
        assert data["unit"] == "MW"
        assert "latitude" in data and "longitude" in data
