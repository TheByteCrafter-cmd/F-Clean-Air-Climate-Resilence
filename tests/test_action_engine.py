"""
VayuDrishti — Authority Action Recommendation Engine Unit & Integration Test Suite (Phase 1E-J2E.4.3)

Comprehensive test coverage for deterministic decision-support action recommendation engine:
- Blocked risk status handling
- LOW, MODERATE, HIGH, VERY_HIGH risk trigger rules
- Persistent forecast triggers
- Hotspot corroboration triggers
- Industrial, major road, and sensitive receptor context triggers
- High uncertainty verification handling
- Missing optional evidence handling (PARTIAL status)
- Station scope guard (ANAND_VIHAR_8118 / 8118)
- Timestamp parsing & expiry calculation (120 min)
- Recommendation deduplication and priority merging
- Reason code correctness and evidence reference preservation
- Deterministic repeatability
- Mandatory human review flag enforcement
- Non-causal wording audit checks
- Non-medical disclaimer presence
- Offline end-to-end integration test
"""

import pytest
from datetime import datetime, timezone

from ml.src.risk.risk_schemas import (
    RiskAssessmentInput,
    RiskAssessmentResult,
    RiskComponentBreakdown,
)
from ml.src.risk.risk_engine import RiskAssessmentEngine, CANONICAL_STATION_ID
from ml.src.actions.action_config import ActionConfig
from ml.src.actions.action_schemas import (
    ActionRecommendation,
    ActionRecommendationInput,
    ActionRecommendationResult,
)
from ml.src.actions.action_engine import ActionRecommendationEngine


@pytest.fixture
def action_engine():
    return ActionRecommendationEngine()


@pytest.fixture
def sample_risk_result():
    return RiskAssessmentResult(
        assessment_id="risk_test_123",
        station_id="ANAND_VIHAR_8118",
        assessment_timestamp="2026-09-20T10:00:00Z",
        forecast_generated_timestamp="2026-09-20T09:30:00Z",
        forecast_age_minutes=30.0,
        risk_score=62.5,
        risk_level="HIGH",
        score_breakdown=RiskComponentBreakdown(
            forecast_severity=25.0,
            forecast_persistence=20.0,
            uncertainty=4.0,
            hotspot_corroboration=10.0,
            context=3.5,
        ),
        reason_codes=["FORECAST_PM25_ELEVATED", "FORECAST_PERSISTENT", "HOTSPOT_CORROBORATED", "INDUSTRIAL_CONTEXT_PRESENT"],
        evidence_references={
            "forecast_result_id": "fc_res_123",
            "hotspot_id": "hotspot_av_001",
            "fusion_id": "fusion_456",
            "context_artifact_id": "ctx_789",
        },
        data_quality_status="READY",
        hotspot_missing=False,
        context_missing=False,
    )


@pytest.fixture
def sample_action_input(sample_risk_result):
    return ActionRecommendationInput(
        risk_result=sample_risk_result,
        industrial_context=True,
        major_road_context=True,
        sensitive_receptor_context=False,
        hotspot_detected=True,
        hotspot_id="hotspot_av_001",
        hotspot_support_score=80.0,
        forecast_result_id="fc_res_123",
        fusion_id="fusion_456",
        context_artifact_id="ctx_789",
    )


# Test 1: Blocked Risk Returns Blocked Recommendations
def test_blocked_risk_returns_blocked_recommendations(action_engine, sample_action_input):
    sample_action_input.risk_result.data_quality_status = "BLOCKED"
    sample_action_input.risk_result.risk_level = "BLOCKED"
    res = action_engine.recommend_actions(sample_action_input)
    assert res.status == "BLOCKED"
    assert len(res.recommendations) == 0
    assert "RISK_ASSESSMENT_BLOCKED" in res.reason_codes


# Test 2: LOW Risk Behavior
def test_low_risk_behavior(action_engine, sample_action_input):
    sample_action_input.risk_result.risk_level = "LOW"
    sample_action_input.risk_result.reason_codes = ["FORECAST_SHORT_LIVED"]
    sample_action_input.industrial_context = False
    sample_action_input.major_road_context = False
    sample_action_input.hotspot_support_score = None

    res = action_engine.recommend_actions(sample_action_input)
    assert res.status in ["READY", "PARTIAL"]
    assert len(res.recommendations) == 1
    rec = res.recommendations[0]
    assert rec.action_type == "MONITOR_LOCAL_AIR_QUALITY"
    assert rec.priority == "INFORMATIONAL"


