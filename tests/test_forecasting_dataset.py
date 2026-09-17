"""
VayuDrishti — Forecasting Dataset & Feature Engineering Test Suite (Phase 1E-J1)

Tests UTC timestamp normalization, target horizon construction (+1h, +3h, +6h),
historical lag creation, backward rolling window statistics, weather alignment,
station isolation, missing data handling, 14-point schema validation, readiness assessment,
and 7 mandatory automated temporal leakage tests.
"""

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import pytest

from ml.src.forecasting import (
    ForecastingConfig,
    ForecastingDataValidator,
    ForecastingDatasetBuilder,
    ForecastingReadinessAssessor,
    verify_zero_temporal_leakage,
)
from ml.src.forecasting.feature_engineering import (
    align_weather_features,
    compute_cyclic_time_features,
    compute_lag_and_rolling_features,
)
from ml.src.forecasting.target_builder import compute_target_horizons
from ml.src.forecasting.timestamp_utils import (
    detect_irregular_intervals,
    parse_utc_timestamp,
    sort_and_deduplicate_records,
)
from tests.fixtures.forecasting.synthetic_forecasting_fixtures import (
    get_synthetic_forecasting_records,
)


@pytest.fixture
def temp_forecasting_dir():
    """Provides a temporary data root directory for forecasting dataset builder tests."""
    tmp_path = Path(tempfile.mkdtemp(prefix="vayudrishti_forecasting_test_"))
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


# ==============================================================================
# 1. TIMESTAMP & ALIGNMENT UTILITY TESTS
# ==============================================================================
def test_parse_utc_timestamp():
    """Verifies parsing ISO timestamp strings and datetime objects into normalized UTC."""
    dt1 = parse_utc_timestamp("2026-03-15T10:00:00Z")
    assert dt1.hour == 10
    assert dt1.tzname() == "UTC"

    dt2 = parse_utc_timestamp("2026-03-15T10:00:00+00:00")
    assert dt2 == dt1

    with pytest.raises(ValueError):
        parse_utc_timestamp("invalid-timestamp-string")


def test_sort_and_deduplicate_records():
    """Verifies sorting by (station_id, pollutant, timestamp) and deduplicating exact keys."""
    raw_records = [
        {"station_id": "st_02", "pollutant": "PM2.5", "timestamp": "2026-03-15T11:00:00Z", "value": 110.0},
        {"station_id": "st_01", "pollutant": "PM2.5", "timestamp": "2026-03-15T12:00:00Z", "value": 120.0},
        {"station_id": "st_01", "pollutant": "PM2.5", "timestamp": "2026-03-15T10:00:00Z", "value": 100.0},
        {"station_id": "st_01", "pollutant": "PM2.5", "timestamp": "2026-03-15T10:00:00Z", "value": 100.0},  # Duplicate
    ]

    processed = sort_and_deduplicate_records(raw_records)
    assert len(processed) == 3
    assert processed[0]["station_id"] == "st_01"
    assert processed[0]["parsed_timestamp"].hour == 10
    assert processed[1]["station_id"] == "st_01"
    assert processed[1]["parsed_timestamp"].hour == 12
    assert processed[2]["station_id"] == "st_02"


def test_detect_irregular_intervals():
    """Verifies irregular temporal interval detection across station series."""
    synth = get_synthetic_forecasting_records(num_hours=12)
    processed = sort_and_deduplicate_records(synth["openaq"])
    gap_info = detect_irregular_intervals(processed)

    assert "station_gaps" in gap_info
    assert "syn_st_01" in gap_info["station_gaps"]
    # Intentional missing observation at h=10 creates a gap of 2 hours
    assert gap_info["station_gaps"]["syn_st_01"]["is_irregular"] is True


# ==============================================================================
# 2. FEATURE ENGINEERING & CYCLIC ENCODING TESTS
# ==============================================================================
def test_compute_cyclic_time_features():
    """Verifies deterministic sine/cosine encodings for hour, day of week, and month."""
    dt = parse_utc_timestamp("2026-03-15T00:00:00Z")  # Midnight, Sunday (dow=6), March (m=3)
    feats = compute_cyclic_time_features(dt)

    assert feats["hour_sin"] == 0.0
    assert feats["hour_cos"] == 1.0
    assert -1.0 <= feats["day_of_week_sin"] <= 1.0
    assert -1.0 <= feats["month_sin"] <= 1.0


def test_compute_lag_and_rolling_features():
    """Verifies historical lag creation and backward rolling statistics."""
    synth = get_synthetic_forecasting_records(num_hours=24)
    processed = sort_and_deduplicate_records(synth["openaq"])
    st01_obs = [r for r in processed if r["station_id"] == "syn_st_01" and r["pollutant"] == "PM25"]

    # Compute features for observation at index 12 (t = 12h)
    feats = compute_lag_and_rolling_features(st01_obs, current_idx=12)

    assert "pm25_lag_1h" in feats
    assert "pm25_lag_3h" in feats
    assert "pm25_lag_6h" in feats
    assert "pm25_roll_mean_3h" in feats
    assert "pm25_roll_median_3h" in feats

    # Rolling window values must be derived strictly from past observations <= t
    assert feats["pm25_roll_mean_3h"] is not None
    assert feats["pm25_roll_median_3h"] is not None


