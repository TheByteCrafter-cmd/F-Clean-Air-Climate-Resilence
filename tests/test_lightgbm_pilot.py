"""
VayuDrishti — LightGBM Pilot Model Training Test Suite (Phase 1E-J2C)

Validates LightGBMPilotTrainer functionality, chronological data splitting,
zero leakage, deterministic training, metric calculation, baseline comparison,
model artifact persistence, and model reload capabilities.
"""

import json
import pytest
import numpy as np
import lightgbm as lgb
from pathlib import Path

from ml.src.forecasting.trainer import LightGBMPilotTrainer, calculate_smape


@pytest.fixture
def trainer(tmp_path):
    return LightGBMPilotTrainer(data_root=tmp_path, random_state=42)


def test_derive_feature_columns(trainer):
    """Test 1: Dynamic feature column derivation."""
    all_cols = [
        "station_id", "prediction_timestamp", "station_name", "pm25_t0",
        "pm25_lag_1h", "pm25_lag_3h", "pm25_roll_mean_3h", "temperature_2m",
        "wind_speed_10m", "hour_sin", "latitude", "longitude",
        "pm25_t_plus_1h", "pm25_t_plus_3h", "pm25_t_plus_6h"
    ]
    derived = trainer.derive_feature_columns(all_cols)
    assert "station_id" not in derived
    assert "prediction_timestamp" not in derived
    assert "pm25_t_plus_1h" not in derived
    assert "pm25_lag_1h" in derived
    assert "temperature_2m" in derived
    assert len(derived) == 8


def test_chronological_split_and_target_separation(trainer):
    """Test 2 & 3: Chronological splitting and zero target leakage."""
    raw_rows = []
    # Generate 100 chronological dummy rows
    for i in range(100):
        ts = f"2025-01-01T{i%24:02d}:00:00Z"
        raw_rows.append({
            "station_id": "ANAND_VIHAR_8118",
            "prediction_timestamp": f"2025-01-{(i//24)+1:02d}T{i%24:02d}:00:00Z",
            "pm25_lag_1h": str(100.0 + i),
            "temperature_2m": "20.0",
            "pm25_t_plus_1h": str(105.0 + i),
        })

    feature_cols = ["pm25_lag_1h", "temperature_2m"]
    split = trainer.prepare_split_data(raw_rows, feature_cols, "pm25_t_plus_1h", train_pct=0.70, val_pct=0.15)

    assert split["total_usable_rows"] == 100
    assert len(split["train_rows"]) == 70
    assert len(split["val_rows"]) == 15
    assert len(split["test_rows"]) == 15

    # Check temporal ordering (Train < Val < Test)
    max_train_ts = split["train_range"][1]
    min_val_ts = split["val_range"][0]
    max_val_ts = split["val_range"][1]
    min_test_ts = split["test_range"][0]

    assert max_train_ts <= min_val_ts
    assert max_val_ts <= min_test_ts


def test_deterministic_training_repeatability(trainer):
    """Test 4 & 6: Deterministic model training configuration."""
    raw_rows = []
    for i in range(100):
        raw_rows.append({
            "station_id": "ANAND_VIHAR_8118",
            "prediction_timestamp": f"2025-01-{(i//24)+1:02d}T{i%24:02d}:00:00Z",
            "pm25_lag_1h": str(100.0 + i),
            "temperature_2m": "20.0",
            "pm25_t_plus_1h": str(105.0 + (i % 10)),
        })

    feature_cols = ["pm25_lag_1h", "temperature_2m"]
    split = trainer.prepare_split_data(raw_rows, feature_cols, "pm25_t_plus_1h")

    res1 = trainer.train_horizon_model("+1h", "pm25_t_plus_1h", split)
    res2 = trainer.train_horizon_model("+1h", "pm25_t_plus_1h", split)

    assert res1["split_metrics"]["test"]["rmse"] == res2["split_metrics"]["test"]["rmse"]
    assert res1["best_iteration"] == res2["best_iteration"]


