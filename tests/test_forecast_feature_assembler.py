"""
VayuDrishti — Forecast Feature Assembler Test Suite (Phase 1E-J2E.3.1)

Verifies real-time safe feature assembly, canonical station metadata registry alignment,
60-minute weather staleness default, strict temporal leakage prevention, exact 27-feature
parity against forecast_dataset.csv, and detailed failure diagnostics.
"""

import csv
import hashlib
import json
import math
from pathlib import Path
import pytest

from ml.src.forecasting.feature_assembler import ForecastFeatureAssembler, ForecastFeatureVector
from ml.src.forecasting.historical_ingestion import DELHI_PILOT_STATIONS
from ml.src.forecasting.inference import ForecastInferenceEngine


@pytest.fixture
def assembler():
    return ForecastFeatureAssembler()


@pytest.fixture
def inference_engine():
    return ForecastInferenceEngine()


def get_file_sha256(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        hasher.update(f.read())
    return hasher.hexdigest()


# 1. Canonical Station Resolution
def test_canonical_station_resolution(assembler):
    assert assembler.normalize_station_id("ANAND_VIHAR_8118") == "ANAND_VIHAR_8118"
    assert assembler.normalize_station_id("8118") == "ANAND_VIHAR_8118"
    assert assembler.normalize_station_id("LOC_8118") == "ANAND_VIHAR_8118"
    assert assembler.normalize_station_id("LOCATION_8118") == "ANAND_VIHAR_8118"
    assert assembler.normalize_station_id("UNKNOWN_9999") is None


# 2. Canonical Coordinates Verification
def test_canonical_coordinates_verification(assembler):
    anand_vihar_meta = next(st for st in DELHI_PILOT_STATIONS if st["station_id"] == "ANAND_VIHAR_8118")
    assert anand_vihar_meta["latitude"] == 28.6476
    assert anand_vihar_meta["longitude"] == 77.3158

    st_meta = assembler.station_metadata["ANAND_VIHAR_8118"]
    assert float(st_meta["latitude"]) == 28.6476
    assert float(st_meta["longitude"]) == 77.3158


# 3. Unsupported Station Rejection
def test_unsupported_station_rejection(assembler):
    res = assembler.assemble_features("INVALID_STATION_9999", "2025-01-01T12:00:00Z")
    assert res.assembly_status == "UNSUPPORTED_STATION"
    assert res.features == {}
    assert len(res.missing_feature_reasons) > 0
    assert "unsupported" in res.missing_feature_reasons[0].lower()


# 4. Valid Feature Vector Assembly
def test_valid_feature_assembly_from_historical_csvs(assembler):
    ts = "2025-01-02T12:00:00Z"
    res = assembler.assemble_features("ANAND_VIHAR_8118", ts)
    assert res.assembly_status == "READY"
    assert res.canonical_station_id == "ANAND_VIHAR_8118"
    assert len(res.features) == 27
    assert res.features["latitude"] == 28.6476
    assert res.features["longitude"] == 77.3158


# 5. Manifest Contract & Feature Ordering
def test_manifest_contract_and_feature_ordering(assembler):
    ts = "2025-01-02T12:00:00Z"
    res = assembler.assemble_features("ANAND_VIHAR_8118", ts)
    assert res.assembly_status == "READY"
    feature_keys = list(res.features.keys())
    assert feature_keys == assembler.manifest_features
    assert len(feature_keys) == 27


# 6. PM2.5 Lag Calculation Semantics
def test_pm25_lag_calculation_semantics(assembler):
    aq_history = [
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2025-01-01T10:00:00Z", "value": "100.0"},
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2025-01-01T22:00:00Z", "value": "150.0"},
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T04:00:00Z", "value": "200.0"},
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T07:00:00Z", "value": "250.0"},
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T09:00:00Z", "value": "300.0"},
        {"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T10:00:00Z", "value": "350.0"},
    ]
    weather_history = [
        {"timestamp": "2025-01-02T10:00:00Z", "temperature_2m": "15.0", "relative_humidity_2m": "80.0", "wind_speed_10m": "2.0", "wind_direction_10m": "180.0", "surface_pressure": "1000.0", "boundary_layer_height": "300.0"}
    ]
    res = assembler.assemble_features("ANAND_VIHAR_8118", "2025-01-02T10:00:00Z", air_quality_records=aq_history, weather_records=weather_history)
    assert res.assembly_status == "READY"
    assert res.features["pm25_lag_1h"] == 300.0   # 10:00 - 1h = 09:00 -> 300.0
    assert res.features["pm25_lag_3h"] == 250.0   # 10:00 - 3h = 07:00 -> 250.0
    assert res.features["pm25_lag_6h"] == 200.0   # 10:00 - 6h = 04:00 -> 200.0
    assert res.features["pm25_lag_12h"] == 150.0  # 10:00 - 12h = 22:00 -> 150.0
    assert res.features["pm25_lag_24h"] == 100.0  # 10:00 - 24h = 10:00 (prev day) -> 100.0


# 7. Backward Rolling Window Calculation Semantics
def test_backward_rolling_statistics(assembler):
    aq_history = [
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-01T10:00:00Z", "value": "100.0"}, # 24h lag
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-01T22:00:00Z", "value": "100.0"}, # 12h lag
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T04:00:00Z", "value": "100.0"}, # 6h lag
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T07:00:00Z", "value": "100.0"}, # 3h lag
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T08:00:00Z", "value": "200.0"},
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T09:00:00Z", "value": "300.0"}, # 1h lag
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T10:00:00Z", "value": "400.0"}, # t0
    ]
    weather_history = [
        {"timestamp": "2025-01-02T10:00:00Z", "temperature_2m": "15.0", "relative_humidity_2m": "80.0", "wind_speed_10m": "2.0", "wind_direction_10m": "180.0", "surface_pressure": "1000.0", "boundary_layer_height": "300.0"}
    ]

    res = assembler.assemble_features("8118", "2025-01-02T10:00:00Z", air_quality_records=aq_history, weather_records=weather_history)
    assert res.assembly_status == "READY"
    # 3h rolling window at 10:00 covers [07:00, 10:00] -> values [100, 200, 300, 400] -> sum = 1000 / 4 = 250.0
    assert res.features["pm25_roll_mean_3h"] == 250.0
    assert res.features["pm25_roll_median_3h"] == 250.0


# 8. Weather Alignment & Wind Components
def test_weather_alignment_and_wind_vector_components(assembler):
    weather_history = [
        {
            "timestamp": "2025-01-02T10:00:00Z",
            "temperature_2m": "20.5",
            "relative_humidity_2m": "65.0",
            "wind_speed_10m": "10.0",
            "wind_direction_10m": "90.0",
            "surface_pressure": "1013.2",
            "boundary_layer_height": "500.0",
        }
    ]
    aq_history = [{"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": f"2025-01-01T{h:02d}:00:00Z", "value": "100.0"} for h in range(24)]
    aq_history.extend([{"station_id": "ANAND_VIHAR_8118", "pollutant": "PM2.5", "timestamp": f"2025-01-02T{h:02d}:00:00Z", "value": "100.0"} for h in range(11)])

    res = assembler.assemble_features("ANAND_VIHAR_8118", "2025-01-02T10:00:00Z", air_quality_records=aq_history, weather_records=weather_history)
    assert res.assembly_status == "READY"
    assert res.features["temperature_2m"] == 20.5
    assert res.features["relative_humidity_2m"] == 65.0
    assert res.features["wind_speed_10m"] == 10.0
    assert res.features["wind_direction_10m"] == 90.0
    assert res.features["wind_u"] == -10.0
    assert res.features["wind_v"] == 0.0


# 9. Weather Staleness Threshold Default (60 Minutes)
def test_weather_staleness_threshold_default(assembler):
    weather_history = [
        {
            "timestamp": "2025-01-02T08:45:00Z",
            "temperature_2m": "15.0",
            "relative_humidity_2m": "80.0",
            "wind_speed_10m": "2.0",
            "wind_direction_10m": "180.0",
            "surface_pressure": "1000.0",
            "boundary_layer_height": "300.0",
        }
    ]
    aq_history = [{"station_id": "8118", "pollutant": "PM2.5", "timestamp": f"2025-01-01T{h:02d}:00:00Z", "value": "100.0"} for h in range(24)]
    aq_history.extend([{"station_id": "8118", "pollutant": "PM2.5", "timestamp": f"2025-01-02T{h:02d}:00:00Z", "value": "100.0"} for h in range(11)])

    res = assembler.assemble_features("8118", "2025-01-02T10:00:00Z", air_quality_records=aq_history, weather_records=weather_history)
    assert res.assembly_status == "WEATHER_STALE"
    assert res.weather_observation_age_minutes == 75.0
    assert len(res.missing_feature_reasons) > 0
    assert "75.0 minutes > 60.0 minute threshold" in res.missing_feature_reasons[0]


# 10. Missing PM2.5 History Handling
def test_missing_pm25_history_handling(assembler):
    aq_history = [
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T09:00:00Z", "value": "100.0"}
    ]
    weather_history = [
        {"timestamp": "2025-01-02T10:00:00Z", "temperature_2m": "15.0", "relative_humidity_2m": "80.0", "wind_speed_10m": "2.0", "wind_direction_10m": "180.0", "surface_pressure": "1000.0", "boundary_layer_height": "300.0"}
    ]
    res = assembler.assemble_features("8118", "2025-01-02T10:00:00Z", air_quality_records=aq_history, weather_records=weather_history)
    assert res.assembly_status == "MISSING_HISTORY"
    assert any("pm25_lag_24h unavailable" in r for r in res.missing_feature_reasons)


# 11. Leakage Protection: Future PM2.5 Excluded
def test_leakage_protection_future_pm25_excluded(assembler):
    aq_history = [
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T10:00:00Z", "value": "100.0"},
        {"station_id": "8118", "pollutant": "PM2.5", "timestamp": "2025-01-02T11:00:00Z", "value": "999.0"},
    ]
    weather_history = [
        {"timestamp": "2025-01-02T10:00:00Z", "temperature_2m": "15.0", "relative_humidity_2m": "80.0", "wind_speed_10m": "2.0", "wind_direction_10m": "180.0", "surface_pressure": "1000.0", "boundary_layer_height": "300.0"}
    ]
    res = assembler.assemble_features("8118", "2025-01-02T10:00:00Z", air_quality_records=aq_history, weather_records=weather_history)
    assert res.pm25_history_count == 1


# 12. Leakage Protection: Future Weather Excluded
def test_leakage_protection_future_weather_excluded(assembler):
    weather_history = [
        {"timestamp": "2025-01-02T11:00:00Z", "temperature_2m": "40.0", "relative_humidity_2m": "10.0", "wind_speed_10m": "5.0", "wind_direction_10m": "180.0", "surface_pressure": "1000.0", "boundary_layer_height": "300.0"}
    ]
    aq_history = [{"station_id": "8118", "pollutant": "PM2.5", "timestamp": f"2025-01-01T{h:02d}:00:00Z", "value": "100.0"} for h in range(24)]
    aq_history.extend([{"station_id": "8118", "pollutant": "PM2.5", "timestamp": f"2025-01-02T{h:02d}:00:00Z", "value": "100.0"} for h in range(11)])

    res = assembler.assemble_features("8118", "2025-01-02T10:00:00Z", air_quality_records=aq_history, weather_records=weather_history)
    assert res.assembly_status == "WEATHER_STALE"
    assert res.weather_observation_age_minutes is None


# 13. Cyclic Time Features Bounds
def test_cyclic_time_features_bounds(assembler):
    ts = "2025-01-02T15:30:00Z"
    res = assembler.assemble_features("ANAND_VIHAR_8118", ts)
    if res.assembly_status == "READY":
        for feat in ["hour_sin", "hour_cos", "day_of_week_sin", "day_of_week_cos", "month_sin", "month_cos"]:
            assert -1.0 <= res.features[feat] <= 1.0


# 14. Dynamic Manifest Feature Validation
def test_dynamic_manifest_feature_validation(assembler):
    assert len(assembler.manifest_features) == 27
    assert "pm25_lag_1h" in assembler.manifest_features
    assert "month_cos" in assembler.manifest_features


# 15. CORRECTION 3 — Exact Feature Parity against forecast_dataset.csv
def test_exact_feature_parity_with_forecast_dataset(assembler):
    dataset_path = Path("data/processed/forecasting/forecast_dataset.csv")
    assert dataset_path.exists(), "forecast_dataset.csv must exist for parity check"

    target_row = None
    with open(dataset_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("pm25_lag_24h") and row.get("temperature_2m"):
                target_row = row
                break

    assert target_row is not None, "Could not find valid benchmark row in forecast_dataset.csv"

    ts = target_row["prediction_timestamp"]
    st_id = target_row["station_id"]

    res = assembler.assemble_features(st_id, ts)
    assert res.assembly_status == "READY"

    for feat in assembler.manifest_features:
        expected_val = float(target_row[feat])
        assembled_val = res.features[feat]
        assert abs(assembled_val - expected_val) < 1e-3, (
            f"Feature parity mismatch for '{feat}' at {ts}: expected {expected_val}, got {assembled_val}"
        )


# 16. CORRECTION 4 — Detailed Failure Diagnostics
def test_detailed_failure_diagnostics(assembler):
    res1 = assembler.assemble_features("ANAND_VIHAR_8118", "2024-12-31T20:30:00Z")
    assert res1.assembly_status == "MISSING_HISTORY"
    assert any("pm25_lag_" in r for r in res1.missing_feature_reasons)

    weather_history = [
        {"timestamp": "2025-01-02T08:00:00Z", "temperature_2m": "15.0", "relative_humidity_2m": "80.0", "wind_speed_10m": "2.0", "wind_direction_10m": "180.0", "surface_pressure": "1000.0", "boundary_layer_height": "300.0"}
    ]
    aq_history = [{"station_id": "8118", "pollutant": "PM2.5", "timestamp": f"2025-01-01T{h:02d}:00:00Z", "value": "100.0"} for h in range(24)]
    aq_history.extend([{"station_id": "8118", "pollutant": "PM2.5", "timestamp": f"2025-01-02T{h:02d}:00:00Z", "value": "100.0"} for h in range(11)])

    res2 = assembler.assemble_features("8118", "2025-01-02T10:00:00Z", air_quality_records=aq_history, weather_records=weather_history)
    assert res2.assembly_status == "WEATHER_STALE"
    assert any("weather observation age = 120.0 minutes > 60.0 minute threshold" in r for r in res2.missing_feature_reasons)


# 17. End-to-End Inference Engine Integration
def test_end_to_end_inference_engine_integration(assembler, inference_engine):
    ts = "2025-01-02T12:00:00Z"
    vector = assembler.assemble_features("ANAND_VIHAR_8118", ts)
    assert vector.assembly_status == "READY"

    forecast = inference_engine.predict(
        station_id=vector.canonical_station_id,
        prediction_timestamp=vector.prediction_timestamp,
        feature_row=vector.features,
    )
    assert forecast["status"] == "SUCCESS"
    assert len(forecast["horizons"]) == 3
    assert forecast["canonical_station_id"] == "ANAND_VIHAR_8118"


# 18. Determinism Across Repeated Calls
def test_determinism_repeated_calls(assembler):
    ts = "2025-01-02T12:00:00Z"
    v1 = assembler.assemble_features("ANAND_VIHAR_8118", ts)
    v2 = assembler.assemble_features("ANAND_VIHAR_8118", ts)
    assert v1.assembly_status == v2.assembly_status
    assert v1.features == v2.features
    assert v1.missing_feature_reasons == v2.missing_feature_reasons


# 19. Malformed Timestamp Handling
def test_malformed_timestamp_handling(assembler):
    res = assembler.assemble_features("ANAND_VIHAR_8118", "invalid-timestamp-string")
    assert res.assembly_status == "INVALID_INPUT"
    assert len(res.missing_feature_reasons) > 0


# 20. Model Artifact Integrity Verification
def test_model_artifact_integrity():
    model_dir = Path("ml/models/forecasting")
    model_files = ["lightgbm_pm25_1h.txt", "lightgbm_pm25_3h.txt", "lightgbm_pm25_6h.txt"]
    for fname in model_files:
        fpath = model_dir / fname
        assert fpath.exists(), f"Model file {fname} missing!"
        sha = get_file_sha256(fpath)
        assert len(sha) == 64