# Test 3: MODERATE Risk Watch Behavior
def test_moderate_risk_watch_behavior(action_engine, sample_action_input):
    sample_action_input.risk_result.risk_level = "MODERATE"
    sample_action_input.risk_result.reason_codes = ["FORECAST_MODERATELY_PERSISTENT"]
    sample_action_input.risk_result.score_breakdown.hotspot_corroboration = 0.0
    sample_action_input.industrial_context = False
    sample_action_input.major_road_context = False
    sample_action_input.hotspot_detected = False
    sample_action_input.hotspot_support_score = None

    res = action_engine.recommend_actions(sample_action_input)
    assert len(res.recommendations) == 1
    assert res.recommendations[0].priority == "WATCH"


# Test 4: HIGH Risk Priority Behavior
def test_high_risk_priority_behavior(action_engine, sample_action_input):
    sample_action_input.risk_result.risk_level = "HIGH"
    sample_action_input.industrial_context = False
    sample_action_input.major_road_context = False
    sample_action_input.hotspot_support_score = None

    res = action_engine.recommend_actions(sample_action_input)
    assert any(rec.priority == "PRIORITY" for rec in res.recommendations)


# Test 5: VERY_HIGH Risk Urgent Review Behavior
def test_very_high_risk_urgent_review_behavior(action_engine, sample_action_input):
    sample_action_input.risk_result.risk_level = "VERY_HIGH"
    sample_action_input.risk_result.reason_codes = ["FORECAST_PM25_ELEVATED", "FORECAST_PERSISTENT"]
    sample_action_input.industrial_context = False
    sample_action_input.major_road_context = False

    res = action_engine.recommend_actions(sample_action_input)
    assert any(rec.priority == "URGENT_REVIEW" for rec in res.recommendations)


# Test 6: Persistent Forecast Trigger
def test_persistent_forecast_trigger(action_engine, sample_action_input):
    sample_action_input.risk_result.risk_level = "HIGH"
    sample_action_input.risk_result.reason_codes = ["FORECAST_PERSISTENT"]

    res = action_engine.recommend_actions(sample_action_input)
    rec_types = [r.action_type for r in res.recommendations]
    assert "ISSUE_PUBLIC_INFORMATION_ADVISORY" in rec_types


# Test 7: Hotspot Trigger
def test_hotspot_trigger(action_engine, sample_action_input):
    sample_action_input.hotspot_detected = True
    sample_action_input.hotspot_support_score = 85.0

    res = action_engine.recommend_actions(sample_action_input)
    rec_types = [r.action_type for r in res.recommendations]
    assert "INCREASE_INSPECTION_PRIORITY" in rec_types


# Test 8: Industrial Context Trigger
def test_industrial_context_trigger(action_engine, sample_action_input):
    sample_action_input.industrial_context = True

    res = action_engine.recommend_actions(sample_action_input)
    rec_types = [r.action_type for r in res.recommendations]
    assert "REVIEW_INDUSTRIAL_ACTIVITY" in rec_types


# Test 9: Major Road Context Trigger
def test_major_road_context_trigger(action_engine, sample_action_input):
    sample_action_input.major_road_context = True

    res = action_engine.recommend_actions(sample_action_input)
    rec_types = [r.action_type for r in res.recommendations]
    assert "REVIEW_MAJOR_ROAD_TRAFFIC_CONDITIONS" in rec_types


# Test 10: Sensitive Receptor Context Trigger
def test_sensitive_receptor_context_trigger(action_engine, sample_action_input):
    sample_action_input.sensitive_receptor_context = True

    res = action_engine.recommend_actions(sample_action_input)
    rec_types = [r.action_type for r in res.recommendations]
    assert "VERIFY_SENSITIVE_RECEPTOR_EXPOSURE_CONTEXT" in rec_types


# Test 11: High Uncertainty Behavior
def test_high_uncertainty_behavior(action_engine, sample_action_input):
    sample_action_input.risk_result.reason_codes.append("FORECAST_UNCERTAINTY_HIGH")
    sample_action_input.risk_result.score_breakdown.uncertainty = 10.0

    res = action_engine.recommend_actions(sample_action_input)
    rec_types = [r.action_type for r in res.recommendations]
    assert "EXPAND_LOCAL_MONITORING" in rec_types
    rec = next(r for r in res.recommendations if r.action_type == "EXPAND_LOCAL_MONITORING")
    assert rec.priority == "WATCH"


# Test 12: Missing Optional Evidence (PARTIAL Status Propagation)
def test_missing_optional_evidence_behavior(action_engine, sample_action_input):
    sample_action_input.risk_result.data_quality_status = "PARTIAL"
    res = action_engine.recommend_actions(sample_action_input)
    assert res.status == "PARTIAL"
    assert len(res.recommendations) > 0


# Test 13: Station Scope Guard
def test_station_scope_guard(action_engine, sample_action_input):
    sample_action_input.risk_result.station_id = "UNKNOWN_999"
    res = action_engine.recommend_actions(sample_action_input)
    assert res.status == "BLOCKED"
    assert "UNSUPPORTED_STATION_SCOPE" in res.reason_codes


