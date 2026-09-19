"""
VayuDrishti — Authority Action Recommendation Engine Package (Phase 1E-J2E.4.3)

Provides deterministic, rule-based decision-support action recommendations from
RiskAssessmentResult and spatial hotspot/context evidence.
"""

from ml.src.actions.action_config import ActionConfig
from ml.src.actions.action_engine import ActionRecommendationEngine
from ml.src.actions.action_schemas import (
    ActionRecommendation,
    ActionRecommendationInput,
    ActionRecommendationResult,
)

__all__ = [
    "ActionConfig",
    "ActionRecommendationEngine",
    "ActionRecommendationInput",
    "ActionRecommendation",
    "ActionRecommendationResult",
]
