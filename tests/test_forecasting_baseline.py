"""
VayuDrishti — Persistence Forecasting Baseline Test Suite (Phase 1E-J2B)

Tests deterministic persistence forecaster, maximum anchor age threshold enforcement,
station isolation, chronological split non-leakage, metric calculations, and all 9
mandatory temporal leakage safety rules.
"""

import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ml.src.forecasting.baseline import PersistenceForecaster
from ml.src.forecasting.evaluation import (
    BaselineEvaluator,
    compute_mae,
    compute_rmse,
    compute_smape,
    split_chronologically,
)


@pytest.fixture
def temp_baseline_dir():
    """Provides temporary directory for baseline evaluator tests."""
    tmp_path = Path(tempfile.mkdtemp(prefix="vayudrishti_baseline_test_"))
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


# ==============================================================================
# 1. MANDATORY LEAKAGE & CORE PERSISTENCE TESTS
# ==============================================================================
def test_future_pm25_does_not_influence_prediction():
    """Rule 1 & 2: Ensures future observations (> t) cannot influence prediction at t."""
    forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)
    pred_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)

    station_history = [
        {"parsed_timestamp": datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc), "pm25_t0": 80.0},
        {"parsed_timestamp": datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc), "pm25_t0": 100.0},
        {"parsed_timestamp": datetime(2026, 3, 1, 11, 0, tzinfo=timezone.utc), "pm25_t0": 500.0},  # Future spike
    ]

    obs, age = forecaster.find_latest_anchor(station_history, pred_dt)

    assert obs is not None
    assert obs["pm25_t0"] == 100.0  # Must be 100.0 (t=10:00), not future 500.0 (t=11:00)
    assert age == 0.0


def test_observation_after_t_cannot_become_anchor():
    """Rule 3: Explicitly verifies observation after t cannot become an anchor."""
    forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)
    pred_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)

    station_history = [
        {"parsed_timestamp": datetime(2026, 3, 1, 10, 1, tzinfo=timezone.utc), "pm25_t0": 250.0},  # 1 min in future
    ]

    obs, age = forecaster.find_latest_anchor(station_history, pred_dt)
    assert obs is None
    assert age is None


def test_station_isolation_guarantee():
    """Rule 4: Station A observations cannot become Station B anchors."""
    forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)

    records = [
        {
            "station_id": "STATION_A",
            "prediction_timestamp": "2026-03-01T10:00:00Z",
            "pm25_t0": 120.0,
            "pm25_t_plus_1h": 125.0,
        },
        {
            "station_id": "STATION_B",
            "prediction_timestamp": "2026-03-01T10:00:00Z",
            "pm25_t0": None,  # Missing for Station B
            "pm25_t_plus_1h": 90.0,
        },
    ]

    preds = forecaster.generate_predictions(records, horizons_hours=[1])

    b_pred = next(p for p in preds if p["station_id"] == "STATION_B")
    assert b_pred["prediction_pm25"] is None  # Must NOT borrow 120.0 from Station A!


def test_anchor_age_calculation():
    """Rule 5: Verifies anchor age calculation accuracy in minutes."""
    forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)
    pred_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)

    station_history = [
        {"parsed_timestamp": datetime(2026, 3, 1, 8, 30, tzinfo=timezone.utc), "pm25_t0": 95.0},
    ]

    obs, age = forecaster.find_latest_anchor(station_history, pred_dt)
    assert obs is not None
    assert age == 90.0  # 10:00 - 8:30 = 90 minutes


def test_max_anchor_age_expiration_policy():
    """Rule 6: Predictions beyond max anchor age threshold become unavailable."""
    forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)
    pred_dt = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)

    # 3.01 hours old (> 180 minutes)
    history_old = [
        {"parsed_timestamp": datetime(2026, 3, 1, 6, 59, tzinfo=timezone.utc), "pm25_t0": 110.0},
    ]
    obs_old, age_old = forecaster.find_latest_anchor(history_old, pred_dt)
    assert obs_old is None

    # Exactly 3.00 hours old (180 minutes) -> Acceptable
    history_exact = [
        {"parsed_timestamp": datetime(2026, 3, 1, 7, 0, tzinfo=timezone.utc), "pm25_t0": 110.0},
    ]
    obs_exact, age_exact = forecaster.find_latest_anchor(history_exact, pred_dt)
    assert obs_exact is not None
    assert age_exact == 180.0


