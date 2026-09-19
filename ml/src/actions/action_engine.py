"""
VayuDrishti — Authority Action Recommendation Engine (Phase 1E-J2E.4.3)

Transforms RiskAssessmentResult and spatial hotspot/context evidence into auditable,
deterministic decision-support ActionRecommendationResult objects.
Enforces deterministic rule precedence, action deduplication, timestamp validity,
data quality gating, non-causal language, and mandatory human review.
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ml.src.forecasting.feature_assembler import STATION_ALIAS_MAP
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp
from ml.src.risk.risk_engine import CANONICAL_STATION_ID
from ml.src.risk.risk_schemas import RiskAssessmentResult
from ml.src.actions.action_config import ActionConfig
from ml.src.actions.action_schemas import (
    ActionRecommendation,
    ActionRecommendationInput,
    ActionRecommendationResult,
)

logger = logging.getLogger(__name__)


class ActionRecommendationEngine:
    """
    Deterministic Authority Action Recommendation Engine (Decision Support Only).

    Transforms risk assessment results and explicit context inputs into time-bounded,
    prioritized, human-reviewable action recommendations.
    """

    def __init__(self, config: Optional[ActionConfig] = None):
        self.config = config or ActionConfig()

    def normalize_station_id(self, station_id: str) -> Optional[str]:
        """Maps station alias to canonical station ID."""
        if not station_id:
            return None
        return STATION_ALIAS_MAP.get(station_id.strip())

    def recommend_actions(
        self, input_data: ActionRecommendationInput
    ) -> ActionRecommendationResult:
        """
        Generates deterministic decision-support action recommendations for input_data.
        """
        result_id = f"act_{uuid.uuid4().hex[:12]}"
        risk_res = input_data.risk_result

        # 1. Station Scope Validation
        canonical_id = self.normalize_station_id(risk_res.station_id)
        if not canonical_id or canonical_id != CANONICAL_STATION_ID:
            return ActionRecommendationResult(
                result_id=result_id,
                station_id=risk_res.station_id or "UNKNOWN",
                assessment_id=risk_res.assessment_id,
                created_timestamp=risk_res.assessment_timestamp,
                expires_timestamp=risk_res.assessment_timestamp,
                recommendations=[],
                status="BLOCKED",
                reason_codes=["UNSUPPORTED_STATION_SCOPE"],
                evidence_references=risk_res.evidence_references,
            )

        # 2. Data Quality Gate — Blocked Risk Check (Step 15)
        if risk_res.data_quality_status == "BLOCKED" or risk_res.risk_level in ["BLOCKED", "UNSUPPORTED_STATION_SCOPE"]:
            return ActionRecommendationResult(
                result_id=result_id,
                station_id=CANONICAL_STATION_ID,
                assessment_id=risk_res.assessment_id,
                created_timestamp=risk_res.assessment_timestamp,
                expires_timestamp=risk_res.assessment_timestamp,
                recommendations=[],
                status="BLOCKED",
                reason_codes=["RISK_ASSESSMENT_BLOCKED"] + risk_res.reason_codes,
                evidence_references=risk_res.evidence_references,
            )

        # 3. Timestamp Validation & Validity Window Calculation (Step 13)
        try:
            assessment_dt = parse_utc_timestamp(risk_res.assessment_timestamp)
        except Exception as e:
            return ActionRecommendationResult(
                result_id=result_id,
                station_id=CANONICAL_STATION_ID,
                assessment_id=risk_res.assessment_id,
                created_timestamp=risk_res.assessment_timestamp,
                expires_timestamp=risk_res.assessment_timestamp,
                recommendations=[],
                status="BLOCKED",
                reason_codes=["INVALID_TIMESTAMP", f"Timestamp error: {e}"],
                evidence_references=risk_res.evidence_references,
            )

        created_timestamp = assessment_dt.isoformat().replace("+00:00", "Z")
        expires_dt = assessment_dt + timedelta(minutes=self.config.default_validity_minutes)
        expires_timestamp = expires_dt.isoformat().replace("+00:00", "Z")

        # 4. Context Extraction — Explicit input or risk flags (CORRECTION 2)
        ind_ctx = input_data.industrial_context if input_data.industrial_context is not None else ("INDUSTRIAL_CONTEXT_PRESENT" in risk_res.reason_codes)
        road_ctx = input_data.major_road_context if input_data.major_road_context is not None else ("MAJOR_ROAD_CONTEXT_PRESENT" in risk_res.reason_codes)
        sens_ctx = input_data.sensitive_receptor_context if input_data.sensitive_receptor_context is not None else ("SENSITIVE_RECEPTOR_CONTEXT_PRESENT" in risk_res.reason_codes)
        hotspot_supp = input_data.hotspot_support_score if input_data.hotspot_support_score is not None else (risk_res.score_breakdown.hotspot_corroboration > 0.0)

        # 5. Rule-Based Trigger Execution (Step 4 & CORRECTION 3)
        raw_candidates: List[Dict[str, Any]] = []

        # Rule 1: Baseline / Routine Air Quality Monitoring
        raw_candidates.append({
            "action_type": "MONITOR_LOCAL_AIR_QUALITY",
            "priority": "INFORMATIONAL" if risk_res.risk_level == "LOW" else ("WATCH" if risk_res.risk_level == "MODERATE" else "PRIORITY"),
            "trigger_condition": f"Risk level is {risk_res.risk_level}.",
            "reason_code": "ACTION_BASELINE_MONITORING",
        })

        # Rule 2: Persistent High Forecast Monitoring
        if risk_res.risk_level in ["HIGH", "VERY_HIGH"] and "FORECAST_PERSISTENT" in risk_res.reason_codes:
            raw_candidates.append({
                "action_type": "MONITOR_LOCAL_AIR_QUALITY",
                "priority": "URGENT_REVIEW" if risk_res.risk_level == "VERY_HIGH" else "PRIORITY",
                "trigger_condition": f"Persistent {risk_res.risk_level} risk forecast across all horizons.",
                "reason_code": "ACTION_PERSISTENT_FORECAST",
            })

        # Rule 3: Corroborated Hotspot Inspection Priority
        if risk_res.risk_level in ["MODERATE", "HIGH", "VERY_HIGH"] and (hotspot_supp or "HOTSPOT_CORROBORATED" in risk_res.reason_codes):
            raw_candidates.append({
                "action_type": "INCREASE_INSPECTION_PRIORITY",
                "priority": "URGENT_REVIEW" if risk_res.risk_level == "VERY_HIGH" else "PRIORITY",
                "trigger_condition": f"{risk_res.risk_level} risk corroborated by thermal/PM hotspot evidence.",
                "reason_code": "ACTION_HOTSPOT_REVIEW",
            })

        # Rule 4: Industrial Context Review
        if risk_res.risk_level in ["MODERATE", "HIGH", "VERY_HIGH"] and ind_ctx:
            raw_candidates.append({
                "action_type": "REVIEW_INDUSTRIAL_ACTIVITY",
                "priority": "PRIORITY" if risk_res.risk_level in ["HIGH", "VERY_HIGH"] else "WATCH",
                "trigger_condition": f"{risk_res.risk_level} risk in designated industrial context area.",
                "reason_code": "ACTION_INDUSTRIAL_CONTEXT_REVIEW",
            })

        # Rule 5: Major Road Traffic Condition Review
        if risk_res.risk_level in ["MODERATE", "HIGH", "VERY_HIGH"] and road_ctx:
            raw_candidates.append({
                "action_type": "REVIEW_MAJOR_ROAD_TRAFFIC_CONDITIONS",
                "priority": "PRIORITY" if risk_res.risk_level in ["HIGH", "VERY_HIGH"] else "WATCH",
                "trigger_condition": f"{risk_res.risk_level} risk along arterial transportation corridor.",
                "reason_code": "ACTION_TRAFFIC_CONTEXT_REVIEW",
            })

        # Rule 6: Sensitive Receptor Exposure Verification
        if risk_res.risk_level in ["MODERATE", "HIGH", "VERY_HIGH"] and sens_ctx:
            raw_candidates.append({
                "action_type": "VERIFY_SENSITIVE_RECEPTOR_EXPOSURE_CONTEXT",
                "priority": "URGENT_REVIEW" if risk_res.risk_level == "VERY_HIGH" else "PRIORITY",
                "trigger_condition": f"{risk_res.risk_level} risk in proximity to sensitive receptors (schools/hospitals).",
                "reason_code": "ACTION_SENSITIVE_RECEPTOR_MONITORING",
            })

        # Rule 7: Public Advisory Recommendation
        if risk_res.risk_level in ["HIGH", "VERY_HIGH"] and "FORECAST_PERSISTENT" in risk_res.reason_codes:
            raw_candidates.append({
                "action_type": "ISSUE_PUBLIC_INFORMATION_ADVISORY",
                "priority": "URGENT_REVIEW" if risk_res.risk_level == "VERY_HIGH" else "PRIORITY",
                "trigger_condition": f"Persistent {risk_res.risk_level} risk level warrants public awareness.",
                "reason_code": "ACTION_PUBLIC_ADVISORY_RECOMMENDED",
            })

        # Rule 8: High Uncertainty Expanded Monitoring (Step 6)
        if "FORECAST_UNCERTAINTY_HIGH" in risk_res.reason_codes or risk_res.score_breakdown.uncertainty > 7.5:
            raw_candidates.append({
                "action_type": "EXPAND_LOCAL_MONITORING",
                "priority": "WATCH",
                "trigger_condition": "High prediction interval uncertainty detected; verification recommended.",
                "reason_code": "ACTION_HIGH_UNCERTAINTY_VERIFY",
            })

        # 6. Deduplication & Precedence Merging (CORRECTION 3)
        grouped: Dict[str, Dict[str, Any]] = {}
        for cand in raw_candidates:
            atype = cand["action_type"]
            if atype not in grouped:
                grouped[atype] = {
                    "action_type": atype,
                    "priority": cand["priority"],
                    "trigger_conditions": [cand["trigger_condition"]],
                    "reason_codes": [cand["reason_code"]],
                }
            else:
                existing = grouped[atype]
                existing["priority"] = self.config.get_highest_priority(existing["priority"], cand["priority"])
                if cand["trigger_condition"] not in existing["trigger_conditions"]:
                    existing["trigger_conditions"].append(cand["trigger_condition"])
                if cand["reason_code"] not in existing["reason_codes"]:
                    existing["reason_codes"].append(cand["reason_code"])

        # 7. Construct Final Action Recommendations in Deterministic Order
        recommendations: List[ActionRecommendation] = []
        for atype in self.config.action_types:
            if atype in grouped:
                g = grouped[atype]
                template = self.config.action_templates[atype]
                rec_id = f"rec_{uuid.uuid4().hex[:12]}"

                # Merge supporting evidence references
                evidence_dict = {
                    "forecast_result_id": input_data.forecast_result_id or risk_res.evidence_references.get("forecast_result_id"),
                    "hotspot_id": input_data.hotspot_id or risk_res.evidence_references.get("hotspot_id"),
                    "fusion_id": input_data.fusion_id or risk_res.evidence_references.get("fusion_id"),
                    "context_artifact_id": input_data.context_artifact_id or risk_res.evidence_references.get("context_artifact_id"),
                }

                recommendations.append(
                    ActionRecommendation(
                        recommendation_id=rec_id,
                        action_type=atype,
                        priority=g["priority"],
                        title=template["title"],
                        description=template["description"],
                        expected_objective=template["objective"],
                        trigger_conditions=g["trigger_conditions"],
                        reason_codes=g["reason_codes"],
                        supporting_evidence=evidence_dict,
                        station_id=CANONICAL_STATION_ID,
                        created_timestamp=created_timestamp,
                        expires_timestamp=expires_timestamp,
                        requires_human_review=True,  # Mandatory True (CORRECTION 4)
                        calculation_version=self.config.action_config_version,
                    )
                )

        # 8. Determine Overall Status & Reasons
        overall_status = "PARTIAL" if risk_res.data_quality_status == "PARTIAL" else "READY"
        overall_reasons = list(dict.fromkeys(risk_res.reason_codes + [r for rec in recommendations for r in rec.reason_codes]))

        return ActionRecommendationResult(
            result_id=result_id,
            station_id=CANONICAL_STATION_ID,
            assessment_id=risk_res.assessment_id,
            created_timestamp=created_timestamp,
            expires_timestamp=expires_timestamp,
            recommendations=recommendations,
            status=overall_status,
            reason_codes=overall_reasons,
            evidence_references=risk_res.evidence_references,
            model_scope="Anand Vihar 8118 station-level pilot",
            calculation_version=self.config.action_config_version,
            requires_human_review=True,
        )
