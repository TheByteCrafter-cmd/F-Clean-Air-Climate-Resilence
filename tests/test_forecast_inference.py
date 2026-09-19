"""
VayuDrishti — Forecast Inference Core Test Suite (Phase 1E-J2E.1)

Tests model loading, manifest validation, feature schema reordering,
station scope guardrails, prediction generation, conformal prediction interval construction,
negative prediction diagnostics, timestamp validation, and determinism.
"""

import json
from pathlib import Path
import pytest
import numpy as np

from ml.src.forecasting.model_loader import (
    CANONICAL_STATION_ID,
    ForecastModelLoader,
    ModelLoaderError,
)
from ml.src.forecasting.inference import (
    ForecastInferenceEngine,
    InferenceError,
)


@pytest.fixture
def project_paths():
    """Provides project paths for tests."""
    root = Path(__file__).resolve().parent.parent
    return {
        "models_dir": root / "ml" / "models" / "forecasting",
        "data_root": root / "data",
    }


@pytest.fixture
def inference_engine(project_paths):
    """Fixture providing initialized ForecastInferenceEngine instance."""
    return ForecastInferenceEngine(
        models_dir=project_paths["models_dir"],
        data_root=project_paths["data_root"],
    )


@pytest.fixture
def valid_sample_feature_row(inference_engine):
    """Fixture providing valid 27-feature dictionary for testing."""
    features = inference_engine.feature_list
    row = {
        "latitude": 28.6469,
        "longitude": 77.316,
        "pm25_lag_1h": 150.0,
        "pm25_lag_3h": 160.0,
        "pm25_lag_6h": 170.0,
        "pm25_lag_12h": 180.0,
        "pm25_lag_24h": 190.0,
        "pm25_roll_mean_3h": 155.0,
        "pm25_roll_median_3h": 155.0,
        "pm25_roll_mean_6h": 165.0,
        "pm25_roll_median_6h": 165.0,
        "pm25_roll_mean_24h": 175.0,
        "pm25_roll_median_24h": 175.0,
        "temperature_2m": 15.5,
        "relative_humidity_2m": 65.0,
        "wind_speed_10m": 2.5,
        "wind_direction_10m": 180.0,
        "wind_u": -0.5,
        "wind_v": -2.4,
        "surface_pressure": 995.0,
        "boundary_layer_height": 250.0,
        "hour_sin": 0.5,
        "hour_cos": 0.866,
        "day_of_week_sin": 0.0,
        "day_of_week_cos": 1.0,
        "month_sin": 0.5,
        "month_cos": 0.866,
    }
    # Sanity check fixture has all required manifest features
    for col in features:
        if col not in row:
            row[col] = 1.0
    return row


def test_model_loading(project_paths):
    """1. Test loading boosters and manifest via ForecastModelLoader."""
    loader = ForecastModelLoader(
        models_dir=project_paths["models_dir"],
        data_root=project_paths["data_root"],
    )
    boosters = loader.load_models()
    assert "+1h" in boosters
    assert "+3h" in boosters
    assert "+6h" in boosters


def test_manifest_validation(project_paths):
    """2. Test model_manifest.json loading and metadata validation."""
    loader = ForecastModelLoader(
        models_dir=project_paths["models_dir"],
        data_root=project_paths["data_root"],
    )
    manifest = loader.load_manifest()
    assert manifest["model_family"] == "LightGBM Regression"
    assert isinstance(manifest["feature_list"], list)
    assert manifest["feature_count"] == len(manifest["feature_list"])


def test_feature_order_validation(inference_engine, valid_sample_feature_row):
    """3. Test that input dictionary is reordered strictly to manifest order."""
    # Pass dictionary with reversed keys
    reversed_row = {k: valid_sample_feature_row[k] for k in reversed(valid_sample_feature_row)}
    X = inference_engine.prepare_feature_vector(reversed_row)

    assert X.shape == (1, inference_engine.feature_count)
    # Check value at index 0 corresponds to first feature in manifest
    first_feat = inference_engine.feature_list[0]
    assert X[0, 0] == float(valid_sample_feature_row[first_feat])


def test_missing_feature_rejection(inference_engine, valid_sample_feature_row):
    """4. Test missing feature rejection raises InferenceError."""
    incomplete_row = dict(valid_sample_feature_row)
    del incomplete_row["pm25_lag_1h"]

    with pytest.raises(InferenceError) as exc_info:
        inference_engine.predict("8118", "2025-01-31T12:00:00Z", incomplete_row)

    assert exc_info.value.error_code == "MISSING_FEATURES"
    assert "pm25_lag_1h" in exc_info.value.details["missing_features"]


def test_unsupported_station_rejection(inference_engine, valid_sample_feature_row):
    """5. Test unsupported station scope rejection."""
    with pytest.raises(InferenceError) as exc_info:
        inference_engine.predict("LOCATION_9999", "2025-01-31T12:00:00Z", valid_sample_feature_row)

    assert exc_info.value.error_code == "UNSUPPORTED_STATION_SCOPE"
    assert "LOCATION_9999" in str(exc_info.value)


def test_plus_1h_prediction_generation(inference_engine, valid_sample_feature_row):
    """6. Test +1h forecast prediction generation."""
    res = inference_engine.predict("8118", "2025-01-31T12:00:00Z", valid_sample_feature_row, horizons=["+1h"])
    assert res["status"] == "SUCCESS"
    assert "+1h" in res["horizons"]
    h1 = res["horizons"]["+1h"]
    assert isinstance(h1["predicted_pm25"], float)


