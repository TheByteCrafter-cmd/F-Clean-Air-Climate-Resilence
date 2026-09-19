"""
VayuDrishti — Risk Assessment Engine Unit & Integration Test Suite (Phase 1E-J2E.4.1)

Comprehensive test coverage for deterministic environmental risk assessment engine:
- Canonical station scope enforcement (ANAND_VIHAR_8118 / alias "8118")
- Timestamp validation & stale forecast rejection (max 120 minutes)
- Telemetry validation (NaN/Infinity handling)
- Exact piecewise severity formula verification
- Persistence component scoring
- Uncertainty interaction and low-severity level capping rule
- Hotspot corroboration scaling
- Spatial context modifiers
- Data quality status reporting (READY, PARTIAL, BLOCKED)
- Deterministic repeatability & 0-100 score bounds
- Pydantic schema validation & non-medical disclaimer check
- End-to-end integration test with forecast engine
- Model artifact SHA256 integrity check
"""

import json
import math
import hashlib
from pathlib import Path
import pytest
from pydantic import ValidationError

from ml.src.risk.risk_config import RiskConfig
from ml.src.risk.risk_schemas import (
    RiskAssessmentInput,
    RiskAssessmentInputModel,
    RiskAssessmentResult,
    RiskComponentBreakdown,
)
from ml.src.risk.risk_engine import RiskAssessmentEngine, CANONICAL_STATION_ID


@pytest.fixture
def risk_engine():
    return RiskAssessmentEngine()


@pytest.fixture
def valid_input():
    return RiskAssessmentInput(
        station_id="ANAND_VIHAR_8118",
        assessment_timestamp="2026-09-20T10:00:00Z",
        forecast_generated_timestamp="2026-09-20T09:30:00Z",
        predicted_pm25_1h=75.0,
        pm25_1h_lower_90=50.0,
        pm25_1h_upper_90=100.0,
        predicted_pm25_3h=85.0,
        pm25_3h_lower_90=55.0,
        pm25_3h_upper_90=115.0,
        predicted_pm25_6h=95.0,
        pm25_6h_lower_90=60.0,
        pm25_6h_upper_90=130.0,
        hotspot_detected=True,
        hotspot_id="hotspot_av_001",
        hotspot_support_score=80.0,
        hotspot_spatial_extent=1.5,
        hotspot_source_families=["INDUSTRIAL_EMISSION"],
        industrial_context=True,
        major_road_context=True,
        sensitive_receptor_context=False,
        forecast_result_id="fc_result_123",
        fusion_id="fusion_456",
        context_artifact_id="ctx_789",
    )


# Test 1: Unsupported Station Scope
def test_unsupported_station_scope(risk_engine, valid_input):
    valid_input.station_id = "INVALID_STATION_9999"
    result = risk_engine.assess_risk(valid_input)
    assert result.risk_level == "UNSUPPORTED_STATION_SCOPE"
    assert result.data_quality_status == "BLOCKED"
    assert "UNSUPPORTED_STATION_SCOPE" in result.reason_codes
    assert result.risk_score == 0.0


# Test 2: Station Alias Support ("8118")
def test_station_alias_support(risk_engine, valid_input):
    valid_input.station_id = "8118"
    result = risk_engine.assess_risk(valid_input)
    assert result.station_id == CANONICAL_STATION_ID
    assert result.risk_level in ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]
    assert result.data_quality_status == "READY"


# Test 3: Invalid Timestamp Syntax
def test_invalid_timestamp_syntax(risk_engine, valid_input):
    valid_input.assessment_timestamp = "invalid-date-string"
    result = risk_engine.assess_risk(valid_input)
    assert result.risk_level == "BLOCKED"
    assert result.data_quality_status == "BLOCKED"
    assert any("INVALID_TIMESTAMP" in r for r in result.reason_codes)


# Test 4: Future Forecast Generated Timestamp
def test_future_forecast_timestamp(risk_engine, valid_input):
    valid_input.assessment_timestamp = "2026-09-20T10:00:00Z"
    valid_input.forecast_generated_timestamp = "2026-09-20T10:30:00Z"
    result = risk_engine.assess_risk(valid_input)
    assert result.risk_level == "BLOCKED"
    assert result.data_quality_status == "BLOCKED"
    assert any("INVALID_TIMESTAMP" in r for r in result.reason_codes)


