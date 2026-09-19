"""
VayuDrishti — Decision Intelligence API Schemas (Phase 1E-J2E.4.5)

Defines Pydantic request and response schemas for POST /api/v1/decision endpoint.
All validation rules ensure finite numerics, strict range bounds, and canonical fields.
Reuses authoritative domain fields from Phase 1E-J2E.4.3 (ActionRecommendation) and
Phase 1E-J2E.4.4 (DecisionIntelligenceResult).
"""

import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class DecisionIntelligenceRequest(BaseModel):
    """Request payload schema for End-to-End Decision Intelligence assessment."""

    station_id: str = Field(..., description="Monitoring station identifier or alias, e.g. ANAND_VIHAR_8118 or 8118")
    prediction_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of forecast prediction")
    assessment_timestamp: Optional[str] = Field(None, description="ISO 8601 UTC timestamp of assessment execution")

    predicted_pm25_1h: Optional[float] = Field(None, description="+1h predicted PM2.5 concentration in µg/m³")
    pm25_1h_lower_90: Optional[float] = Field(None, description="+1h lower 90% conformal bound")
    pm25_1h_upper_90: Optional[float] = Field(None, description="+1h upper 90% conformal bound")

    predicted_pm25_3h: Optional[float] = Field(None, description="+3h predicted PM2.5 concentration in µg/m³")
    pm25_3h_lower_90: Optional[float] = Field(None, description="+3h lower 90% conformal bound")
    pm25_3h_upper_90: Optional[float] = Field(None, description="+3h upper 90% conformal bound")

    predicted_pm25_6h: Optional[float] = Field(None, description="+6h predicted PM2.5 concentration in µg/m³")
    pm25_6h_lower_90: Optional[float] = Field(None, description="+6h lower 90% conformal bound")
    pm25_6h_upper_90: Optional[float] = Field(None, description="+6h upper 90% conformal bound")

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

    forecast_result: Optional[Dict[str, Any]] = Field(None, description="Optional pre-computed forecast result dictionary")

    @model_validator(mode="after")
    def validate_finite_numerics(self):
        """Ensures all provided numeric fields are finite numbers (no NaN, +Inf, -Inf)."""
        numeric_fields = [
            ("predicted_pm25_1h", self.predicted_pm25_1h),
            ("pm25_1h_lower_90", self.pm25_1h_lower_90),
            ("pm25_1h_upper_90", self.pm25_1h_upper_90),
            ("predicted_pm25_3h", self.predicted_pm25_3h),
            ("pm25_3h_lower_90", self.pm25_3h_lower_90),
            ("pm25_3h_upper_90", self.pm25_3h_upper_90),
            ("predicted_pm25_6h", self.predicted_pm25_6h),
            ("pm25_6h_lower_90", self.pm25_6h_lower_90),
            ("pm25_6h_upper_90", self.pm25_6h_upper_90),
        ]
        if self.hotspot_support_score is not None:
            numeric_fields.append(("hotspot_support_score", self.hotspot_support_score))
        if self.hotspot_spatial_extent is not None:
            numeric_fields.append(("hotspot_spatial_extent", self.hotspot_spatial_extent))

        for name, val in numeric_fields:
            if val is not None and (math.isnan(val) or math.isinf(val)):
                raise ValueError(f"Field '{name}' must be a finite number, got {val}")

        return self