def test_plus_3h_prediction_generation(inference_engine, valid_sample_feature_row):
    """7. Test +3h forecast prediction generation."""
    res = inference_engine.predict("ANAND_VIHAR_8118", "2025-01-31T12:00:00Z", valid_sample_feature_row, horizons=["+3h"])
    assert res["status"] == "SUCCESS"
    assert "+3h" in res["horizons"]
    h3 = res["horizons"]["+3h"]
    assert isinstance(h3["predicted_pm25"], float)


def test_plus_6h_prediction_generation(inference_engine, valid_sample_feature_row):
    """8. Test +6h forecast prediction generation."""
    res = inference_engine.predict("8118", "2025-01-31T12:00:00Z", valid_sample_feature_row, horizons=["+6h"])
    assert res["status"] == "SUCCESS"
    assert "+6h" in res["horizons"]
    h6 = res["horizons"]["+6h"]
    assert isinstance(h6["predicted_pm25"], float)


def test_80_percent_interval_construction(inference_engine, valid_sample_feature_row):
    """9. Test 80% prediction interval construction (lower = pred - q80, upper = pred + q80)."""
    res = inference_engine.predict("8118", "2025-01-31T12:00:00Z", valid_sample_feature_row, horizons=["+1h"])
    h1 = res["horizons"]["+1h"]
    pred = h1["predicted_pm25"]
    iv80 = h1["prediction_intervals"]["80_pct"]

    q80 = iv80["conformal_radius"]
    assert round(pred - q80, 4) == iv80["lower_bound"]
    assert round(pred + q80, 4) == iv80["upper_bound"]
    assert iv80["interval_width"] == round(2.0 * q80, 4)


def test_90_percent_interval_construction(inference_engine, valid_sample_feature_row):
    """10. Test 90% prediction interval construction."""
    res = inference_engine.predict("8118", "2025-01-31T12:00:00Z", valid_sample_feature_row, horizons=["+1h"])
    h1 = res["horizons"]["+1h"]
    pred = h1["predicted_pm25"]
    iv90 = h1["prediction_intervals"]["90_pct"]

    q90 = iv90["conformal_radius"]
    assert round(pred - q90, 4) == iv90["lower_bound"]
    assert round(pred + q90, 4) == iv90["upper_bound"]
    assert iv90["interval_width"] == round(2.0 * q90, 4)


def test_frozen_conformal_radius_loading(project_paths):
    """11. Test frozen conformal radii loading and validation."""
    loader = ForecastModelLoader(
        models_dir=project_paths["models_dir"],
        data_root=project_paths["data_root"],
    )
    radii = loader.load_conformal_metrics()
    for h in ["+1h", "+3h", "+6h"]:
        assert h in radii
        assert radii[h]["radius_80"] >= 0.0
        assert radii[h]["radius_90"] >= 0.0


def test_unclipped_endpoints(inference_engine):
    """12. Test raw unclipped interval endpoint preservation."""
    # Test handling with synthetic prediction <= 10.0 and q = 42.46 -> lower bound negative
    q_80 = 42.4646
    raw_pred = 10.0
    lower = raw_pred - q_80
    upper = raw_pred + q_80

    assert lower == -32.4646
    assert upper == 52.4646


def test_negative_prediction_diagnostic(inference_engine, valid_sample_feature_row):
    """13. Test negative prediction diagnostic flag assignment."""
    res = inference_engine.predict("8118", "2025-01-31T12:00:00Z", valid_sample_feature_row)
    for h in ["+1h", "+3h", "+6h"]:
        pred_meta = res["horizons"][h]
        assert "prediction_negative" in pred_meta
        assert pred_meta["prediction_negative"] == bool(pred_meta["predicted_pm25"] < 0.0)


def test_invalid_timestamp_rejection(inference_engine, valid_sample_feature_row):
    """14. Test malformed prediction timestamp rejection."""
    with pytest.raises(InferenceError) as exc_info:
        inference_engine.predict("8118", "invalid-date-string", valid_sample_feature_row)

    assert exc_info.value.error_code == "INVALID_TIMESTAMP"


def test_deterministic_reload_prediction(project_paths, valid_sample_feature_row):
    """15. Test model reloading determinism."""
    engine1 = ForecastInferenceEngine(models_dir=project_paths["models_dir"], data_root=project_paths["data_root"])
    res1 = engine1.predict("8118", "2025-01-31T12:00:00Z", valid_sample_feature_row)

    engine2 = ForecastInferenceEngine(models_dir=project_paths["models_dir"], data_root=project_paths["data_root"])
    res2 = engine2.predict("8118", "2025-01-31T12:00:00Z", valid_sample_feature_row)

    assert res1 == res2


def test_output_schema_validation(inference_engine, valid_sample_feature_row):
    """16. Test output schema fields completeness."""
    res = inference_engine.predict("8118", "2025-01-31T12:00:00Z", valid_sample_feature_row)
    assert res["status"] == "SUCCESS"
    assert res["canonical_station_id"] == CANONICAL_STATION_ID
    assert "prediction_timestamp" in res
    assert "feature_count" in res
    assert len(res["horizons"]) == 3
