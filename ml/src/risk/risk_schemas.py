"""
VayuDrishti — Risk Assessment Engine Schemas (Phase 1E-J2E.4.1)

Defines dataclasses and Pydantic validation contracts for risk assessment inputs,
auditable score component breakdowns, and structured output artifacts.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskAssessmentInputModel(BaseModel):
    """Pydantic validation schema for RiskAssessmentInput."""

    station_id: str = Field(..., description="Monitoring station identifier, e.g. ANAND_VIHAR_8118")
    assessment_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of assessment execution")
    forecast_generated_timestamp: str = Field(..., description="ISO 8601 UTC timestamp when input forecast was generated")

    predicted_pm25_1h: float = Field(..., description="+1h predicted PM2.5 concentration in µg/m³")
    pm25_1h_lower_90: float = Field(..., description="+1h lower 90% conformal bound")
    pm25_1h_upper_90: float = Field(..., description="+1h upper 90% conformal bound")

    predicted_pm25_3h: float = Field(..., description="+3h predicted PM2.5 concentration in µg/m³")
    pm25_3h_lower_90: float = Field(..., description="+3h lower 90% conformal bound")
    pm25_3h_upper_90: float = Field(..., description="+3h upper 90% conformal bound")

    predicted_pm25_6h: float = Field(..., description="+6h predicted PM2.5 concentration in µg/m³")
    pm25_6h_lower_90: float = Field(..., description="+6h lower 90% conformal bound")
    pm25_6h_upper_90: float = Field(..., description="+6h upper 90% conformal bound")

    hotspot_detected: Optional[bool] = Field(None, description="Whether a corroborating hotspot was detected")
    hotspot_id: Optional[str] = Field(None, description="ID of corroborating hotspot artifact")
    hotspot_support_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="Hotspot support score (0-100)")
    hotspot_spatial_extent: Optional[float] = Field(None, description="Spatial extent of hotspot in km²")
    hotspot_source_families: Optional[List[str]] = Field(None, description="List of supporting source families")

    industrial_context: Optional[bool] = Field(None, description="Presence of industrial zone context")
    major_road_context: Optional[bool] = Field(None, description="Presence of major arterial road context")
    sensitive_receptor_context: Optional[bool] = Field(None, description="Presence of sensitive receptors (schools, hospitals)")

    forecast_result_id: Optional[str] = Field(None, description="Reference ID to forecast result")
    fusion_id: Optional[str] = Field(None, description="Reference ID to evidence fusion result")
    context_artifact_id: Optional[str] = Field(None, description="Reference ID to geospatial context artifact")


@dataclass
class RiskAssessmentInput:
    """Dataclass contract for RiskAssessmentInput."""

    station_id: str
    assessment_timestamp: str
    forecast_generated_timestamp: str

    predicted_pm25_1h: float
    pm25_1h_lower_90: float
    pm25_1h_upper_90: float

    predicted_pm25_3h: float
    pm25_3h_lower_90: float
    pm25_3h_upper_90: float

    predicted_pm25_6h: float
    pm25_6h_lower_90: float
    pm25_6h_upper_90: float

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


@dataclass
class RiskComponentBreakdown:
    """Auditable component score breakdown (0-100 sum)."""

    forecast_severity: float
    forecast_persistence: float
    uncertainty: float
    hotspot_corroboration: float
    context: float


@dataclass
class RiskAssessmentResult:
    """Canonical output artifact for an environmental risk assessment."""

    assessment_id: str
    station_id: str
    assessment_timestamp: str
    forecast_generated_timestamp: str
    forecast_age_minutes: float
    risk_score: float
    risk_level: str  # LOW, MODERATE, HIGH, VERY_HIGH, UNSUPPORTED_STATION_SCOPE, BLOCKED
    score_breakdown: RiskComponentBreakdown
    reason_codes: List[str] = field(default_factory=list)
    evidence_references: Dict[str, Optional[str]] = field(default_factory=dict)
    data_quality_status: str = "READY"  # READY, PARTIAL, BLOCKED
    hotspot_missing: bool = True
    context_missing: bool = True
    model_scope: str = "Anand Vihar 8118 station-level pilot"
    calculation_version: str = "1.0"
    non_medical_disclaimer: str = (
        "VayuDrishti risk scores represent operational environmental risk levels for community "
        "decision support. They do NOT constitute medical diagnosis, patient advice, or disease probabilities."
    )