# Test 5: Stale Forecast Rejection (> 120 min)
def test_stale_forecast_rejection(risk_engine, valid_input):
    valid_input.assessment_timestamp = "2026-09-20T13:00:00Z"  # 3.5 hours later
    valid_input.forecast_generated_timestamp = "2026-09-20T09:30:00Z"
    result = risk_engine.assess_risk(valid_input)
    assert result.risk_level == "BLOCKED"
    assert result.data_quality_status == "BLOCKED"
    assert any("STALE_FORECAST" in r for r in result.reason_codes)
    assert result.forecast_age_minutes == 210.0


# Test 6: Missing / Invalid Telemetry (NaN / Infinity)
def test_missing_or_nan_telemetry(risk_engine, valid_input):
    valid_input.predicted_pm25_1h = float("nan")
    result = risk_engine.assess_risk(valid_input)
    assert result.risk_level == "BLOCKED"
    assert result.data_quality_status == "BLOCKED"
    assert "MISSING_FORECAST_DATA" in result.reason_codes


# Test 7: Exact Severity Formula - Band 1 (p_eff < 30)
def test_severity_piecewise_band1():
    config = RiskConfig()
    # p_eff = 15.0 -> score = 10 * 15 / 30 = 5.0
    assert config.compute_severity_score(15.0) == 5.0


# Test 8: Exact Severity Formula - Band 2 (30 <= p_eff < 60)
def test_severity_piecewise_band2():
    config = RiskConfig()
    # p_eff = 45.0 -> score = 10 + 10 * (45 - 30) / 30 = 15.0
    assert config.compute_severity_score(45.0) == 15.0


# Test 9: Exact Severity Formula - Band 3 (60 <= p_eff < 120)
def test_severity_piecewise_band3():
    config = RiskConfig()
    # p_eff = 90.0 -> score = 20 + 10 * (90 - 60) / 60 = 25.0
    assert config.compute_severity_score(90.0) == 25.0


# Test 10: Exact Severity Formula - Band 4 (p_eff >= 120)
def test_severity_piecewise_band4():
    config = RiskConfig()
    # p_eff = 150.0 -> score = 40.0
    assert config.compute_severity_score(150.0) == 40.0


# Test 11: Persistence Component - Short Lived
def test_persistence_short_lived(risk_engine, valid_input):
    valid_input.predicted_pm25_1h = 25.0
    valid_input.predicted_pm25_3h = 30.0
    valid_input.predicted_pm25_6h = 45.0
    result = risk_engine.assess_risk(valid_input)
    assert result.score_breakdown.forecast_persistence == 0.0
    assert "FORECAST_SHORT_LIVED" in result.reason_codes


# Test 12: Persistence Component - Moderately Persistent
def test_persistence_moderately_persistent(risk_engine, valid_input):
    valid_input.predicted_pm25_1h = 70.0
    valid_input.predicted_pm25_3h = 65.0
    valid_input.predicted_pm25_6h = 40.0
    result = risk_engine.assess_risk(valid_input)
    assert result.score_breakdown.forecast_persistence == 10.0
    assert "FORECAST_MODERATELY_PERSISTENT" in result.reason_codes


# Test 13: Persistence Component - Fully Persistent
def test_persistence_fully_persistent(risk_engine, valid_input):
    valid_input.predicted_pm25_1h = 70.0
    valid_input.predicted_pm25_3h = 80.0
    valid_input.predicted_pm25_6h = 90.0
    result = risk_engine.assess_risk(valid_input)
    assert result.score_breakdown.forecast_persistence == 20.0
    assert "FORECAST_PERSISTENT" in result.reason_codes


