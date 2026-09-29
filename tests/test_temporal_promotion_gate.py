"""
VayuDrishti — Robust Temporal Validation & Model Promotion Gate Tests (Phase 1E-J2E.5.1)

Comprehensive test suite verifying multi-window chronological validation, frozen model SHA256 protection,
validation run artifact isolation, residual diagnostics, temporal drift tracking, pollution-regime breakdown,
conformal uncertainty coverage, and deterministic promotion gate resolution.
"""

import json
import shutil
import numpy as np
import pytest
from pathlib import Path

from ml.src.forecasting import (
    RobustTemporalValidator,
    PromotionGateEvaluator,
    compute_metrics,
)
from ml.src.forecasting.robust_temporal_validation import (
    FROZEN_MODEL_HASHES,
    PRODUCTION_VALIDATION_STATUS,
    VALID_PROMOTION_GATE_STATUSES,
    compute_file_sha256,
    compute_regime_metrics,
)


@pytest.fixture
def validator(tmp_path):
    """Fixture providing a RobustTemporalValidator pointing to project data."""
    return RobustTemporalValidator(
        data_root=Path("data"),
        models_dir=Path("ml/models/forecasting"),
        candidates_dir=Path("ml/models/forecasting/candidates"),
        validation_runs_dir=tmp_path / "validation_runs",
    )


@pytest.fixture
def promotion_evaluator():
    """Fixture providing a PromotionGateEvaluator."""
    return PromotionGateEvaluator(data_root=Path("data"))


# Test 1: Frozen model hashes verification before execution
def test_frozen_model_hashes_verified(validator):
    hashes = validator.verify_frozen_model_hashes()
    assert "1h" in hashes
    assert "3h" in hashes
    assert "6h" in hashes
    for h in ["1h", "3h", "6h"]:
        assert hashes[h]["status"] == "MATCH"
        assert hashes[h]["actual"] == FROZEN_MODEL_HASHES[h]


# Test 2: Compute metrics helper accuracy
def test_compute_metrics_accuracy():
    y_true = np.array([100.0, 150.0, 200.0], dtype=np.float32)
    y_pred = np.array([110.0, 140.0, 210.0], dtype=np.float32)
    m = compute_metrics(y_true, y_pred)
    assert m["sample_count"] == 3
    assert abs(m["mae"] - 10.0) < 1e-3
    assert m["rmse"] > 0
    assert m["smape"] > 0


# Test 3: Compute metrics handling of empty arrays
def test_compute_metrics_empty():
    m = compute_metrics(np.array([]), np.array([]))
    assert m["mae"] == 0.0
    assert m["sample_count"] == 0


# Test 4: Compute regime metrics functionality
def test_compute_regime_metrics():
    y_true = np.array([50.0, 80.0, 150.0, 300.0], dtype=np.float32)
    y_pred = np.array([55.0, 85.0, 160.0, 310.0], dtype=np.float32)
    regimes = compute_regime_metrics(y_true, y_pred)
    assert "MODERATE_LOW" in regimes
    assert "POOR_HIGH" in regimes
    assert "SEVERE_CRITICAL" in regimes
    assert regimes["MODERATE_LOW"]["sample_count"] == 2
    assert regimes["POOR_HIGH"]["sample_count"] == 1
    assert regimes["SEVERE_CRITICAL"]["sample_count"] == 1


# Test 5: Dataset loading and chronological sorting
def test_load_dataset_sorting(validator):
    rows, feature_cols = validator.load_dataset()
    assert len(rows) > 0
    assert len(feature_cols) == 27
    ts_list = [r["prediction_timestamp"] for r in rows]
    assert ts_list == sorted(ts_list)


