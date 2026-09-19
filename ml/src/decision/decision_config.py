"""
VayuDrishti — Decision Intelligence Orchestrator Config (Phase 1E-J2E.4.4)

Defines configuration parameters, default validity thresholds, disclaimers,
and status precedence for end-to-end decision intelligence orchestration.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class DecisionConfig:
    """Configuration settings for DecisionIntelligenceEngine."""

    decision_config_version: str = "1.0"
    default_validity_minutes: int = 60
    supported_station_id: str = "ANAND_VIHAR_8118"
    model_scope: str = "Anand Vihar 8118 station-level pilot"

    # Status precedence order (BLOCKED > PARTIAL > READY)
    status_precedence: List[str] = field(
        default_factory=lambda: ["BLOCKED", "PARTIAL", "READY"]
    )

    non_medical_disclaimer: str = (
        "VayuDrishti decision intelligence outputs provide operational environmental decision support "
        "for human authority review. They do NOT constitute medical advice, clinical diagnosis, "
        "or patient care recommendations."
    )

    non_causal_disclaimer: str = (
        "Decision intelligence outputs synthesize environmental forecast, risk, and action evidence "
        "for human authority review. They do NOT establish legal liability or definitive source attribution."
    )

    def resolve_overall_status(self, statuses: List[str]) -> str:
        """
        Determines overall data quality status using deterministic precedence:
        BLOCKED > PARTIAL > READY.
        """
        if any(s == "BLOCKED" for s in statuses):
            return "BLOCKED"
        if any(s == "PARTIAL" for s in statuses):
            return "PARTIAL"
        return "READY"