class ActionRecommendationSchema(BaseModel):
    """Pydantic schema matching authoritative ActionRecommendation domain contract (Phase 1E-J2E.4.3)."""

    recommendation_id: str = Field(..., description="Unique recommendation identifier")
    action_type: str = Field(..., description="Action category type code")
    priority: str = Field(..., description="Action priority level: INFORMATIONAL, WATCH, PRIORITY, URGENT_REVIEW")
    title: str = Field(..., description="Short action title")
    description: str = Field(..., description="Detailed operational recommendation description")
    expected_objective: str = Field(..., description="Target objective of recommended action")
    trigger_conditions: List[str] = Field(default_factory=list, description="List of rule conditions that triggered action")
    reason_codes: List[str] = Field(default_factory=list, description="Machine-readable decision audit codes")
    supporting_evidence: Dict[str, Optional[str]] = Field(default_factory=dict, description="Audit trace references to evidence items")
    station_id: str = Field(..., description="Canonical station identifier")
    created_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of recommendation creation")
    expires_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of recommendation expiration")
    requires_human_review: bool = Field(True, description="Mandatory human review invariant (ALWAYS True)")
    calculation_version: str = Field("1.0", description="Version of action calculation logic")
    non_medical_disclaimer: str = Field(..., description="Mandatory non-medical advisory disclaimer")
    non_causal_disclaimer: str = Field(..., description="Mandatory non-causal attribution disclaimer")


class DecisionIntelligenceResponse(BaseModel):
    """Response payload schema for End-to-End Decision Intelligence API (Phase 1E-J2E.4.5)."""

    status: str = Field("SUCCESS", description="API transport execution status")
    decision_result_id: str = Field(..., description="Unique decision intelligence evaluation identifier")
    station_id: str = Field(..., description="Canonical monitoring station identifier, e.g. ANAND_VIHAR_8118")
    prediction_timestamp: str = Field(..., description="ISO 8601 UTC prediction timestamp")
    created_timestamp: str = Field(..., description="ISO 8601 UTC timestamp when decision artifact was generated")
    expires_timestamp: str = Field(..., description="Earliest ISO 8601 UTC expiration timestamp among constituent outputs")

    forecast_status: str = Field(..., description="Data quality status of forecast component: READY, PARTIAL, BLOCKED")
    risk_status: str = Field(..., description="Data quality status of risk assessment component: READY, PARTIAL, BLOCKED")
    action_status: str = Field(..., description="Data quality status of authority action component: READY, PARTIAL, BLOCKED")
    overall_data_quality_status: str = Field(..., description="Overall pipeline status: READY, PARTIAL, BLOCKED (BLOCKED > PARTIAL > READY)")

    forecast_reference: Optional[Dict[str, Any]] = Field(None, description="Reference metadata for forecast component")
    risk_reference: Optional[Dict[str, Any]] = Field(None, description="Reference metadata for risk assessment component")
    action_reference: Optional[Dict[str, Any]] = Field(None, description="Reference metadata for action recommendation component")
    evidence_references: Dict[str, Optional[str]] = Field(default_factory=dict, description="Audit references to constituent evidence items")

    risk_score: float = Field(..., description="Deterministic 0-100 environmental risk score")
    risk_level: str = Field(..., description="Operational risk level: LOW, MODERATE, HIGH, VERY_HIGH, UNSUPPORTED_STATION_SCOPE, BLOCKED")
    recommendation_count: int = Field(..., description="Count of operational action recommendations generated")
    recommendations: List[ActionRecommendationSchema] = Field(default_factory=list, description="Prioritized list of action recommendations")
    missing_evidence: List[str] = Field(default_factory=list, description="List of missing evidence descriptors")

    decision_summary: str = Field(..., description="Non-causal, non-medical operational decision summary paragraph")
    requires_human_review: bool = Field(True, description="Mandatory human review invariant (Hard Rule: ALWAYS True)")
    model_scope: str = Field(..., description="Scope statement of underlying models")
    calculation_version: str = Field(..., description="Orchestration calculation version")
    non_medical_disclaimer: str = Field(..., description="Mandatory non-medical operational disclaimer")
    non_causal_disclaimer: str = Field(..., description="Mandatory non-causal attribution disclaimer")

    @model_validator(mode="after")
    def ensure_human_review_true(self):
        """Hard Rule (CHANGE 1): Enforces requires_human_review MUST ALWAYS BE TRUE."""
        if self.requires_human_review is not True:
            self.requires_human_review = True
        return self