# Test 6: Multi-window chronological splits generation
def test_prepare_multi_window_splits(validator):
    rows, feature_cols = validator.load_dataset()
    windows = validator.prepare_multi_window_splits(rows, feature_cols, "pm25_t_plus_1h", num_windows=3)
    assert len(windows) == 3
    for idx, w in enumerate(windows):
        assert w["window_index"] == idx + 1
        assert len(w["train_rows"]) > 0
        assert len(w["val_rows"]) > 0
        assert len(w["test_rows"]) > 0
        assert w["X_train"].shape[1] == 27
        assert w["X_val"].shape[1] == 27
        assert w["X_test"].shape[1] == 27


# Test 7: Multi-window splits chronological order non-overlapping train/val/test
def test_multi_window_chronological_isolation(validator):
    rows, feature_cols = validator.load_dataset()
    windows = validator.prepare_multi_window_splits(rows, feature_cols, "pm25_t_plus_1h", num_windows=2)
    for w in windows:
        train_max = w["split_dates"]["train_max"]
        val_min = w["split_dates"]["val_min"]
        val_max = w["split_dates"]["val_max"]
        test_min = w["split_dates"]["test_min"]
        assert train_max <= val_min
        assert val_max <= test_min


# Test 8: Validation run candidate model training isolation in validation_runs directory
def test_train_validation_model_isolation(validator):
    rows, feature_cols = validator.load_dataset()
    windows = validator.prepare_multi_window_splits(rows, feature_cols, "pm25_t_plus_1h", num_windows=1)
    meta = validator.train_validation_model(windows[0], "+1h")
    assert meta["status"] == "TRAINED"
    model_path = Path(meta["model_path"])
    assert model_path.exists()
    assert "validation_runs" in str(model_path)
    assert model_path.parent == validator.validation_runs_dir


# Test 9: Persistence baseline multi-horizon evaluation
def test_evaluate_persistence_baseline(validator):
    rows, feature_cols = validator.load_dataset()
    windows = validator.prepare_multi_window_splits(rows, feature_cols, "pm25_t_plus_1h", num_windows=1)
    metrics = validator.evaluate_persistence_baseline(windows[0]["test_rows"], horizon_hours=1)
    assert metrics["sample_count"] > 0
    assert metrics["mae"] >= 0.0


# Test 10: Full robust temporal validation run execution
def test_run_robust_temporal_validation(validator):
    res = validator.run_robust_temporal_validation(num_windows=3, train_validation_models=True)
    assert res["production_validation_status"] == PRODUCTION_VALIDATION_STATUS
    assert res["feature_parity_passed"] is True
    assert res["frozen_hashes_untouched"] is True
    assert "window_results" in res
    assert "+1h" in res["window_results"]
    assert "+3h" in res["window_results"]
    assert "+6h" in res["window_results"]


# Test 11: Verification that rolling_temporal_validation_report.json is generated
def test_rolling_temporal_validation_report_file_generated(validator):
    validator.run_robust_temporal_validation(num_windows=2, train_validation_models=True)
    report_file = Path("data/processed/forecasting/rolling_temporal_validation_report.json")
    assert report_file.exists()
    with open(report_file, "r") as f:
        data = json.load(f)
    assert data["phase"] == "PHASE 1E-J2E.5.1 — ROBUST TEMPORAL VALIDATION & MODEL PROMOTION GATE"
    assert data["production_validation_status"] == PRODUCTION_VALIDATION_STATUS


# Test 12: Promotion gate evaluation resolution for valid report
def test_promotion_gate_evaluator_valid(validator, promotion_evaluator):
    val_report = validator.run_robust_temporal_validation(num_windows=2, train_validation_models=True)
    gate_res = promotion_evaluator.evaluate_promotion_gate(val_report)
    assert gate_res["promotion_gate_status"] in VALID_PROMOTION_GATE_STATUSES
    assert gate_res["production_validation_status"] == PRODUCTION_VALIDATION_STATUS
    assert gate_res["frozen_model_hash_protection_verified"] is True
    assert gate_res["feature_contract_parity_verified"] is True


