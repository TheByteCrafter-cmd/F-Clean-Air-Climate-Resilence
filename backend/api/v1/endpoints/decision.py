"""
VayuDrishti — Decision Intelligence API Endpoint (Phase 1E-J2E.4.5)

Exposes POST /api/v1/decision endpoint for end-to-end decision intelligence evaluation.
FastAPI operates strictly as transport, request validation, and response serialization.
All forecasting, risk assessment, action recommendation, and decision orchestration logic
are delegated exclusively to DecisionIntelligenceEngine.orchestrate().
"""

import logging
from typing import Optional

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from backend.api.v1.schemas.common import ErrorDetail, ErrorResponse
from backend.api.v1.schemas.decision import (
    ActionRecommendationSchema,
    DecisionIntelligenceRequest,
    DecisionIntelligenceResponse,
)
from ml.src.decision.decision_config import DecisionConfig
from ml.src.decision.decision_engine import DecisionIntelligenceEngine
from ml.src.decision.decision_schemas import DecisionIntelligenceInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/decision", tags=["decision"])

# Application-lifetime singleton DecisionIntelligenceEngine instance
_decision_engine: Optional[DecisionIntelligenceEngine] = None
_decision_engine_init_error: Optional[str] = None


def get_decision_engine(force_reload: bool = False) -> DecisionIntelligenceEngine:
    """Returns application-lifetime DecisionIntelligenceEngine instance or raises RuntimeError if uninitialized."""
    global _decision_engine, _decision_engine_init_error
    if _decision_engine is None or force_reload:
        try:
            _decision_engine = DecisionIntelligenceEngine(config=DecisionConfig())
            _decision_engine_init_error = None
            logger.info("DecisionIntelligenceEngine initialized successfully for API transport layer.")
        except Exception as e:
            _decision_engine = None
            _decision_engine_init_error = str(e)
            logger.error(f"Failed to initialize DecisionIntelligenceEngine: {e}")
            raise RuntimeError(f"Decision intelligence service initialization error: {e}")

    return _decision_engine


@router.post(
    "",
    response_model=DecisionIntelligenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate end-to-end environmental decision intelligence",
    description="""
    Accepts forecast predictions or telemetry, optional spatial hotspot evidence, and optional exposure context,
    and returns a canonical auditable DecisionIntelligenceResult containing forecast, risk, and action outputs.
    Delegates all domain evaluation to authoritative DecisionIntelligenceEngine.
    """,
)
def evaluate_decision(payload: DecisionIntelligenceRequest):
    """
    Executes decision intelligence endpoint request.

    Delegates all pipeline execution strictly to DecisionIntelligenceEngine.orchestrate().
    """
    try:
        engine = get_decision_engine()

        # 1. Map API Request Pydantic schema to DecisionIntelligenceInput domain contract
        input_data = DecisionIntelligenceInput(
            station_id=payload.station_id,
            prediction_timestamp=payload.prediction_timestamp,
            assessment_timestamp=payload.assessment_timestamp,
            predicted_pm25_1h=payload.predicted_pm25_1h,
            pm25_1h_lower_90=payload.pm25_1h_lower_90,
            pm25_1h_upper_90=payload.pm25_1h_upper_90,
            predicted_pm25_3h=payload.predicted_pm25_3h,
            pm25_3h_lower_90=payload.pm25_3h_lower_90,
            pm25_3h_upper_90=payload.pm25_3h_upper_90,
            predicted_pm25_6h=payload.predicted_pm25_6h,
            pm25_6h_lower_90=payload.pm25_6h_lower_90,
            pm25_6h_upper_90=payload.pm25_6h_upper_90,
            hotspot_detected=payload.hotspot_detected,
            hotspot_id=payload.hotspot_id,
            hotspot_support_score=payload.hotspot_support_score,
            hotspot_spatial_extent=payload.hotspot_spatial_extent,
            hotspot_source_families=payload.hotspot_source_families,
            industrial_context=payload.industrial_context,
            major_road_context=payload.major_road_context,
            sensitive_receptor_context=payload.sensitive_receptor_context,
            forecast_result_id=payload.forecast_result_id,
            fusion_id=payload.fusion_id,
            context_artifact_id=payload.context_artifact_id,
            forecast_result=payload.forecast_result,
        )

        # 2. Delegate orchestration execution to DecisionIntelligenceEngine
        result = engine.orchestrate(input_data)

        # 3. Serialize ActionRecommendation domain objects to ActionRecommendationSchema
        rec_schemas = [
            ActionRecommendationSchema(
                recommendation_id=rec.recommendation_id,
                action_type=rec.action_type,
                priority=rec.priority,
                title=rec.title,
                description=rec.description,
                expected_objective=rec.expected_objective,
                trigger_conditions=rec.trigger_conditions,
                reason_codes=rec.reason_codes,
                supporting_evidence=rec.supporting_evidence,
                station_id=rec.station_id,
                created_timestamp=rec.created_timestamp,
                expires_timestamp=rec.expires_timestamp,
                requires_human_review=True,  # Mandatory True
                calculation_version=rec.calculation_version,
                non_medical_disclaimer=rec.non_medical_disclaimer,
                non_causal_disclaimer=rec.non_causal_disclaimer,
            )
            for rec in result.recommendations
        ]

        # 4. Construct response model (requires_human_review is ALWAYS True)
        return DecisionIntelligenceResponse(
            status="SUCCESS",
            decision_result_id=result.decision_result_id,
            station_id=result.station_id,
            prediction_timestamp=result.prediction_timestamp,
            created_timestamp=result.created_timestamp,
            expires_timestamp=result.expires_timestamp,
            forecast_status=result.forecast_status,
            risk_status=result.risk_status,
            action_status=result.action_status,
            overall_data_quality_status=result.overall_data_quality_status,
            forecast_reference=result.forecast_reference,
            risk_reference=result.risk_reference,
            action_reference=result.action_reference,
            evidence_references=result.evidence_references,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            recommendation_count=result.recommendation_count,
            recommendations=rec_schemas,
            missing_evidence=result.missing_evidence,
            decision_summary=result.decision_summary,
            requires_human_review=True,  # Hard Invariant: ALWAYS True
            model_scope=result.model_scope,
            calculation_version=result.calculation_version,
            non_medical_disclaimer=result.non_medical_disclaimer,
            non_causal_disclaimer=result.non_causal_disclaimer,
        )

    except RuntimeError as re:
        logger.error(f"Decision intelligence service unavailable: {re}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="DECISION_SERVICE_UNAVAILABLE",
                    message="Decision intelligence engine service is unavailable.",
                    details={"error": str(re)},
                )
            ).model_dump(),
        )

    except Exception as e:
        logger.error(f"Unexpected error during decision API execution: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="DECISION_ORCHESTRATION_ERROR",
                    message="Decision intelligence evaluation failed due to an unexpected server error.",
                )
            ).model_dump(),
        )
