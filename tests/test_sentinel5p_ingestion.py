"""
VayuDrishti - Phase 1E-D Sentinel-5P / Earth Engine Ingestion Tests
Comprehensive unit tests for Sentinel-5P client, normalizer, validator, and pipeline.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest

from backend.api.v1.schemas.satellite import SatelliteSignal, Sentinel5PNO2Signal
from backend.ingestion import (
    DEFAULT_DELHI_ROI,
    GEE_COLLECTION_ID,
    S5P_PRIMARY_BAND,
    Sentinel5PClient,
    Sentinel5PNormalizer,
    Sentinel5PValidator,
    Sentinel5PQualityReport,
    Sentinel5PPipeline,
    GEEAuthenticationError,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sentinel5p_delhi_sample.json"


# ------------------------------------------------------------------------------
# 1. Earth Engine Catalog Contract & Auth Tests
# ------------------------------------------------------------------------------

def test_sentinel5p_catalog_contract():
    """Verify Earth Engine catalog contract parameters."""
    contract = Sentinel5PClient.get_catalog_contract()
    assert contract["dataset_id"] == "COPERNICUS/S5P/NRTI/L3_NO2"
    assert contract["platform"] == "Sentinel-5P"
    assert contract["instrument"] == "TROPOMI"
    assert contract["primary_band"]["name"] == "tropospheric_NO2_column_number_density"
    assert contract["primary_band"]["unit"] == "mol/m?"
    assert contract["primary_band"]["valid_min"] == -0.0001
    assert "cloud_fraction" in contract["supporting_bands"]


def test_sentinel5p_unauthenticated_graceful_handling():
    """Verify client reports GEE RUNTIME ACCESS NOT CONFIGURED and raises on live call."""
    client = Sentinel5PClient()
    is_auth, msg = client.check_authentication()
    # In unconfigured local dev, is_auth must be False
    assert is_auth is False
    assert "GEE RUNTIME ACCESS NOT CONFIGURED" in msg

    # extract_live must raise GEEAuthenticationError without crashing
    with pytest.raises(GEEAuthenticationError) as exc_info:
        client.extract_live()
    assert "GEE RUNTIME ACCESS NOT CONFIGURED" in str(exc_info.value)


# ------------------------------------------------------------------------------
# 2. Normalization Engine Tests
# ------------------------------------------------------------------------------

def test_sentinel5p_normalizer_field_and_band_mapping():
    """Verify mapping of raw GEE records to canonical Sentinel5PNO2Signal schema."""
    normalizer = Sentinel5PNormalizer()
    rec = {
        "latitude": 28.6139,
        "longitude": 77.2090,
        "tropospheric_NO2_column_number_density": 0.000142,
        "cloud_fraction": 0.12,
        "qa_value": 0.88,
        "stratospheric_NO2_column_number_density": 0.000035,
        "NO2_column_number_density": 0.000177,
        "system_time_start": 1789200000000,
    }
    result = normalizer.normalize_record(rec)
    assert result.is_valid is True
    signal = result.signal
    assert signal is not None
    assert isinstance(signal, Sentinel5PNO2Signal)
    assert isinstance(signal, SatelliteSignal)  # Inheritance check

    assert signal.satellite == "Sentinel-5P"
    assert signal.instrument == "TROPOMI"
    assert signal.signal_type == "SATELLITE_NO2_COLUMN"
    assert signal.unit == "mol/m?"
    assert signal.value == 0.000142
    assert signal.tropospheric_no2_mol_m2 == 0.000142
    assert signal.cloud_fraction == 0.12
    assert signal.qa_value == 0.88
    assert signal.quality_indicator == "HIGH"
    assert signal.geometry["coordinates"] == [77.209, 28.6139]

    # SCIENTIFIC INTEGRITY: Ensure no PM2.5 or ug/m3 conversion exists
    assert not hasattr(signal, "pm25_concentration")
    assert not hasattr(signal, "ug_m3")


def test_sentinel5p_normalizer_timestamp_parsing():
    """Verify parsing of epoch milliseconds and ISO strings to UTC datetimes."""
    normalizer = Sentinel5PNormalizer()

    # Milliseconds
    res1 = normalizer.normalize_record({
        "latitude": 28.6, "longitude": 77.2,
        "tropospheric_NO2_column_number_density": 0.0001,
        "system_time_start": 1789200000000,
    })
    assert res1.is_valid is True
    assert res1.signal.acquisition_time.tzinfo == timezone.utc

    # ISO string
    res2 = normalizer.normalize_record({
        "latitude": 28.6, "longitude": 77.2,
        "tropospheric_NO2_column_number_density": 0.0001,
        "timestamp": "2026-09-12T08:00:00Z",
    })
    assert res2.is_valid is True
    assert res2.signal.acquisition_time == datetime(2026, 9, 12, 8, 0, 0, tzinfo=timezone.utc)


def test_sentinel5p_normalizer_negative_value_preservation():
    """Verify scientifically valid small negative DOAS noise is preserved without zero-clamping."""
    normalizer = Sentinel5PNormalizer()

    # Small negative value (-1.5e-5 mol/m? = -15 ?mol/m?) -> PRESERVED
    res_valid_neg = normalizer.normalize_record({
        "latitude": 28.78, "longitude": 77.02,
        "tropospheric_NO2_column_number_density": -0.000015,
        "timestamp": "2026-09-12T08:00:00Z",
    })
    assert res_valid_neg.is_valid is True
    assert res_valid_neg.signal.tropospheric_no2_mol_m2 == -0.000015
    assert res_valid_neg.signal.value == -0.000015
    # Must NOT be clamped to zero
    assert res_valid_neg.signal.value != 0.0

    # Extreme unphysical negative anomaly (< -0.0001 mol/m?) -> REJECTED
    res_extreme_neg = normalizer.normalize_record({
        "latitude": 28.78, "longitude": 77.02,
        "tropospheric_NO2_column_number_density": -0.0005,
        "timestamp": "2026-09-12T08:00:00Z",
    })
    assert res_extreme_neg.is_valid is False
    assert "Unphysical negative" in res_extreme_neg.rejection_reason


def test_sentinel5p_normalizer_quality_tiering():
    """Verify quality tier determination from cloud fraction and QA value."""
    normalizer = Sentinel5PNormalizer()

    # High quality (clear sky, high QA)
    res_hi = normalizer.normalize_record({
        "latitude": 28.6, "longitude": 77.2,
        "tropospheric_NO2_column_number_density": 0.0001,
        "cloud_fraction": 0.15, "qa_value": 0.85,
        "timestamp": "2026-09-12T08:00:00Z",
    })
    assert res_hi.signal.quality_indicator == "HIGH"

    # Nominal quality (moderate cloud <= 0.5)
    res_nom = normalizer.normalize_record({
        "latitude": 28.6, "longitude": 77.2,
        "tropospheric_NO2_column_number_density": 0.0001,
        "cloud_fraction": 0.40, "qa_value": 0.60,
        "timestamp": "2026-09-12T08:00:00Z",
    })
    assert res_nom.signal.quality_indicator == "NOMINAL"

    # Low quality (high cloud > 0.5)
    res_lo = normalizer.normalize_record({
        "latitude": 28.6, "longitude": 77.2,
        "tropospheric_NO2_column_number_density": 0.0001,
        "cloud_fraction": 0.65, "qa_value": 0.40,
        "timestamp": "2026-09-12T08:00:00Z",
    })
    assert res_lo.signal.quality_indicator == "LOW"


def test_sentinel5p_normalizer_syntax_rejections():
    """Verify rejection of malformed or incomplete records."""
    normalizer = Sentinel5PNormalizer()

    # Missing coordinate
    assert normalizer.normalize_record({}).is_valid is False
    assert normalizer.normalize_record({"latitude": None, "longitude": 77.2}).is_valid is False

    # Out of bounds coordinates
    res_coord = normalizer.normalize_record({
        "latitude": 95.0, "longitude": 77.2,
        "tropospheric_NO2_column_number_density": 0.0001,
        "timestamp": "2026-09-12T08:00:00Z",
    })
    assert res_coord.is_valid is False
    assert "out of bounds" in res_coord.rejection_reason

    # Missing NO2 value
    res_no_val = normalizer.normalize_record({
        "latitude": 28.6, "longitude": 77.2,
        "timestamp": "2026-09-12T08:00:00Z",
    })
    assert res_no_val.is_valid is False
    assert "Missing tropospheric NO2" in res_no_val.rejection_reason


# ------------------------------------------------------------------------------
# 3. Validator & Quality Auditor Tests
# ------------------------------------------------------------------------------

def test_sentinel5p_validator_roi_filtering():
    """Verify spatial ROI bounding box filtering."""
    normalizer = Sentinel5PNormalizer()
    validator = Sentinel5PValidator(filter_clouds=False)

    sig_delhi = normalizer.normalize_record({
        "latitude": 28.6139, "longitude": 77.2090,
        "tropospheric_NO2_column_number_density": 0.00014,
        "timestamp": "2026-09-12T08:00:00Z",
    }).signal

    sig_punjab = normalizer.normalize_record({
        "latitude": 31.6340, "longitude": 74.8723,
        "tropospheric_NO2_column_number_density": 0.00015,
        "timestamp": "2026-09-12T08:00:00Z",
    }).signal

    retained, report = validator.validate_dataset([sig_delhi, sig_punjab], roi=DEFAULT_DELHI_ROI)
    assert len(retained) == 1
    assert retained[0].latitude == 28.6139
    assert report.out_of_bounds_count == 1


def test_sentinel5p_validator_cloud_screening():
    """Verify rejection of cloud-obscured observations."""
    normalizer = Sentinel5PNormalizer()
    validator = Sentinel5PValidator(filter_clouds=True, max_cloud_fraction=0.50)

    sig_cloud = normalizer.normalize_record({
        "latitude": 28.60, "longitude": 77.18,
        "tropospheric_NO2_column_number_density": 0.00016,
        "cloud_fraction": 0.72,
        "timestamp": "2026-09-12T08:00:00Z",
    }).signal

    retained, report = validator.validate_dataset([sig_cloud], roi=None)
    assert len(retained) == 0
    assert report.cloud_rejected_count == 1


def test_sentinel5p_validator_deduplication():
    """Verify deterministic deduplication based on signal_id."""
    normalizer = Sentinel5PNormalizer()
    validator = Sentinel5PValidator()

    rec = {
        "latitude": 28.6139, "longitude": 77.2090,
        "tropospheric_NO2_column_number_density": 0.00014,
        "timestamp": "2026-09-12T08:00:00Z",
    }
    sig1 = normalizer.normalize_record(rec).signal
    sig2 = normalizer.normalize_record(rec).signal
    assert sig1.signal_id == sig2.signal_id

    retained, report = validator.validate_dataset([sig1, sig2], roi=None)
    assert len(retained) == 1
    assert report.duplicate_count == 1


def test_sentinel5p_quality_report_rendering():
    """Verify quality report JSON and Markdown serialization."""
    normalizer = Sentinel5PNormalizer()
    validator = Sentinel5PValidator()

    sig = normalizer.normalize_record({
        "latitude": 28.6139, "longitude": 77.2090,
        "tropospheric_NO2_column_number_density": 0.00015,
        "cloud_fraction": 0.15,
        "timestamp": "2026-09-12T08:00:00Z",
    }).signal

    _, report = validator.validate_dataset([sig], roi=DEFAULT_DELHI_ROI)
    rep_dict = report.model_dump()
    assert rep_dict["dataset_id"] == "COPERNICUS/S5P/NRTI/L3_NO2"
    assert rep_dict["unit"] == "mol/m?"

    md = report.to_markdown()
    assert "# Sentinel-5P TROPOMI Tropospheric NO2 Ingestion Quality Report" in md
    assert "mol/m?" in md
    assert "Scientific Integrity Note" in md


# ------------------------------------------------------------------------------
# 4. Pipeline Execution from Fixture
# ------------------------------------------------------------------------------

def test_sentinel5p_pipeline_execution_from_fixture(tmp_path):
    """Verify end-to-end pipeline run from offline test fixture."""
    pipeline = Sentinel5PPipeline(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed" / "satellite",
    )

    signals, report, files = pipeline.run_pipeline(
        fixture_path=FIXTURE_PATH,
        roi=DEFAULT_DELHI_ROI,
        save_raw=True,
    )

    # Out of 11 fixture observations:
    # 6 retained in Delhi pilot
    # 5 rejected (1 cloud obscured, 1 out of ROI, 1 duplicate, 1 extreme negative, 1 missing coord)
    assert len(signals) == 6
    assert report.total_samples_received == 11
    assert report.samples_retained == 6
    assert report.samples_rejected == 5
    assert report.cloud_rejected_count == 1
    assert report.out_of_bounds_count == 1
    assert report.duplicate_count == 1
    assert report.negative_values_preserved_count == 1  # -0.000015 mol/m? retained!

    # Check files exist
    assert "raw_json" in files and files["raw_json"].exists()
    assert "processed_jsonl" in files and files["processed_jsonl"].exists()
    assert "report_json" in files and files["report_json"].exists()
    assert "report_md" in files and files["report_md"].exists()

    # Check processed JSONL contents
    lines = files["processed_jsonl"].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 6
    for line in lines:
        data = json.loads(line)
        assert data["signal_type"] == "SATELLITE_NO2_COLUMN"
        assert data["unit"] == "mol/m?"
        assert "tropospheric_no2_mol_m2" in data