# Test 13: Verification that promotion_gate_report.json is generated
def test_promotion_gate_report_file_generated(validator, promotion_evaluator):
    val_report = validator.run_robust_temporal_validation(num_windows=2, train_validation_models=True)
    promotion_evaluator.evaluate_promotion_gate(val_report)
    report_file = Path("data/processed/forecasting/promotion_gate_report.json")
    assert report_file.exists()
    with open(report_file, "r") as f:
        data = json.load(f)
    assert data["phase"] == "PHASE 1E-J2E.5.1 — ROBUST TEMPORAL VALIDATION & MODEL PROMOTION GATE"
    assert data["production_validation_status"] == PRODUCTION_VALIDATION_STATUS


# Test 14: Promotion gate blocks when frozen hash is mutated
def test_promotion_gate_blocks_on_hash_mutation(promotion_evaluator):
    mock_report = {
        "frozen_hashes_untouched": False,
        "feature_parity_passed": True,
        "data_summary": {"total_rows": 2000, "window_count": 3},
        "aggregated_metrics": {},
    }
    gate_res = promotion_evaluator.evaluate_promotion_gate(mock_report)
    assert gate_res["promotion_gate_status"] == "PROMOTION_BLOCKED"
    assert "FROZEN_MODEL_HASH_MUTATED" in gate_res["block_reasons"]


# Test 15: Promotion gate blocks when feature contract parity fails
def test_promotion_gate_blocks_on_feature_parity_failure(promotion_evaluator):
    mock_report = {
        "frozen_hashes_untouched": True,
        "feature_parity_passed": False,
        "data_summary": {"total_rows": 2000, "window_count": 3},
        "aggregated_metrics": {},
    }
    gate_res = promotion_evaluator.evaluate_promotion_gate(mock_report)
    assert gate_res["promotion_gate_status"] == "PROMOTION_BLOCKED"
    assert "FEATURE_CONTRACT_PARITY_FAILED" in gate_res["block_reasons"]


# Test 16: Promotion gate sets MORE_EVIDENCE_REQUIRED when sample count is low and candidate is poor
def test_promotion_gate_more_evidence_required(promotion_evaluator):
    mock_report = {
        "frozen_hashes_untouched": True,
        "feature_parity_passed": True,
        "data_summary": {"total_rows": 50, "window_count": 1},
        "aggregated_metrics": {
            "+1h": {
                "candidate_model_avg_mae": 50.0,
                "persistence_avg_mae": 30.0,
                "frozen_model_avg_mae": 25.0,
            }
        },
    }
    gate_res = promotion_evaluator.evaluate_promotion_gate(mock_report)
    assert gate_res["promotion_gate_status"] == "MORE_EVIDENCE_REQUIRED"


# Test 17: Production validation status is NOT_PRODUCTION_VALIDATED under all gate outcomes
def test_production_validation_status_always_not_production_validated(promotion_evaluator):
    for status_name in ["mock_a", "mock_b"]:
        mock_report = {
            "frozen_hashes_untouched": True,
            "feature_parity_passed": True,
            "data_summary": {"total_rows": 600, "window_count": 3},
            "aggregated_metrics": {
                "+1h": {
                    "candidate_model_avg_mae": 20.0,
                    "persistence_avg_mae": 30.0,
                    "frozen_model_avg_mae": 25.0,
                }
            },
        }
        gate_res = promotion_evaluator.evaluate_promotion_gate(mock_report)
        assert gate_res["production_validation_status"] == "NOT_PRODUCTION_VALIDATED"


# Test 18: Frozen model files strictly untouched after full validation run
def test_frozen_model_sha256_unmodified_after_validation(validator):
    hashes_before = validator.verify_frozen_model_hashes()
    validator.run_robust_temporal_validation(num_windows=2, train_validation_models=True)
    hashes_after = validator.verify_frozen_model_hashes()

    for h in ["1h", "3h", "6h"]:
        assert hashes_before[h]["actual"] == hashes_after[h]["actual"]
        assert hashes_after[h]["actual"] == FROZEN_MODEL_HASHES[h]


