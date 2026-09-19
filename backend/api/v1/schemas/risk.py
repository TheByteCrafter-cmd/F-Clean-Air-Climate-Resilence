"""
VayuDrishti — Risk Assessment API Schemas (Phase 1E-J2E.4.2)

Defines Pydantic request and response schemas for POST /api/v1/risk endpoint.
All validation rules ensure finite numbers, strict range bounds, and canonical fields.
"""

import math
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class RiskAssessmentRequest(BaseModel):
    """Request payload schema for environmental risk assessment."""

    station_id: str = Field(..., description="Monitoring station identifier or alias, e.g. ANAND_VIHAR_8118 or 8118")
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

    @model_validator(mode="after")
    def validate_finite_numerics(self):
        """Ensures all numeric fields are finite numbers (no NaN, +Inf, -Inf)."""
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
            if val is None or math.isnan(val) or math.isinf(val):
                raise ValueError(f"Field '{name}' must be a finite number, got {val}")

        return self


class RiskComponentBreakdownSchema(BaseModel):
    """Auditable component score breakdown (0-100 sum)."""

    forecast_severity: float = Field(..., description="Forecast severity score (0-40)")
    forecast_persistence: float = Field(..., description="Forecast persistence score (0-20)")
    uncertainty: float = Field(..., description="Uncertainty score (0-15)")
    hotspot_corroboration: float = Field(..., description="Hotspot corroboration score (0-15)")
    context: float = Field(..., description="Spatial/exposure context score (0-10)")


class RiskAssessmentResponse(BaseModel):
    """Response payload schema for environmental risk assessment."""

    status: str = Field("SUCCESS", description="API transport execution status")
    assessment_id: str = Field(..., description="Unique assessment execution identifier")
    canonical_station_id: str = Field(..., description="Canonical monitoring station identifier, e.g. ANAND_VIHAR_8118")
    assessment_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of assessment execution")
    forecast_generated_timestamp: str = Field(..., description="ISO 8601 UTC timestamp when input forecast was generated")
    forecast_age_minutes: float = Field(..., description="Age of forecast in minutes relative to assessment timestamp")

    risk_score: float = Field(..., description="Deterministic bounded environmental risk score (0-100)")
    risk_level: str = Field(..., description="Environmental operational risk level: LOW, MODERATE, HIGH, VERY_HIGH, UNSUPPORTED_STATION_SCOPE, BLOCKED")

    score_breakdown: RiskComponentBreakdownSchema = Field(..., description="Auditable breakdown of component scores")
    reason_codes: List[str] = Field(default_factory=list, description="Machine-readable decision and audit reason codes")

    data_quality_status: str = Field(..., description="Data quality state: READY, PARTIAL, BLOCKED")
    hotspot_missing: bool = Field(..., description="Whether optional hotspot evidence was missing")
    context_missing: bool = Field(..., description="Whether optional spatial context was missing")

    evidence_references: Dict[str, Optional[str]] = Field(default_factory=dict, description="Audit references to evidence objects")
    model_scope: str = Field(..., description="Scope statement of underlying model")
    calculation_version: str = Field(..., description="Version of risk calculation logic")
    non_medical_disclaimer: str = Field(..., description="Mandatory non-medical operational risk disclaimer")


class RiskSummary(BaseModel):
    """Backward-compatible summary schema."""

    risk_level: str = Field(..., description="Calculated public health risk level: LOW, MODERATE, HIGH, CRITICAL")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Risk assessment confidence (0-100)")
    contributing_signals: List[str] = Field(default_factory=list, description="List of primary contributing factor tags")
    affected_zone: Optional[str] = Field(None, description="Affected municipal ward or corridor zone name")
