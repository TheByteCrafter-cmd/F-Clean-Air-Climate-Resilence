"""
VayuDrishti — Authority Action Recommendation Schemas (Phase 1E-J2E.4.3)

Defines dataclasses and Pydantic validation contracts for action inputs,
individual action recommendations, and overall recommendation results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ml.src.risk.risk_schemas import RiskAssessmentResult


@dataclass
class ActionRecommendationInput:
    """Explicit input contract for ActionRecommendationEngine (CORRECTION 2)."""

    risk_result: RiskAssessmentResult
    industrial_context: Optional[bool] = None
    major_road_context: Optional[bool] = None
    sensitive_receptor_context: Optional[bool] = None
    hotspot_detected: Optional[bool] = None
    hotspot_id: Optional[str] = None
    hotspot_support_score: Optional[float] = None
    hotspot_spatial_extent: Optional[float] = None
    hotspot_source_families: Optional[List[str]] = None
    forecast_result_id: Optional[str] = None
    fusion_id: Optional[str] = None
    context_artifact_id: Optional[str] = None


@dataclass
class ActionRecommendation:
    """Dataclass contract for an individual decision-support action recommendation."""

    recommendation_id: str
    action_type: str
    priority: str  # INFORMATIONAL, WATCH, PRIORITY, URGENT_REVIEW
    title: str
    description: str
    expected_objective: str
    trigger_conditions: List[str]
    reason_codes: List[str]
    supporting_evidence: Dict[str, Optional[str]]
    station_id: str
    created_timestamp: str
    expires_timestamp: str
    requires_human_review: bool = True  # Mandatory True (CORRECTION 4)
    calculation_version: str = "1.0"
    non_medical_disclaimer: str = (
        "VayuDrishti action recommendations are operational environmental decision-support suggestions "
        "for human authority review. They do NOT constitute medical advice, clinical diagnosis, or patient care recommendations."
    )
    non_causal_disclaimer: str = (
        "Action recommendations identify environmental risk contexts for operational review. "
        "They do NOT establish legal liability or definitive source attribution."
    )


@dataclass
class ActionRecommendationResult:
    """Dataclass contract for the canonical action recommendation output artifact."""

    result_id: str
    station_id: str
    assessment_id: str
    created_timestamp: str
    expires_timestamp: str
    recommendations: List[ActionRecommendation] = field(default_factory=list)
    status: str = "READY"  # READY, PARTIAL, BLOCKED, EXPIRED
    reason_codes: List[str] = field(default_factory=list)
    evidence_references: Dict[str, Optional[str]] = field(default_factory=dict)
    model_scope: str = "Anand Vihar 8118 station-level pilot"
    calculation_version: str = "1.0"
    requires_human_review: bool = True  # Mandatory True (CORRECTION 4)
    non_medical_disclaimer: str = (
        "VayuDrishti action recommendations are operational environmental decision-support suggestions "
        "for human authority review. They do NOT constitute medical advice, clinical diagnosis, or patient care recommendations."
    )