# Test 14: Timestamp Validation
def test_timestamp_validation(action_engine, sample_action_input):
    sample_action_input.risk_result.assessment_timestamp = "invalid-date"
    res = action_engine.recommend_actions(sample_action_input)
    assert res.status == "BLOCKED"
    assert any("INVALID_TIMESTAMP" in r for r in res.reason_codes)


# Test 15: Expiry Timestamp Calculation (120 min)
def test_expiry_timestamp_calculation(action_engine, sample_action_input):
    sample_action_input.risk_result.assessment_timestamp = "2026-09-20T10:00:00Z"
    res = action_engine.recommend_actions(sample_action_input)
    assert res.created_timestamp == "2026-09-20T10:00:00Z"
    assert res.expires_timestamp == "2026-09-20T12:00:00Z"


# Test 16: Recommendation Deduplication & Precedence
def test_recommendation_deduplication(action_engine, sample_action_input):
    # Multiple rules triggering MONITOR_LOCAL_AIR_QUALITY
    sample_action_input.risk_result.risk_level = "VERY_HIGH"
    sample_action_input.risk_result.reason_codes = ["FORECAST_PERSISTENT"]

    res = action_engine.recommend_actions(sample_action_input)
    monitor_recs = [r for r in res.recommendations if r.action_type == "MONITOR_LOCAL_AIR_QUALITY"]
    assert len(monitor_recs) == 1  # Exactly 1 deduplicated recommendation
    assert monitor_recs[0].priority == "URGENT_REVIEW"  # Highest priority selected


# Test 17: Reason Code Correctness
def test_reason_code_correctness(action_engine, sample_action_input):
    res = action_engine.recommend_actions(sample_action_input)
    for rec in res.recommendations:
        assert len(rec.reason_codes) > 0


# Test 18: Evidence Reference Preservation
def test_evidence_reference_preservation(action_engine, sample_action_input):
    res = action_engine.recommend_actions(sample_action_input)
    assert res.evidence_references["forecast_result_id"] == "fc_res_123"
    assert res.evidence_references["hotspot_id"] == "hotspot_av_001"
    for rec in res.recommendations:
        assert rec.supporting_evidence["forecast_result_id"] == "fc_res_123"


# Test 19: Deterministic Repeatability
def test_deterministic_repeatability(action_engine, sample_action_input):
    res1 = action_engine.recommend_actions(sample_action_input)
    res2 = action_engine.recommend_actions(sample_action_input)
    assert len(res1.recommendations) == len(res2.recommendations)
    for r1, r2 in zip(res1.recommendations, res2.recommendations):
        assert r1.action_type == r2.action_type
        assert r1.priority == r2.priority
        assert r1.reason_codes == r2.reason_codes


# Test 20: Human Review Flag Mandatory (CORRECTION 4)
def test_human_review_flag_mandatory(action_engine, sample_action_input):
    res = action_engine.recommend_actions(sample_action_input)
    assert res.requires_human_review is True
    for rec in res.recommendations:
        assert rec.requires_human_review is True


# Test 21: Non-Causal Wording Audit Checks
def test_non_causal_wording_checks(action_engine, sample_action_input):
    res = action_engine.recommend_actions(sample_action_input)
    forbidden_words = ["caused", "responsible", "guilty", "proven origin"]
    for rec in res.recommendations:
        text = (rec.title + " " + rec.description).lower()
        for fword in forbidden_words:
            assert fword not in text, f"Forbidden causal word '{fword}' found in recommendation text!"


# Test 22: Non-Medical Output Check
def test_non_medical_output_check(action_engine, sample_action_input):
    res = action_engine.recommend_actions(sample_action_input)
    assert "medical advice" in res.non_medical_disclaimer.lower()
    for rec in res.recommendations:
        assert "medical advice" in rec.non_medical_disclaimer.lower()


# Test 23: Configuration Version Check
def test_configuration_version_check(action_engine, sample_action_input):
    res = action_engine.recommend_actions(sample_action_input)
    assert res.calculation_version == "1.0"
    for rec in res.recommendations:
        assert rec.calculation_version == "1.0"


# Test 24: Offline End-to-End Integration Test
def test_offline_end_to_end_forecast_risk_action_integration(action_engine):
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

    risk_engine = RiskAssessmentEngine()
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
    assert risk_res.risk_level in ["HIGH", "VERY_HIGH"]

    act_input = ActionRecommendationInput(
        risk_result=risk_res,
        industrial_context=True,
        major_road_context=True,
        forecast_result_id="fc_e2e_test",
    )
    act_res = action_engine.recommend_actions(act_input)
    assert act_res.status == "PARTIAL"  # Hotspot missing
    assert len(act_res.recommendations) >= 3
    assert act_res.requires_human_review is True
