"""
VayuDrishti — Decision Intelligence Orchestrator Schemas (Phase 1E-J2E.4.4)

Defines dataclasses and Pydantic validation contracts for DecisionIntelligenceInput,
composite references, and the canonical DecisionIntelligenceResult output artifact.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ml.src.actions.action_schemas import (
    ActionRecommendation,
    ActionRecommendationResult,
)
from ml.src.risk.risk_schemas import RiskAssessmentResult


class DecisionIntelligenceInputModel(BaseModel):
    """Pydantic validation schema for DecisionIntelligenceInput."""

    station_id: str = Field(..., description="Monitoring station identifier, e.g. ANAND_VIHAR_8118")
    prediction_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of forecast prediction")
    assessment_timestamp: Optional[str] = Field(None, description="ISO 8601 UTC timestamp of assessment execution")

    predicted_pm25_1h: Optional[float] = Field(None, description="+1h predicted PM2.5 in µg/m³")
    pm25_1h_lower_90: Optional[float] = Field(None, description="+1h lower 90% conformal bound")
    pm25_1h_upper_90: Optional[float] = Field(None, description="+1h upper 90% conformal bound")

    predicted_pm25_3h: Optional[float] = Field(None, description="+3h predicted PM2.5 in µg/m³")
    pm25_3h_lower_90: Optional[float] = Field(None, description="+3h lower 90% conformal bound")
    pm25_3h_upper_90: Optional[float] = Field(None, description="+3h upper 90% conformal bound")

    predicted_pm25_6h: Optional[float] = Field(None, description="+6h predicted PM2.5 in µg/m³")
    pm25_6h_lower_90: Optional[float] = Field(None, description="+6h lower 90% conformal bound")
    pm25_6h_upper_90: Optional[float] = Field(None, description="+6h upper 90% conformal bound")

    hotspot_detected: Optional[bool] = Field(None, description="Presence of corroborating hotspot")
    hotspot_id: Optional[str] = Field(None, description="ID of corroborating hotspot artifact")
    hotspot_support_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Hotspot support score (0-100)")
    hotspot_spatial_extent: Optional[float] = Field(None, description="Spatial extent of hotspot in km²")
    hotspot_source_families: Optional[List[str]] = Field(None, description="List of supporting source families")

    industrial_context: Optional[bool] = Field(None, description="Presence of industrial zone context")
    major_road_context: Optional[bool] = Field(None, description="Presence of major arterial road context")
    sensitive_receptor_context: Optional[bool] = Field(None, description="Presence of sensitive receptors (schools/hospitals)")

    forecast_result_id: Optional[str] = Field(None, description="Reference ID to forecast result")
    fusion_id: Optional[str] = Field(None, description="Reference ID to evidence fusion result")
    context_artifact_id: Optional[str] = Field(None, description="Reference ID to geospatial context artifact")


@dataclass
class DecisionIntelligenceInput:
    """Dataclass input contract for DecisionIntelligenceEngine."""

    station_id: str
    prediction_timestamp: str
    assessment_timestamp: Optional[str] = None

    predicted_pm25_1h: Optional[float] = None
    pm25_1h_lower_90: Optional[float] = None
    pm25_1h_upper_90: Optional[float] = None

    predicted_pm25_3h: Optional[float] = None
    pm25_3h_lower_90: Optional[float] = None
    pm25_3h_upper_90: Optional[float] = None

    predicted_pm25_6h: Optional[float] = None
    pm25_6h_lower_90: Optional[float] = None
    pm25_6h_upper_90: Optional[float] = None

    hotspot_detected: Optional[bool] = None
    hotspot_id: Optional[str] = None
    hotspot_support_score: Optional[float] = None
    hotspot_spatial_extent: Optional[float] = None
    hotspot_source_families: Optional[List[str]] = None

    industrial_context: Optional[bool] = None
    major_road_context: Optional[bool] = None
    sensitive_receptor_context: Optional[bool] = None

    forecast_result_id: Optional[str] = None
    fusion_id: Optional[str] = None
    context_artifact_id: Optional[str] = None

    forecast_result: Optional[Dict[str, Any]] = None
    risk_result: Optional[RiskAssessmentResult] = None
    action_result: Optional[ActionRecommendationResult] = None


@dataclass
class DecisionIntelligenceResult:
    """Canonical dataclass output contract for end-to-end Decision Intelligence Result."""

    decision_result_id: str
    station_id: str
    prediction_timestamp: str
    created_timestamp: str
    expires_timestamp: str

    forecast_status: str  # READY, PARTIAL, BLOCKED
    risk_status: str      # READY, PARTIAL, BLOCKED
    action_status: str    # READY, PARTIAL, BLOCKED
    overall_data_quality_status: str  # READY, PARTIAL, BLOCKED (BLOCKED > PARTIAL > READY)

    forecast_reference: Optional[Dict[str, Any]] = None
    risk_reference: Optional[Dict[str, Any]] = None
    action_reference: Optional[Dict[str, Any]] = None
    evidence_references: Dict[str, Optional[str]] = field(default_factory=dict)

    risk_score: float = 0.0
    risk_level: str = "BLOCKED"
    recommendation_count: int = 0
    recommendations: List[ActionRecommendation] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)

    decision_summary: str = ""
    requires_human_review: bool = True  # Mandatory True (Hard Rule)
    model_scope: str = "Anand Vihar 8118 station-level pilot"
    calculation_version: str = "1.0"

    non_medical_disclaimer: str = (
        "VayuDrishti decision intelligence outputs provide operational environmental decision support "
        "for human authority review. They do NOT constitute medical advice, clinical diagnosis, "
        "or patient care recommendations."
    )
    non_causal_disclaimer: str = (
        "Decision intelligence outputs synthesize environmental forecast, risk, and action evidence "
        "for human authority review. They do NOT establish legal liability or definitive source attribution."
    )
