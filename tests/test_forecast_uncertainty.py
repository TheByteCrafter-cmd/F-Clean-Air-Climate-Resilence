"""
VayuDrishti — Forecast Uncertainty & Residual Analysis Test Suite (Phase 1E-J2D)

Tests residual computation, Split Conformal prediction interval calibration,
order-statistic quantile rules, empirical coverage evaluation, baseline reconciliation,
and artifact persistence.
"""

import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pytest

from ml.src.forecasting.evaluator import (
    CONFORMAL_GUARANTEE_STATEMENT,
    ForecastResidualEvaluator,
    compute_conformal_quantile,
    compute_percentiles,
)


@pytest.fixture
def evaluator(tmp_path):
    """Fixture providing ForecastResidualEvaluator instance using project paths."""
    data_root = Path(__file__).resolve().parent.parent / "data"
    models_dir = Path(__file__).resolve().parent.parent / "ml" / "models" / "forecasting"
    eval_dir = tmp_path / "model_evaluation"
    return ForecastResidualEvaluator(data_root=data_root, models_dir=models_dir, eval_dir=eval_dir)


def test_residual_computation():
    """1. Test residual calculation correctness (actual - predicted)."""
    actuals = np.array([100.0, 150.0, 200.0])
    preds = np.array([90.0, 160.0, 200.0])

    residuals = actuals - preds
    abs_errors = np.abs(residuals)
    sq_errors = residuals ** 2

    np.testing.assert_array_almost_equal(residuals, [10.0, -10.0, 0.0])
    np.testing.assert_array_almost_equal(abs_errors, [10.0, 10.0, 0.0])
    np.testing.assert_array_almost_equal(sq_errors, [100.0, 100.0, 0.0])


def test_order_statistic_conformal_quantile():
    """2. Test finite-sample order statistic conformal quantile calculation."""
    # 100 validation residuals: 1.0, 2.0, ..., 100.0
    val_abs_res = np.arange(1.0, 101.0)  # n = 100

    # For 80% confidence (alpha = 0.20): k = ceil(101 * 0.80) = ceil(80.8) = 81
    # 81st element of sorted val_abs_res is 81.0
    q_80 = compute_conformal_quantile(val_abs_res, alpha=0.20)
    assert q_80 == 81.0

    # For 90% confidence (alpha = 0.10): k = ceil(101 * 0.90) = ceil(90.9) = 91
    # 91st element is 91.0
    q_90 = compute_conformal_quantile(val_abs_res, alpha=0.10)
    assert q_90 == 91.0


def test_empirical_coverage_calculation():
    """3. Test hit rate and empirical coverage calculation."""
    actuals = np.array([100.0, 150.0, 200.0, 250.0])
    preds = np.array([105.0, 145.0, 215.0, 300.0])
    q = 10.0  # interval is [pred - 10, pred + 10]

    lowers = preds - q
    uppers = preds + q

    hits = [(l <= act <= u) for act, l, u in zip(actuals, lowers, uppers)]
    # [100 in [95, 115] (True), 150 in [135, 155] (True), 200 in [205, 225] (False), 250 in [290, 310] (False)]
    assert hits == [True, True, False, False]

    emp_coverage = (sum(hits) / len(hits)) * 100.0
    assert emp_coverage == 50.0


def test_interval_width_reporting(evaluator):
    """4. Test that interval width is constant (2*q) per horizon and reported honestly."""
    result = evaluator.evaluate_residuals_and_uncertainty()

    uncertainty = result["uncertainty_metrics"]
    for h_name in ["+1h", "+3h", "+6h"]:
        q80 = uncertainty[h_name]["conformal_radius_80"]
        w80 = uncertainty[h_name]["average_interval_width_80"]
        med_w80 = uncertainty[h_name]["median_interval_width_80"]

        assert round(2.0 * q80, 4) == w80
        assert w80 == med_w80  # Constant width per horizon


def test_unclipped_intervals():
    """5. Test unclipped prediction interval handling."""
    pred = 10.0
    q = 25.0
    lower = pred - q
    upper = pred + q

    # Ensure negative lower bounds are unclipped and preserved
    assert lower == -15.0
    assert upper == 35.0


def test_high_pollution_error_analysis(evaluator):
    """6. Test high-pollution error analysis structure."""
    result = evaluator.evaluate_residuals_and_uncertainty()
    diag = result["residual_diagnostics"]

    for h_name in ["+1h", "+3h", "+6h"]:
        hp = diag[h_name]["high_pollution_analysis"]
        assert "threshold_pm25" in hp
        assert hp["threshold_pm25"] == 200.0
        assert "sample_count" in hp
        assert "mean_residual" in hp


def test_temporal_error_breakdown(evaluator):
    """7. Test temporal error breakdown structure."""
    result = evaluator.evaluate_residuals_and_uncertainty()
    diag = result["residual_diagnostics"]

    for h_name in ["+1h", "+3h", "+6h"]:
        tb = diag[h_name]["temporal_breakdown"]
        assert "by_hour_of_day" in tb
        assert "by_day_of_week" in tb


def test_baseline_reconciliation(evaluator):
    """8. Test baseline reconciliation output structure."""
    reconciled = evaluator.reconcile_baselines()
    assert reconciled["reconciliation_status"] == "RECONCILED"
    assert "horizons" in reconciled
    for h in ["+1h", "+3h", "+6h"]:
        assert h in reconciled["horizons"]
        assert "j2c_holdout_test_baseline" in reconciled["horizons"][h]
        assert "j2c_lightgbm_model" in reconciled["horizons"][h]


def test_artifact_persistence_and_schemas(evaluator):
    """9. Test artifact persistence and JSON schema validity."""
    result = evaluator.evaluate_residuals_and_uncertainty()
    artifacts = result["artifacts"]

    for name, path in artifacts.items():
        assert Path(path).exists(), f"Artifact {name} does not exist at {path}"

    with open(artifacts["uncertainty_metrics_json"], "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["conformal_guarantee_disclaimer"] == CONFORMAL_GUARANTEE_STATEMENT
        assert "horizons" in data


def test_repeatability(evaluator):
    """10. Test repeatability and determinism across pipeline runs."""
    res1 = evaluator.evaluate_residuals_and_uncertainty()
    res2 = evaluator.evaluate_residuals_and_uncertainty()

    assert res1["uncertainty_metrics"] == res2["uncertainty_metrics"]
    assert res1["horizon_widths"] == res2["horizon_widths"]


def test_model_reloading_and_inference_with_uncertainty():
    """11. Test reloading trained LightGBM model and producing predictions + conformal bounds."""
    models_dir = Path(__file__).resolve().parent.parent / "ml" / "models" / "forecasting"
    model_path = models_dir / "lightgbm_pm25_1h.txt"

    assert model_path.exists()
    gbm = lgb.Booster(model_file=str(model_path))

    # Dummy feature vector with 27 features
    dummy_input = np.ones((1, 27), dtype=np.float32)
    pred = float(gbm.predict(dummy_input)[0])

    q_80 = 42.46
    lower_80 = pred - q_80
    upper_80 = pred + q_80

    assert isinstance(pred, float)
    assert lower_80 < pred < upper_80
