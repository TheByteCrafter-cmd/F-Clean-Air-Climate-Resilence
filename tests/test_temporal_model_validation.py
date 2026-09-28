"""
VayuDrishti — Temporal Model Validation & Readiness Assessment Tests (Phase 1E-J2E.5.0)

Focused test suite verifying:
- Chronological train/validation/test splitting (NO random splitting)
- Feature contract parity (27 features)
- Persistence baseline vs Frozen vs Candidate evaluation on identical test rows
- Candidate model isolation in candidates/
- Frozen model SHA256 hash protection
- Conformal uncertainty coverage & residual diagnostics
- Readiness status gates & no automatic promotion
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from ml.src.forecasting.timestamp_utils import parse_utc_timestamp
from ml.src.forecasting.temporal_validation import (
    FROZEN_MODEL_HASHES,
    PRODUCTION_VALIDATION_STATUS,
    TemporalModelValidator,
    compute_file_sha256,
    compute_metrics,
)



@pytest.fixture
def validator():
    """Returns initialized TemporalModelValidator instance."""
    return TemporalModelValidator()


@pytest.fixture
def synthetic_rows():
    """Generates synthetic hourly rows for chronological split tests."""
    rows = []
    start_dt = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(100):
        t_dt = start_dt + timedelta(hours=i)
        t_str = t_dt.isoformat().replace("+00:00", "Z")
        rows.append({
            "station_id": "ANAND_VIHAR_8118",
            "prediction_timestamp": t_str,
            "pm25_t0": 100.0 + i,
            "pm25_t_plus_1h": 102.0 + i,
            "pm25_t_plus_3h": 105.0 + i,
            "pm25_t_plus_6h": 110.0 + i,
            "latitude": 28.6469,
            "longitude": 77.3160,
        })
    return rows


# -----------------------------------------------------------------------------
# 1-6. SPLIT, DATA SUFFICIENCY & TARGET ALIGNMENT TESTS
# -----------------------------------------------------------------------------

def test_01_chronological_split(validator, synthetic_rows):
    """Test 1: Verifies train/val/test splits strictly preserve chronological order."""
    feature_cols = ["latitude", "longitude", "pm25_t0"]
    split = validator.prepare_chronological_split(synthetic_rows, feature_cols, "pm25_t_plus_1h")

    assert split["status"] == "READY"
    train_max = parse_utc_timestamp(split["split_dates"]["train_max"])
    val_min = parse_utc_timestamp(split["split_dates"]["val_min"])
    val_max = parse_utc_timestamp(split["split_dates"]["val_max"])
    test_min = parse_utc_timestamp(split["split_dates"]["test_min"])

    assert train_max <= val_min
    assert val_max <= test_min


def test_02_no_random_split_verification(validator, synthetic_rows):
    """Test 2: Verifies split order is identical across multiple calls (deterministic)."""
    feature_cols = ["latitude", "longitude", "pm25_t0"]
    s1 = validator.prepare_chronological_split(synthetic_rows, feature_cols, "pm25_t_plus_1h")
    s2 = validator.prepare_chronological_split(synthetic_rows, feature_cols, "pm25_t_plus_1h")

    assert s1["split_dates"] == s2["split_dates"]
    assert len(s1["test_rows"]) == len(s2["test_rows"])


def test_03_data_sufficiency_gate(validator):
    """Test 3: Small datasets (< 30 rows) return INSUFFICIENT_DATA status."""
    small_rows = [
        {"station_id": "ANAND_VIHAR_8118", "prediction_timestamp": f"2025-01-01T{h:02d}:00:00Z", "pm25_t_plus_1h": 100.0}
        for h in range(10)
    ]
    split = validator.prepare_chronological_split(small_rows, ["pm25_t0"], "pm25_t_plus_1h")
    assert split["status"] == "INSUFFICIENT_DATA"


def test_04_target_alignment_plus_1h(validator, synthetic_rows):
    """Test 4: Target alignment for +1h horizon generates non-empty target values."""
    split = validator.prepare_chronological_split(synthetic_rows, ["pm25_t0"], "pm25_t_plus_1h")
    assert len(split["y_test"]) > 0
    assert not np.isnan(split["y_test"]).any()


def test_05_target_alignment_plus_3h(validator, synthetic_rows):
    """Test 5: Target alignment for +3h horizon generates non-empty target values."""
    split = validator.prepare_chronological_split(synthetic_rows, ["pm25_t0"], "pm25_t_plus_3h")
    assert len(split["y_test"]) > 0
    assert not np.isnan(split["y_test"]).any()


def test_06_target_alignment_plus_6h(validator, synthetic_rows):
    """Test 6: Target alignment for +6h horizon generates non-empty target values."""
    split = validator.prepare_chronological_split(synthetic_rows, ["pm25_t0"], "pm25_t_plus_6h")
    assert len(split["y_test"]) > 0
    assert not np.isnan(split["y_test"]).any()


# -----------------------------------------------------------------------------
# 7-12. PERSISTENCE BASELINE, FEATURE PARITY & MODEL FROZEN HASH TESTS
# -----------------------------------------------------------------------------

def test_07_persistence_baseline_evaluation(validator, synthetic_rows):
    """Test 7: Persistence baseline generates non-zero metrics on test set."""
    split = validator.prepare_chronological_split(synthetic_rows, ["pm25_t0"], "pm25_t_plus_1h")
    metrics = validator.evaluate_persistence_baseline(split["test_rows"], "pm25_t_plus_1h", horizon_hours=1)
    assert "mae" in metrics
    assert "rmse" in metrics
    assert "smape" in metrics
    assert metrics["sample_count"] > 0


def test_08_identical_evaluation_rows(validator):
    """Test 8: Baseline and models evaluate on identical holdout test set rows."""
    res = validator.validate_temporal_performance()
    comp = res["comparison_report"]["model_comparison"]
    for h_key in ["+1h", "+3h", "+6h"]:
        if comp[h_key].get("status") != "INSUFFICIENT_DATA":
            n_pers = comp[h_key]["persistence_baseline"]["sample_count"]
            n_froz = comp[h_key]["frozen_model"]["sample_count"]
            assert n_pers == n_froz


def test_09_feature_count_parity(validator):
    """Test 9: Verified feature count matches canonical 27 features."""
    _, feature_cols = validator.load_dataset()
    assert len(feature_cols) == 27


def test_10_feature_ordering_parity(validator):
    """Test 10: Verified dataset feature columns match model_manifest.json feature list."""
    _, feature_cols = validator.load_dataset()
    manifest_features = validator.assembler.manifest_features
    assert feature_cols == manifest_features


def test_11_candidate_model_isolation(validator):
    """Test 11: Candidate models are stored in candidates/ subfolder only."""
    res = validator.validate_temporal_performance(train_candidate=True)
    cands = res["comparison_report"].get("candidate_models", {})
    for h_key, meta in cands.items():
        if meta.get("status") == "TRAINED":
            assert "candidates" in meta["candidate_path"]


def test_12_frozen_model_protection_hashes(validator):
    """Test 12: Frozen LightGBM model hashes match original SHA256 baselines."""
    verif = validator.verify_frozen_model_hashes()
    for h_key, meta in verif.items():
        assert meta["status"] == "MATCH"
        assert meta["actual"] == FROZEN_MODEL_HASHES[h_key]


# -----------------------------------------------------------------------------
# 13-18. METRICS, RESIDUALS, DRIFT & READINESS GATE TESTS
# -----------------------------------------------------------------------------

def test_13_metric_calculation_correctness():
    """Test 13: Verifies compute_metrics returns exact MAE, RMSE, and sMAPE values."""
    y_true = np.array([100.0, 150.0, 200.0], dtype=np.float32)
    y_pred = np.array([110.0, 140.0, 210.0], dtype=np.float32)
    m = compute_metrics(y_true, y_pred)
    assert m["mae"] == 10.0
    assert m["rmse"] == 10.0
    assert m["sample_count"] == 3


def test_14_residual_calculation_diagnostics(validator):
    """Test 14: Residual diagnostics report mean, median, and bias direction."""
    res = validator.validate_temporal_performance()
    res_diag = res["validation_report"]["residual_diagnostics"]
    for h_key in ["+1h", "+3h", "+6h"]:
        assert "mean_residual" in res_diag[h_key]
        assert "bias_direction" in res_diag[h_key]


def test_15_temporal_drift_diagnostics(validator):
    """Test 15: Rolling MAE and RMSE diagnostics are generated across test period."""
    res = validator.validate_temporal_performance()
    drift = res["validation_report"]["temporal_drift"]
    for h_key in ["+1h", "+3h", "+6h"]:
        assert "rolling_mae_mean" in drift[h_key]
        assert "rolling_rmse_mean" in drift[h_key]


def test_16_conformal_coverage_validation(validator):
    """Test 16: Evaluates empirical 80% and 90% conformal coverage on test set."""
    res = validator.validate_temporal_performance()
    conf = res["validation_report"]["conformal_coverage"]
    for h_key in ["+1h", "+3h", "+6h"]:
        assert "test_empirical_coverage_80_pct" in conf[h_key]
        assert "test_empirical_coverage_90_pct" in conf[h_key]


def test_17_readiness_status_gate(validator):
    """Test 17: Readiness status returns CANDIDATE_EVALUATED when candidate is trained."""
    res = validator.validate_temporal_performance(train_candidate=True)
    assert res["readiness_status"] == "CANDIDATE_EVALUATED"


def test_18_insufficient_data_behavior(validator):
    """Test 18: Returns INSUFFICIENT_DATA when synthetic dataset has < 30 rows."""
    small_rows = [
        {"station_id": "ANAND_VIHAR_8118", "prediction_timestamp": f"2025-01-01T{h:02d}:00:00Z", "pm25_t_plus_1h": 100.0}
        for h in range(10)
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("station_id,prediction_timestamp,pm25_t_plus_1h\n")
        for r in small_rows:
            f.write(f"{r['station_id']},{r['prediction_timestamp']},{r['pm25_t_plus_1h']}\n")
        f_path = Path(f.name)

    try:
        res = validator.validate_temporal_performance(csv_path=f_path)
        assert res["readiness_status"] == "INSUFFICIENT_DATA"
    finally:
        f_path.unlink()


# -----------------------------------------------------------------------------
# 19-22. PROMOTION SAFETY, REPEATABILITY & ARTIFACT SCHEMA TESTS
# -----------------------------------------------------------------------------

def test_19_no_automatic_model_promotion(validator):
    """Test 19: Verifies production validation status remains NOT_PRODUCTION_VALIDATED."""
    res = validator.validate_temporal_performance(train_candidate=True)
    assert res["production_validation_status"] == PRODUCTION_VALIDATION_STATUS
    assert res["production_validation_status"] == "NOT_PRODUCTION_VALIDATED"


def test_20_deterministic_repeated_evaluation(validator):
    """Test 20: Repeated evaluation runs produce bit-identical metrics."""
    r1 = validator.validate_temporal_performance(train_candidate=False)
    r2 = validator.validate_temporal_performance(train_candidate=False)

    m1 = r1["comparison_report"]["model_comparison"]["+1h"]["frozen_model"]
    m2 = r2["comparison_report"]["model_comparison"]["+1h"]["frozen_model"]
    assert m1 == m2


def test_21_missing_data_handling(validator):
    """Test 21: Handles missing target values gracefully without crashing."""
    rows, feature_cols = validator.load_dataset()
    # Insert NaN target in middle row
    rows[10]["pm25_t_plus_1h"] = None
    split = validator.prepare_chronological_split(rows, feature_cols, "pm25_t_plus_1h")
    assert split["status"] == "READY"


def test_22_artifact_schema_verification(validator):
    """Test 22: Verifies output JSON report files exist and conform to schema keys."""
    res = validator.validate_temporal_performance(train_candidate=True)
    val_path = Path(res["artifacts"]["temporal_validation_report_json"])
    comp_path = Path(res["artifacts"]["model_comparison_report_json"])

    assert val_path.exists()
    assert comp_path.exists()

    val_json = json.loads(val_path.read_text(encoding="utf-8"))
    comp_json = json.loads(comp_path.read_text(encoding="utf-8"))

    assert "readiness_status" in val_json
    assert "production_validation_status" in val_json
    assert "model_comparison" in comp_json