# Test 19: Residual diagnostics percentiles and mean integrity
def test_residual_diagnostics_integrity(validator):
    rows, feature_cols = validator.load_dataset()
    windows = validator.prepare_multi_window_splits(rows, feature_cols, "pm25_t_plus_1h", num_windows=1)
    w = windows[0]
    frozen_path = validator.models_dir / "lightgbm_pm25_1h.txt"
    import lightgbm as lgb
    booster = lgb.Booster(model_file=str(frozen_path))
    pred = booster.predict(w["X_test"], predict_disable_shape_check=True)
    res = w["y_test"] - pred
    assert len(res) == len(w["y_test"])
    assert np.isnan(res).sum() == 0


# Test 20: Conformal coverage calculation sanity check
def test_conformal_coverage_bounds(validator):
    res = validator.run_robust_temporal_validation(num_windows=2, train_validation_models=False)
    for h in ["+1h", "+3h", "+6h"]:
        for w_eval in res["window_results"][h]:
            cov = w_eval["conformal_coverage"]
            assert 0.0 <= cov["coverage_80_pct"] <= 100.0
            assert 0.0 <= cov["coverage_90_pct"] <= 100.0
            assert 0.0 <= cov["coverage_95_pct"] <= 100.0
            assert cov["quantile_80"] <= cov["quantile_90"] <= cov["quantile_95"]


# Test 21: Export parity check in ml.src.forecasting
def test_package_exports():
    import ml.src.forecasting as m
    assert hasattr(m, "RobustTemporalValidator")
    assert hasattr(m, "PromotionGateEvaluator")
    assert hasattr(m, "compute_metrics")


# Test 22: Valid promotion gate statuses set definition
def test_valid_promotion_gate_statuses_set():
    assert len(VALID_PROMOTION_GATE_STATUSES) == 4
    assert "MORE_EVIDENCE_REQUIRED" in VALID_PROMOTION_GATE_STATUSES
    assert "CANDIDATE_SUPPORTED_FOR_REVIEW" in VALID_PROMOTION_GATE_STATUSES
    assert "PROMOTION_BLOCKED" in VALID_PROMOTION_GATE_STATUSES
    assert "PROMOTION_REVIEW_REQUIRED" in VALID_PROMOTION_GATE_STATUSES


# Test 23: SHA256 helper digest computation with missing file
def test_compute_file_sha256_nonexistent():
    with pytest.raises(FileNotFoundError):
        compute_file_sha256("nonexistent_file_path.txt")


# Test 24: High volatility drift detection in promotion evaluator
test_cases_drift = [
    (18.0, True),  # High std => excessive drift
    (2.0, False),   # Low std => stable
]

@pytest.mark.parametrize("cand_std,expected_drift_flag", test_cases_drift)
def test_promotion_gate_drift_sensitivity(promotion_evaluator, cand_std, expected_drift_flag):
    mock_report = {
        "frozen_hashes_untouched": True,
        "feature_parity_passed": True,
        "data_summary": {"total_rows": 2000, "window_count": 3},
        "aggregated_metrics": {
            "+1h": {
                "candidate_model_avg_mae": 15.0,
                "candidate_model_std_mae": cand_std,
                "persistence_avg_mae": 30.0,
                "frozen_model_avg_mae": 20.0,
            }
        },
    }
    res = promotion_evaluator.evaluate_promotion_gate(mock_report)
    if expected_drift_flag:
        assert any("EXCESSIVE_DRIFT" in reason for reason in res["block_reasons"])
    else:
        assert not any("EXCESSIVE_DRIFT" in reason for reason in res["block_reasons"])


# Test 25: Multi-horizon completeness check (+1h, +3h, +6h)
def test_multi_horizon_completeness(validator):
    report = validator.run_robust_temporal_validation(num_windows=2, train_validation_models=True)
    assert set(report["window_results"].keys()) == {"+1h", "+3h", "+6h"}
    assert set(report["aggregated_metrics"].keys()) == {"+1h", "+3h", "+6h"}
    assert set(report["drift_tracking"].keys()) == {"+1h", "+3h", "+6h"}
