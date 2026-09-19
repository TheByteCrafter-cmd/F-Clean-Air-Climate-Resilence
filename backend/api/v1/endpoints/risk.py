"""
VayuDrishti — Risk Assessment API Endpoint (Phase 1E-J2E.4.2)

Exposes POST /api/v1/risk endpoint for environmental operational risk assessment.
FastAPI operates strictly as transport, request validation, and response serialization.
All risk score calculations, freshness auditing, and station scope logic are delegated
exclusively to RiskAssessmentEngine.assess_risk().
"""

import logging
from typing import Optional

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from backend.api.v1.schemas.common import ErrorDetail, ErrorResponse
from backend.api.v1.schemas.risk import (
    RiskAssessmentRequest,
    RiskAssessmentResponse,
    RiskComponentBreakdownSchema,
)
from ml.src.risk.risk_config import RiskConfig
from ml.src.risk.risk_engine import RiskAssessmentEngine
from ml.src.risk.risk_schemas import RiskAssessmentInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/risk", tags=["risk"])

# Application-lifetime singleton RiskAssessmentEngine instance
_risk_engine: Optional[RiskAssessmentEngine] = None
_risk_engine_init_error: Optional[str] = None


def get_risk_engine(force_reload: bool = False) -> RiskAssessmentEngine:
    """Returns application-lifetime RiskAssessmentEngine instance or raises exception if uninitialized."""
    global _risk_engine, _risk_engine_init_error
    if _risk_engine is None or force_reload:
        try:
            _risk_engine = RiskAssessmentEngine(config=RiskConfig())
            _risk_engine_init_error = None
            logger.info("RiskAssessmentEngine initialized successfully for API transport layer.")
        except Exception as e:
            _risk_engine = None
            _risk_engine_init_error = str(e)
            logger.error(f"Failed to initialize RiskAssessmentEngine: {e}")
            raise RuntimeError(f"Risk assessment service initialization error: {e}")

    return _risk_engine


@router.post(
    "",
    response_model=RiskAssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Assess environmental operational risk level",
    description="""
    Accepts validated forecast telemetry (+1h, +3h, +6h predictions and 90% conformal bounds),
    optional corroborating spatial hotspot evidence, and optional spatial/exposure context,
    and returns a deterministic bounded 0-100 environmental operational risk score, risk level,
    auditable component breakdown, reason codes, evidence references, and non-medical disclaimer.
    """,
)
def assess_risk(payload: RiskAssessmentRequest):
    """
    Executes risk assessment endpoint request.

    Delegates all risk scoring and domain validation strictly to RiskAssessmentEngine.assess_risk().
    """
    try:
        engine = get_risk_engine()

        # 1. Map API Request Pydantic schema to RiskAssessmentInput domain contract
        input_data = RiskAssessmentInput(
            station_id=payload.station_id,
            assessment_timestamp=payload.assessment_timestamp,
            forecast_generated_timestamp=payload.forecast_generated_timestamp,
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
        )

        # 2. Delegate assessment execution to authoritative RiskAssessmentEngine
        result = engine.assess_risk(input_data)

        # 3. Serialize RiskAssessmentResult into RiskAssessmentResponse
        breakdown_schema = RiskComponentBreakdownSchema(
            forecast_severity=result.score_breakdown.forecast_severity,
            forecast_persistence=result.score_breakdown.forecast_persistence,
            uncertainty=result.score_breakdown.uncertainty,
            hotspot_corroboration=result.score_breakdown.hotspot_corroboration,
            context=result.score_breakdown.context,
        )

        return RiskAssessmentResponse(
            status="SUCCESS",
            assessment_id=result.assessment_id,
            canonical_station_id=result.station_id,
            assessment_timestamp=result.assessment_timestamp,
            forecast_generated_timestamp=result.forecast_generated_timestamp,
            forecast_age_minutes=result.forecast_age_minutes,
            risk_score=result.risk_score,
            risk_level=result.risk_level,
            score_breakdown=breakdown_schema,
            reason_codes=result.reason_codes,
            data_quality_status=result.data_quality_status,
            hotspot_missing=result.hotspot_missing,
            context_missing=result.context_missing,
            evidence_references=result.evidence_references,
            model_scope=result.model_scope,
            calculation_version=result.calculation_version,
            non_medical_disclaimer=result.non_medical_disclaimer,
        )

    except RuntimeError as re:
        logger.error(f"Risk assessment service unavailable: {re}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="RISK_SERVICE_UNAVAILABLE",
                    message="Risk assessment engine service is unavailable.",
                    details={"error": str(re)},
                )
            ).model_dump(),
        )

    except Exception as e:
        logger.error(f"Unexpected error during risk API execution: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="RISK_ASSESSMENT_ERROR",
                    message="Risk assessment failed due to an unexpected server error.",
                )
            ).model_dump(),
        )