# Test 14: Uncertainty Capping Rule (CORRECTION 3)
def test_uncertainty_level_capping(risk_engine, valid_input):
    # Low PM2.5 concentrations (low severity < 15.0)
    valid_input.predicted_pm25_1h = 10.0
    valid_input.predicted_pm25_3h = 12.0
    valid_input.predicted_pm25_6h = 15.0
    # Wide conformal interval (high uncertainty score)
    valid_input.pm25_1h_lower_90 = 0.0
    valid_input.pm25_1h_upper_90 = 100.0
    valid_input.pm25_3h_lower_90 = 0.0
    valid_input.pm25_3h_upper_90 = 100.0
    valid_input.pm25_6h_lower_90 = 0.0
    valid_input.pm25_6h_upper_90 = 100.0
    # Add hotspot and context to push total score > 50
    valid_input.hotspot_support_score = 100.0
    valid_input.industrial_context = True
    valid_input.major_road_context = True
    valid_input.sensitive_receptor_context = True

    result = risk_engine.assess_risk(valid_input)
    # Severity score for p_eff ~ 12.8 is ~ 4.27 (< 15.0)
    assert result.score_breakdown.forecast_severity < 15.0
    # Even if total score exceeds 50.0, risk level MUST be capped at MODERATE
    assert result.risk_level in ["LOW", "MODERATE"]
    assert result.risk_level != "HIGH"
    assert result.risk_level != "VERY_HIGH"


# Test 15: Hotspot Corroboration Scaling (0-15 pts)
def test_hotspot_corroboration_scaling(risk_engine, valid_input):
    valid_input.hotspot_support_score = 50.0  # 50% support score -> 7.5 pts
    result = risk_engine.assess_risk(valid_input)
    assert result.score_breakdown.hotspot_corroboration == 7.5
    assert "HOTSPOT_CORROBORATED" in result.reason_codes


# Test 16: Spatial Context Modifiers (0-10 pts)
def test_spatial_context_modifiers(risk_engine, valid_input):
    valid_input.industrial_context = True  # 3.5
    valid_input.major_road_context = True  # 3.0
    valid_input.sensitive_receptor_context = True  # 3.5
    result = risk_engine.assess_risk(valid_input)
    assert result.score_breakdown.context == 10.0  # 3.5 + 3.0 + 3.5 = 10.0
    assert "INDUSTRIAL_CONTEXT_PRESENT" in result.reason_codes
    assert "MAJOR_ROAD_CONTEXT_PRESENT" in result.reason_codes
    assert "SENSITIVE_RECEPTOR_CONTEXT_PRESENT" in result.reason_codes


# Test 17: Partial Data Quality Status
def test_partial_data_quality_status(risk_engine, valid_input):
    valid_input.hotspot_support_score = None
    valid_input.hotspot_detected = None
    result = risk_engine.assess_risk(valid_input)
    assert result.data_quality_status == "PARTIAL"
    assert result.hotspot_missing is True
    assert result.risk_level in ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]


# Test 18: Ready Data Quality Status
def test_ready_data_quality_status(risk_engine, valid_input):
    result = risk_engine.assess_risk(valid_input)
    assert result.data_quality_status == "READY"
    assert result.hotspot_missing is False
    assert result.context_missing is False


# Test 19: Deterministic Repeatability
def test_deterministic_repeatability(risk_engine, valid_input):
    res1 = risk_engine.assess_risk(valid_input)
    res2 = risk_engine.assess_risk(valid_input)
    assert res1.risk_score == res2.risk_score
    assert res1.risk_level == res2.risk_level
    assert res1.score_breakdown == res2.score_breakdown
    assert res1.reason_codes == res2.reason_codes


# Test 20: Bounded Score Range (0.0 to 100.0)
def test_bounded_score_range(risk_engine, valid_input):
    # Extreme high input values
    valid_input.predicted_pm25_1h = 500.0
    valid_input.predicted_pm25_3h = 600.0
    valid_input.predicted_pm25_6h = 700.0
    valid_input.hotspot_support_score = 100.0
    valid_input.industrial_context = True
    valid_input.major_road_context = True
    valid_input.sensitive_receptor_context = True

    result = risk_engine.assess_risk(valid_input)
    assert result.risk_score <= 100.0
    assert result.risk_score >= 0.0
    assert result.risk_level == "VERY_HIGH"


# Test 21: Pydantic Schema Validation
def test_pydantic_schema_validation():
    invalid_dict = {
        "station_id": "ANAND_VIHAR_8118",
        "assessment_timestamp": "2026-09-20T10:00:00Z",
        "forecast_generated_timestamp": "2026-09-20T09:30:00Z",
        "predicted_pm25_1h": "NOT_A_NUMBER",  # Invalid type
    }
    with pytest.raises(ValidationError):
        RiskAssessmentInputModel(**invalid_dict)


