"""
VayuDrishti — Decision Intelligence Orchestrator Test Suite (Phase 1E-J2E.4.4)

Tests end-to-end orchestration, status precedence (BLOCKED > PARTIAL > READY),
station scope validation, earliest expiry rules, human review invariant, evidence tracking,
non-causal summary generation, and full offline pipeline integration.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone

from ml.src.decision.decision_config import DecisionConfig
from ml.src.decision.decision_schemas import (
    DecisionIntelligenceInput,
    DecisionIntelligenceInputModel,
    DecisionIntelligenceResult,
)
from ml.src.decision.decision_engine import DecisionIntelligenceEngine
from ml.src.risk.risk_engine import CANONICAL_STATION_ID, RiskAssessmentEngine
from ml.src.risk.risk_schemas import (
    RiskAssessmentInput,
    RiskAssessmentResult,
    RiskComponentBreakdown,
)
from ml.src.actions.action_engine import ActionRecommendationEngine
from ml.src.actions.action_schemas import (
    ActionRecommendationInput,
    ActionRecommendationResult,
)


@pytest.fixture
def engine():
    return DecisionIntelligenceEngine()


@pytest.fixture
def valid_input():
    return DecisionIntelligenceInput(
        station_id="ANAND_VIHAR_8118",
        prediction_timestamp="2026-03-30T12:00:00Z",
        assessment_timestamp="2026-03-30T12:00:00Z",
        predicted_pm25_1h=145.2,
        pm25_1h_lower_90=120.0,
        pm25_1h_upper_90=170.4,
        predicted_pm25_3h=158.0,
        pm25_3h_lower_90=130.0,
        pm25_3h_upper_90=186.0,
        predicted_pm25_6h=172.5,
        pm25_6h_lower_90=140.0,
        pm25_6h_upper_90=205.0,
        hotspot_detected=True,
        hotspot_id="hs_av_20260330_01",
        hotspot_support_score=85.0,
        hotspot_spatial_extent=4.5,
        hotspot_source_families=["INDUSTRIAL_STACK", "TRAFFIC_CORRIDOR"],
        industrial_context=True,
        major_road_context=True,
        sensitive_receptor_context=True,
        forecast_result_id="fc_av_20260330_12",
        fusion_id="fus_av_20260330_12",
        context_artifact_id="ctx_av_20260330_01",
    )


# 1. Initialization
def test_decision_engine_init(engine):
    assert engine is not None
    assert engine.config.decision_config_version == "1.0"
    assert engine.config.supported_station_id == "ANAND_VIHAR_8118"


# 2. Canonical Station Scope Validation
def test_station_scope_canonical(engine, valid_input):
    res = engine.orchestrate(valid_input)
    assert res.station_id == "ANAND_VIHAR_8118"
    assert res.overall_data_quality_status == "READY"


# 3. Station Scope Alias Mapping
def test_station_scope_alias(engine, valid_input):
    valid_input.station_id = "8118"
    res = engine.orchestrate(valid_input)
    assert res.station_id == "ANAND_VIHAR_8118"
    assert res.overall_data_quality_status == "READY"


# 4. Station Scope Unsupported Guard
def test_station_scope_unsupported(engine, valid_input):
    valid_input.station_id = "UNSUPPORTED_9999"
    res = engine.orchestrate(valid_input)
    assert res.overall_data_quality_status == "BLOCKED"
    assert res.risk_level == "UNSUPPORTED_STATION_SCOPE"
    assert res.requires_human_review is True
    assert "outside supported pilot scope" in res.decision_summary


# 5. Invalid Timestamp Guard
def test_invalid_prediction_timestamp(engine, valid_input):
    valid_input.prediction_timestamp = "INVALID_TIMESTAMP_STRING"
    res = engine.orchestrate(valid_input)
    assert res.overall_data_quality_status == "BLOCKED"
    assert res.requires_human_review is True
    assert "invalid prediction timestamp" in res.decision_summary.lower()


# 6. Full Ready Orchestration Flow
def test_full_ready_orchestration(engine, valid_input):
    res = engine.orchestrate(valid_input)
    assert res.overall_data_quality_status == "READY"
    assert res.forecast_status == "READY"
    assert res.risk_status == "READY"
    assert res.action_status == "READY"
    assert res.risk_score > 0.0
    assert res.recommendation_count > 0
    assert len(res.recommendations) == res.recommendation_count
    assert res.requires_human_review is True


# 7. Partial Forecast Horizons
def test_partial_forecast_horizons(engine, valid_input):
    valid_input.predicted_pm25_3h = None
    valid_input.predicted_pm25_6h = None
    res = engine.orchestrate(valid_input)
    assert res.forecast_status == "PARTIAL"
    assert res.overall_data_quality_status == "PARTIAL"
    assert "complete_conformal_forecast_horizons" in res.missing_evidence


# 8. Blocked Forecast Status
def test_blocked_forecast_status(engine, valid_input):
    valid_input.predicted_pm25_1h = None
    valid_input.predicted_pm25_3h = None
    valid_input.predicted_pm25_6h = None
    res = engine.orchestrate(valid_input)
    assert res.forecast_status == "BLOCKED"
    assert res.overall_data_quality_status == "BLOCKED"


# 9. Human Review Invariant (MANDATORY HARD RULE)
def test_human_review_invariant_always_true(engine, valid_input):
    # Test Ready
    res_ready = engine.orchestrate(valid_input)
    assert res_ready.requires_human_review is True

    # Test Partial
    valid_input.predicted_pm25_3h = None
    res_partial = engine.orchestrate(valid_input)
    assert res_partial.requires_human_review is True

    # Test Blocked
    valid_input.station_id = "INVALID_STATION"
    res_blocked = engine.orchestrate(valid_input)
    assert res_blocked.requires_human_review is True


# 10. Status Precedence (BLOCKED > PARTIAL > READY)
def test_status_precedence_blocked_over_partial_and_ready(engine):
    assert engine.config.resolve_overall_status(["READY", "PARTIAL", "BLOCKED"]) == "BLOCKED"
    assert engine.config.resolve_overall_status(["BLOCKED", "READY"]) == "BLOCKED"


# 11. Status Precedence (PARTIAL > READY)
def test_status_precedence_partial_over_ready(engine):
    assert engine.config.resolve_overall_status(["READY", "PARTIAL", "READY"]) == "PARTIAL"
    assert engine.config.resolve_overall_status(["READY", "READY"]) == "READY"


# 12. Earliest Expiry Calculation
def test_earliest_expiry_calculation(engine, valid_input):
    res = engine.orchestrate(valid_input)
    # Default validity is 60 min from assessment timestamp (12:00 -> 13:00)
    assert res.expires_timestamp == "2026-03-30T13:00:00Z"


# 13. Missing Evidence Tracking
def test_missing_evidence_tracking(engine, valid_input):
    valid_input.hotspot_detected = None
    valid_input.industrial_context = None
    valid_input.major_road_context = None
    valid_input.sensitive_receptor_context = None

    res = engine.orchestrate(valid_input)
    assert "hotspot_data" in res.missing_evidence
    assert "geospatial_context_data" in res.missing_evidence


# 14. Evidence Reference Preservation
def test_evidence_reference_preservation(engine, valid_input):
    res = engine.orchestrate(valid_input)
    ref = res.evidence_references
    assert ref.get("forecast_result_id") == "fc_av_20260330_12"
    assert ref.get("hotspot_id") == "hs_av_20260330_01"
    assert ref.get("fusion_id") == "fus_av_20260330_12"
    assert ref.get("context_artifact_id") == "ctx_av_20260330_01"
    assert ref.get("assessment_id") is not None
    assert ref.get("action_result_id") is not None


# 15. Recommendation Linkage
def test_recommendation_linkage(engine, valid_input):
    res = engine.orchestrate(valid_input)
    for rec in res.recommendations:
        assert rec.station_id == "ANAND_VIHAR_8118"
        assert rec.requires_human_review is True
        assert rec.supporting_evidence.get("forecast_result_id") == "fc_av_20260330_12"


# 16. Non-Causal Decision Summary Text
def test_non_causal_decision_summary(engine, valid_input):
    res = engine.orchestrate(valid_input)
    assert "Anand Vihar 8118" in res.decision_summary
    assert "risk score" in res.decision_summary
    assert "Overall pipeline status: READY" in res.decision_summary
    assert res.non_causal_disclaimer is not None
    assert res.non_medical_disclaimer is not None


# 17. Orchestration with Precomputed Objects
def test_orchestration_with_precomputed_objects(engine, valid_input):
    # First compute risk result
    risk_inp = RiskAssessmentInput(
        station_id="ANAND_VIHAR_8118",
        assessment_timestamp="2026-03-30T12:00:00Z",
        forecast_generated_timestamp="2026-03-30T12:00:00Z",
        predicted_pm25_1h=145.2,
        pm25_1h_lower_90=120.0,
        pm25_1h_upper_90=170.4,
        predicted_pm25_3h=158.0,
        pm25_3h_lower_90=130.0,
        pm25_3h_upper_90=186.0,
        predicted_pm25_6h=172.5,
        pm25_6h_lower_90=140.0,
        pm25_6h_upper_90=205.0,
    )
    risk_res = engine.risk_engine.assess_risk(risk_inp)

    valid_input.risk_result = risk_res
    res = engine.orchestrate(valid_input)
    assert res.risk_score == risk_res.risk_score
    assert res.risk_level == risk_res.risk_level


# 18. Orchestration from Forecast Dict
def test_orchestration_from_forecast_dict(engine):
    fc_dict = {
        "status": "SUCCESS",
        "data_quality_status": "READY",
        "forecast_result_id": "fc_dict_123",
        "horizons": {
            "+1h": {
                "predicted_pm25": 110.0,
                "prediction_intervals": {
                    "90_pct": {"lower_bound": 90.0, "upper_bound": 130.0}
                },
            },
            "+3h": {
                "predicted_pm25": 125.0,
                "prediction_intervals": {
                    "90_pct": {"lower_bound": 100.0, "upper_bound": 150.0}
                },
            },
            "+6h": {
                "predicted_pm25": 140.0,
                "prediction_intervals": {
                    "90_pct": {"lower_bound": 110.0, "upper_bound": 170.0}
                },
            },
        },
    }
    inp = DecisionIntelligenceInput(
        station_id="ANAND_VIHAR_8118",
        prediction_timestamp="2026-03-30T12:00:00Z",
        forecast_result=fc_dict,
    )
    res = engine.orchestrate(inp)
    assert res.forecast_status == "READY"
    assert res.risk_score > 0.0


# 19. Pydantic Input Model Validation
def test_pydantic_schema_validation():
    model_data = {
        "station_id": "ANAND_VIHAR_8118",
        "prediction_timestamp": "2026-03-30T12:00:00Z",
        "predicted_pm25_1h": 145.2,
        "pm25_1h_lower_90": 120.0,
        "pm25_1h_upper_90": 170.4,
    }
    validated = DecisionIntelligenceInputModel(**model_data)
    assert validated.station_id == "ANAND_VIHAR_8118"
    assert validated.predicted_pm25_1h == 145.2


# 20. Determinism Check
def test_determinism(engine, valid_input):
    res1 = engine.orchestrate(valid_input)
    res2 = engine.orchestrate(valid_input)

    assert res1.risk_score == res2.risk_score
    assert res1.risk_level == res2.risk_level
    assert res1.recommendation_count == res2.recommendation_count
    assert res1.overall_data_quality_status == res2.overall_data_quality_status
    assert res1.decision_summary == res2.decision_summary


# 21. Full Offline Pipeline Integration Test
def test_end_to_end_offline_integration():
    """Verifies complete chain from forecast input through DecisionIntelligenceEngine."""
    engine = DecisionIntelligenceEngine()
    inp = DecisionIntelligenceInput(
        station_id="ANAND_VIHAR_8118",
        prediction_timestamp="2026-03-30T12:00:00Z",
        predicted_pm25_1h=210.0,
        pm25_1h_lower_90=180.0,
        pm25_1h_upper_90=240.0,
        predicted_pm25_3h=225.0,
        pm25_3h_lower_90=190.0,
        pm25_3h_upper_90=260.0,
        predicted_pm25_6h=250.0,
        pm25_6h_lower_90=210.0,
        pm25_6h_upper_90=290.0,
        hotspot_detected=True,
        hotspot_id="hs_e2e_01",
        hotspot_support_score=95.0,
        industrial_context=True,
        sensitive_receptor_context=True,
    )

    result = engine.orchestrate(inp)
    assert isinstance(result, DecisionIntelligenceResult)
    assert result.station_id == "ANAND_VIHAR_8118"
    assert result.risk_level in ["HIGH", "VERY_HIGH"]
    assert result.recommendation_count >= 3
    assert result.requires_human_review is True