def test_prediction_schema_and_sanity(trainer):
    """Test 5: Prediction schema and sanity check."""
    raw_rows = []
    for i in range(100):
        raw_rows.append({
            "station_id": "ANAND_VIHAR_8118",
            "prediction_timestamp": f"2025-01-{(i//24)+1:02d}T{i%24:02d}:00:00Z",
            "pm25_lag_1h": str(100.0 + i),
            "temperature_2m": "20.0",
            "pm25_t_plus_1h": str(105.0 + i),
        })

    feature_cols = ["pm25_lag_1h", "temperature_2m"]
    split = trainer.prepare_split_data(raw_rows, feature_cols, "pm25_t_plus_1h")
    res = trainer.train_horizon_model("+1h", "pm25_t_plus_1h", split)

    sanity = res["sanity_check"]
    assert sanity["is_numeric"] is True
    assert sanity["is_finite"] is True
    assert sanity["has_nans"] is False
    assert sanity["count"] == len(split["y_test"])

    # Check test_predictions structure
    preds = res["test_predictions"]
    assert len(preds) == len(split["y_test"])
    assert "predicted_pm25" in preds[0]
    assert "actual_pm25" in preds[0]
    assert "absolute_error" in preds[0]


def test_smape_metric_calculation():
    """Test 7: sMAPE metric calculation."""
    actuals = np.array([100.0, 150.0, 200.0])
    preds = np.array([110.0, 140.0, 200.0])
    smape = calculate_smape(actuals, preds)
    assert smape is not None
    assert round(smape, 2) == 5.47


def test_baseline_comparison_structure(trainer):
    """Test 8: Baseline comparison dictionary structure."""
    raw_rows = []
    for i in range(100):
        raw_rows.append({
            "station_id": "ANAND_VIHAR_8118",
            "prediction_timestamp": f"2025-01-{(i//24)+1:02d}T{i%24:02d}:00:00Z",
            "pm25_t0": str(100.0 + i),
            "pm25_lag_1h": str(100.0 + i),
            "temperature_2m": "20.0",
            "pm25_t_plus_1h": str(105.0 + i),
        })

    feature_cols = ["pm25_lag_1h", "temperature_2m"]
    split = trainer.prepare_split_data(raw_rows, feature_cols, "pm25_t_plus_1h")
    res = trainer.train_horizon_model("+1h", "pm25_t_plus_1h", split)

    pers_comp = res["persistence_comparison"]
    assert "persistence_mae" in pers_comp
    assert "lightgbm_mae" in pers_comp
    assert "mae_improvement_pct" in pers_comp


def test_feature_importance_generation(trainer):
    """Test 9: Gain-based feature importance generation."""
    raw_rows = []
    for i in range(100):
        raw_rows.append({
            "station_id": "ANAND_VIHAR_8118",
            "prediction_timestamp": f"2025-01-{(i//24)+1:02d}T{i%24:02d}:00:00Z",
            "pm25_lag_1h": str(100.0 + i),
            "temperature_2m": str(20.0 + (i % 5)),
            "pm25_t_plus_1h": str(105.0 + i),
        })

    feature_cols = ["pm25_lag_1h", "temperature_2m"]
    split = trainer.prepare_split_data(raw_rows, feature_cols, "pm25_t_plus_1h")
    res = trainer.train_horizon_model("+1h", "pm25_t_plus_1h", split)

    fi = res["feature_importance"]
    assert len(fi) == 2
    assert "feature" in fi[0]
    assert "importance" in fi[0]
    assert fi[0]["importance_type"] == "gain"


def test_model_artifact_saving_and_reload(trainer, tmp_path):
    """Test 10: Model artifact saving and reload inference verification."""
    raw_rows = []
    for i in range(100):
        raw_rows.append({
            "station_id": "ANAND_VIHAR_8118",
            "prediction_timestamp": f"2025-01-{(i//24)+1:02d}T{i%24:02d}:00:00Z",
            "pm25_lag_1h": str(100.0 + i),
            "temperature_2m": "20.0",
            "pm25_t_plus_1h": str(105.0 + i),
        })

    feature_cols = ["pm25_lag_1h", "temperature_2m"]
    split = trainer.prepare_split_data(raw_rows, feature_cols, "pm25_t_plus_1h")
    res = trainer.train_horizon_model("+1h", "pm25_t_plus_1h", split)

    model_file = Path(res["model_path"])
    assert model_file.exists()

    # Load saved LightGBM Booster and predict
    loaded_booster = lgb.Booster(model_file=str(model_file))
    reloaded_pred = loaded_booster.predict(split["X_test"])

    # Predict with in-memory model
    assert len(reloaded_pred) == len(split["y_test"])
    assert np.allclose(reloaded_pred, [p["predicted_pm25"] for p in res["test_predictions"]], atol=1e-3)