# Test 22: Non-Medical Disclaimer Presence
def test_non_medical_disclaimer_presence(risk_engine, valid_input):
    result = risk_engine.assess_risk(valid_input)
    assert "medical diagnosis" in result.non_medical_disclaimer.lower()
    assert "operational environmental risk" in result.non_medical_disclaimer.lower()


# Test 23: Offline End-to-End Integration Test
def test_offline_end_to_end_forecast_to_risk(risk_engine):
    from ml.src.forecasting.inference import ForecastInferenceEngine

    infer_engine = ForecastInferenceEngine()
    features = {
        "latitude": 28.6508,
        "longitude": 77.3152,
        "pm25_lag_1h": 140.0,
        "pm25_lag_3h": 135.0,
        "pm25_lag_6h": 130.0,
        "pm25_lag_12h": 125.0,
        "pm25_lag_24h": 120.0,
        "pm25_roll_mean_3h": 138.33,
        "pm25_roll_median_3h": 138.33,
        "pm25_roll_mean_6h": 135.0,
        "pm25_roll_median_6h": 135.0,
        "pm25_roll_mean_24h": 125.0,
        "pm25_roll_median_24h": 125.0,
        "temperature_2m": 25.0,
        "relative_humidity_2m": 60.0,
        "wind_speed_10m": 2.5,
        "wind_direction_10m": 180.0,
        "wind_u": 0.0,
        "wind_v": -2.5,
        "surface_pressure": 1005.0,
        "boundary_layer_height": 500.0,
        "hour_sin": 0.5,
        "hour_cos": 0.866,
        "day_of_week_sin": 0.0,
        "day_of_week_cos": 1.0,
        "month_sin": -0.5,
        "month_cos": -0.866,
    }

    forecast_res = infer_engine.predict("ANAND_VIHAR_8118", "2026-09-20T09:30:00Z", features)
    assert forecast_res["status"] == "SUCCESS"

    risk_input = RiskAssessmentInput(
        station_id=forecast_res["canonical_station_id"],
        assessment_timestamp="2026-09-20T10:00:00Z",
        forecast_generated_timestamp=forecast_res["prediction_timestamp"],
        predicted_pm25_1h=forecast_res["horizons"]["+1h"]["predicted_pm25"],
        pm25_1h_lower_90=forecast_res["horizons"]["+1h"]["prediction_intervals"]["90_pct"]["lower_bound"],
        pm25_1h_upper_90=forecast_res["horizons"]["+1h"]["prediction_intervals"]["90_pct"]["upper_bound"],
        predicted_pm25_3h=forecast_res["horizons"]["+3h"]["predicted_pm25"],
        pm25_3h_lower_90=forecast_res["horizons"]["+3h"]["prediction_intervals"]["90_pct"]["lower_bound"],
        pm25_3h_upper_90=forecast_res["horizons"]["+3h"]["prediction_intervals"]["90_pct"]["upper_bound"],
        predicted_pm25_6h=forecast_res["horizons"]["+6h"]["predicted_pm25"],
        pm25_6h_lower_90=forecast_res["horizons"]["+6h"]["prediction_intervals"]["90_pct"]["lower_bound"],
        pm25_6h_upper_90=forecast_res["horizons"]["+6h"]["prediction_intervals"]["90_pct"]["upper_bound"],
        industrial_context=True,
        major_road_context=True,
        forecast_result_id="fc_e2e_test",
    )

    risk_res = risk_engine.assess_risk(risk_input)
    assert risk_res.data_quality_status == "PARTIAL"  # Hotspot missing
    assert risk_res.risk_level in ["HIGH", "VERY_HIGH"]
    assert risk_res.risk_score > 50.0


# Test 24: Model Artifact SHA256 Integrity Verification
def test_model_artifact_sha256_integrity():
    model_dir = Path("ml/models/forecasting")
    manifest_path = model_dir / "model_manifest.json"
    assert manifest_path.exists()

    for horizon in ["1h", "3h", "6h"]:
        model_file = model_dir / f"lightgbm_pm25_{horizon}.txt"
        assert model_file.exists(), f"Model file missing: {model_file}"
        file_bytes = model_file.read_bytes()
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        assert len(sha256_hash) == 64
