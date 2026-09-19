"""
VayuDrishti — Authority Action Recommendation Engine Configuration (Phase 1E-J2E.4.3)

Defines versioned action catalog, priority level hierarchy, time validity policies,
and non-causal decision-support message templates.
"""

from typing import Dict, List


class ActionConfig:
    """Versioned configuration for deterministic action recommendation generation."""

    def __init__(
        self,
        action_config_version: str = "1.0",
        default_validity_minutes: float = 120.0,
    ):
        self.action_config_version = action_config_version
        self.default_validity_minutes = default_validity_minutes

        # Priority Level Hierarchy (Numeric rank for deterministic comparison)
        self.priority_rank: Dict[str, int] = {
            "INFORMATIONAL": 1,
            "WATCH": 2,
            "PRIORITY": 3,
            "URGENT_REVIEW": 4,
        }

        # Catalog of Supported Action Types
        self.action_types: List[str] = [
            "MONITOR_LOCAL_AIR_QUALITY",
            "INCREASE_INSPECTION_PRIORITY",
            "REVIEW_INDUSTRIAL_ACTIVITY",
            "REVIEW_MAJOR_ROAD_TRAFFIC_CONDITIONS",
            "VERIFY_SENSITIVE_RECEPTOR_EXPOSURE_CONTEXT",
            "ISSUE_PUBLIC_INFORMATION_ADVISORY",
            "EXPAND_LOCAL_MONITORING",
        ]

        # Non-Causal Decision-Support Action Templates
        self.action_templates: Dict[str, Dict[str, str]] = {
            "MONITOR_LOCAL_AIR_QUALITY": {
                "title": "Local Air Quality Monitoring",
                "description": (
                    "Routine or enhanced air quality monitoring recommended for station area "
                    "to track PM2.5 forecast trend evolution."
                ),
                "objective": "Maintain situational awareness and track forecast progression.",
            },
            "INCREASE_INSPECTION_PRIORITY": {
                "title": "Elevate Field Inspection Priority",
                "description": (
                    "Increased inspection priority recommended for local enforcement teams "
                    "given elevated forecast risk and corroborating hotspot evidence."
                ),
                "objective": "Target field inspection resources toward corroborated high-risk zones.",
            },
            "REVIEW_INDUSTRIAL_ACTIVITY": {
                "title": "Industrial-Context Activity Review",
                "description": (
                    "Review of local industrial activity and emission compliance recommended "
                    "given elevated forecast risk in an industrial-context area."
                ),
                "objective": "Verify operational emission controls in industrial proximity.",
            },
            "REVIEW_MAJOR_ROAD_TRAFFIC_CONDITIONS": {
                "title": "Major-Road Traffic Condition Review",
                "description": (
                    "Review of arterial traffic congestion and dust suppression measures recommended "
                    "given elevated forecast risk along major traffic corridors."
                ),
                "objective": "Assess traffic corridor management and road dust control measures.",
            },
            "VERIFY_SENSITIVE_RECEPTOR_EXPOSURE_CONTEXT": {
                "title": "Sensitive Receptor Exposure Verification",
                "description": (
                    "Verification of exposure mitigation for sensitive receptors (schools, hospitals, care centers) "
                    "recommended given elevated environmental risk."
                ),
                "objective": "Confirm protective measures for vulnerable community populations.",
            },
            "ISSUE_PUBLIC_INFORMATION_ADVISORY": {
                "title": "Public Environmental Information Advisory",
                "description": (
                    "Issuance of public environmental information advisory recommended to provide "
                    "community awareness regarding persistent high PM2.5 forecast levels."
                ),
                "objective": "Inform local population to reduce outdoor physical exertion during peak hours.",
            },
            "EXPAND_LOCAL_MONITORING": {
                "title": "Verification & Expanded Monitoring",
                "description": (
                    "Expanded sensor verification or mobile monitoring recommended "
                    "to resolve high forecast uncertainty or verify uncorroborated risk signals."
                ),
                "objective": "Reduce prediction uncertainty through targeted local verification.",
            },
        }

    def get_highest_priority(self, p1: str, p2: str) -> str:
        """Returns the higher priority level between p1 and p2 based on deterministic rank."""
        rank1 = self.priority_rank.get(p1, 0)
        rank2 = self.priority_rank.get(p2, 0)
        return p1 if rank1 >= rank2 else p2