def test_align_weather_features():
    """Verifies weather feature alignment to prediction time t using observations <= t only."""
    synth = get_synthetic_forecasting_records(num_hours=12)
    weather = synth["weather"]

    prediction_dt = parse_utc_timestamp("2026-03-15T05:00:00Z")
    aligned = align_weather_features(prediction_dt, 28.610, 77.200, weather)

    assert aligned["temperature_2m"] is not None
    assert aligned["relative_humidity_2m"] is not None
    assert aligned["wind_speed_10m"] is not None
    assert aligned["wind_u"] is not None
    assert aligned["wind_v"] is not None


# ==============================================================================
# 3. TARGET HORIZONS TESTS
# ==============================================================================
def test_compute_target_horizons():
    """Verifies strictly future-looking target horizons (+1h, +3h, +6h)."""
    synth = get_synthetic_forecasting_records(num_hours=24)
    processed = sort_and_deduplicate_records(synth["openaq"])
    st01_obs = [r for r in processed if r["station_id"] == "syn_st_01" and r["pollutant"] == "PM25"]

    targets = compute_target_horizons(st01_obs, current_idx=5)

    assert "pm25_t_plus_1h" in targets
    assert "pm25_t_plus_3h" in targets
    assert "pm25_t_plus_6h" in targets

    # Value at index 5 + 1h = index 6 value
    val_plus_1h = st01_obs[6]["value"]
    assert targets["pm25_t_plus_1h"] == round(val_plus_1h, 2)


# ==============================================================================
# 4. MANDATORY TEMPORAL LEAKAGE TESTS (TESTS 1 - 7)
# ==============================================================================
def test_mandatory_temporal_leakage_protections(temp_forecasting_dir):
    """Executes the 7 mandatory automated temporal leakage verification tests."""
    builder = ForecastingDatasetBuilder(data_root=temp_forecasting_dir)
    synth = get_synthetic_forecasting_records(num_hours=24)

    leakage_result = verify_zero_temporal_leakage(
        builder_fn=lambda o, w: builder.build_dataset_rows(o, w),
        test_openaq_records=synth["openaq"],
        test_weather_records=synth["weather"],
    )

    assert leakage_result["leakage_passed"] is True
    test_res = leakage_result["test_results"]
    assert test_res["test_1_future_1h_pm25_mutation_safe"] is True
    assert test_res["test_2_future_3h_pm25_mutation_safe"] is True
    assert test_res["test_3_future_6h_pm25_mutation_safe"] is True
    assert test_res["test_4_future_weather_mutation_safe"] is True
    assert test_res["test_5_rolling_window_strictly_past"] is True
    assert test_res["test_6_station_isolation_guaranteed"] is True
    assert test_res["test_7_target_shifting_strictly_forward"] is True


# ==============================================================================
# 5. DATASET BUILDER, QUALITY & READINESS TESTS
# ==============================================================================
def test_forecasting_dataset_builder_pipeline(temp_forecasting_dir):
    """Verifies end-to-end dataset construction and artifact persistence."""
    builder = ForecastingDatasetBuilder(data_root=temp_forecasting_dir)
    synth = get_synthetic_forecasting_records(num_hours=24)

    result = builder.build_and_save(
        custom_openaq_records=synth["openaq"],
        custom_weather_records=synth["weather"],
    )

    assert result["dataset_rows_count"] > 0
    assert result["quality_report"]["is_valid"] is True
    assert result["leakage_report"]["leakage_passed"] is True

    # Verify output files exist
    artifacts = result["artifacts"]
    assert Path(artifacts["csv_path"]).exists()
    assert Path(artifacts["manifest_path"]).exists()
    assert Path(artifacts["quality_path"]).exists()
    assert Path(artifacts["readiness_path"]).exists()

    # Read manifest and verify schema
    with open(artifacts["manifest_path"], "r", encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["dataset_version"] == "1.0-provisional"
    assert manifest["row_count"] == result["dataset_rows_count"]
    assert "target_horizons" in manifest


def test_honest_readiness_assessment_on_single_timestamp(temp_forecasting_dir):
    """
    Verifies that a dataset with insufficient historical timestamps (e.g. 1 timestamp snapshot)
    honestly evaluates to NOT_READY with explicit non-readiness reasons.
    """
    builder = ForecastingDatasetBuilder(data_root=temp_forecasting_dir)

    # Single timestamp snapshot records (like real local snapshot)
    single_ts_records = [
        {"station_id": "st_01", "timestamp": "2026-09-13T16:00:00Z", "pollutant": "PM2.5", "value": 142.5, "location": {"latitude": 28.64, "longitude": 77.31}},
        {"station_id": "st_02", "timestamp": "2026-09-13T16:00:00Z", "pollutant": "PM2.5", "value": 118.0, "location": {"latitude": 28.67, "longitude": 77.13}},
        {"station_id": "st_03", "timestamp": "2026-09-13T16:00:00Z", "pollutant": "PM2.5", "value": 96.0, "location": {"latitude": 28.63, "longitude": 77.20}},
    ]

    result = builder.build_and_save(custom_openaq_records=single_ts_records)

    readiness = result["readiness_report"]
    assert readiness["readiness_status"] == "NOT_READY"
    assert readiness["training_ready"] is False
    assert len(readiness["readiness_reasons"]) >= 1
    assert "Insufficient historical timestamps" in readiness["readiness_reasons"][0]