def test_target_horizon_mapping():
    """Rule 7: Verifies +1h, +3h, +6h target mapping and error computations."""
    forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)

    records = [
        {
            "station_id": "ANAND_VIHAR",
            "prediction_timestamp": "2026-03-01T10:00:00Z",
            "pm25_t0": 100.0,
            "pm25_t_plus_1h": 110.0,
            "pm25_t_plus_3h": 130.0,
            "pm25_t_plus_6h": 150.0,
        }
    ]

    preds = forecaster.generate_predictions(records, horizons_hours=[1, 3, 6])
    assert len(preds) == 3

    p1 = next(p for p in preds if p["horizon"] == "+1h")
    assert p1["prediction_pm25"] == 100.0
    assert p1["actual_pm25"] == 110.0
    assert p1["absolute_error"] == 10.0
    assert p1["squared_error"] == 100.0

    p3 = next(p for p in preds if p["horizon"] == "+3h")
    assert p3["absolute_error"] == 30.0

    p6 = next(p for p in preds if p["horizon"] == "+6h")
    assert p6["absolute_error"] == 50.0


def test_chronological_split_leakage_protection():
    """Rule 8: Verifies chronological split produces non-overlapping, strictly ordered partitions."""
    records = [
        {"prediction_timestamp": f"2026-03-01T{h:02d}:00:00Z", "val": h}
        for h in range(20)
    ]

    dev, val, test = split_chronologically(records, dev_pct=0.70, val_pct=0.15, test_pct=0.15)

    assert len(dev) + len(val) + len(test) == 20
    max_dev_ts = max(r["prediction_timestamp"] for r in dev)
    min_val_ts = min(r["prediction_timestamp"] for r in val)
    max_val_ts = max(r["prediction_timestamp"] for r in val)
    min_test_ts = min(r["prediction_timestamp"] for r in test)

    assert max_dev_ts <= min_val_ts
    assert max_val_ts <= min_test_ts


def test_deterministic_reproducibility():
    """Rule 9: Re-running benchmark produces identical output on identical inputs."""
    forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)
    records = [
        {
            "station_id": "ITO_8120",
            "prediction_timestamp": "2026-03-01T12:00:00Z",
            "pm25_t0": 150.0,
            "pm25_t_plus_1h": 160.0,
        }
    ]

    preds1 = forecaster.generate_predictions(records)
    preds2 = forecaster.generate_predictions(records)

    assert preds1 == preds2


# ==============================================================================
# 2. METRIC FUNCTION TESTS
# ==============================================================================
def test_evaluation_metric_formulas():
    """Verifies MAE, RMSE, and sMAPE formula calculations."""
    actuals = [100.0, 200.0, 150.0]
    preds = [110.0, 190.0, 150.0]

    # MAE = (|10| + |-10| + |0|) / 3 = 20 / 3 = 6.6667
    assert compute_mae(actuals, preds) == 6.6667

    # RMSE = sqrt((100 + 100 + 0) / 3) = sqrt(66.6667) = 8.1650
    assert compute_rmse(actuals, preds) == 8.1650

    # sMAPE
    smape_val = compute_smape(actuals, preds)
    assert smape_val > 0.0


# ==============================================================================
# 3. READINESS GATE INTEGRATION TESTS
# ==============================================================================
def test_evaluator_blocks_on_not_ready(temp_baseline_dir):
    """Verifies that BaselineEvaluator respects NOT_READY gate and does not fabricate metrics."""
    evaluator = BaselineEvaluator(data_root=temp_baseline_dir)

    # Ensure processed directory has NOT_READY readiness artifact
    processed_dir = temp_baseline_dir / "processed" / "forecasting"
    processed_dir.mkdir(parents=True, exist_ok=True)
    with open(processed_dir / "forecast_data_readiness.json", "w", encoding="utf-8") as f:
        json.dump({
            "readiness_status": "NOT_READY",
            "training_ready": False,
            "readiness_reasons": ["Insufficient timestamps."],
        }, f)

    result = evaluator.evaluate_benchmark()

    assert result["overall_status"] == "BLOCKED"
    assert result["benchmark_status"] == "BASELINE BLOCKED BY DATA READINESS"

    # Check created artifacts
    baseline_dir = processed_dir / "baseline"
    assert (baseline_dir / "baseline_readiness.json").exists()
    assert (baseline_dir / "baseline_metrics.json").exists()
    assert (baseline_dir / "baseline_evaluation_manifest.json").exists()
    assert (baseline_dir / "persistence_predictions.csv").exists()
