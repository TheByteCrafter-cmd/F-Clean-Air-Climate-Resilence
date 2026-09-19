"""
VayuDrishti — End-to-End Decision Intelligence Orchestrator (Phase 1E-J2E.4.4)

Composes Forecast Inference, Risk Assessment Engine, and Authority Action
Recommendation Engine into a single, auditable DecisionIntelligenceResult.
Enforces deterministic pipeline execution, status precedence (BLOCKED > PARTIAL > READY),
earliest expiry timestamp computation, non-causal decision summary generation,
and mandatory human review.
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from ml.src.forecasting.feature_assembler import STATION_ALIAS_MAP
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp
from ml.src.risk.risk_engine import CANONICAL_STATION_ID, RiskAssessmentEngine
from ml.src.risk.risk_schemas import (
    RiskAssessmentInput,
    RiskAssessmentResult,
    RiskComponentBreakdown,
)
from ml.src.actions.action_engine import ActionRecommendationEngine
from ml.src.actions.action_schemas import (
    ActionRecommendationInput,
    ActionRecommendationResult,
)
from ml.src.decision.decision_config import DecisionConfig
from ml.src.decision.decision_schemas import (
    DecisionIntelligenceInput,
    DecisionIntelligenceResult,
)

logger = logging.getLogger(__name__)


class DecisionIntelligenceEngine:
    """
    Deterministic End-to-End Decision Intelligence Orchestrator.

    Composes forecast inference outputs, risk assessment results, and authority
    action recommendations into a single auditable DecisionIntelligenceResult artifact.
    """

    def __init__(
        self,
        config: Optional[DecisionConfig] = None,
        risk_engine: Optional[RiskAssessmentEngine] = None,
        action_engine: Optional[ActionRecommendationEngine] = None,
    ):
        self.config = config or DecisionConfig()
        self.risk_engine = risk_engine or RiskAssessmentEngine()
        self.action_engine = action_engine or ActionRecommendationEngine()

    def normalize_station_id(self, station_id: str) -> Optional[str]:
        """Maps station alias to canonical station ID."""
        if not station_id:
            return None
        return STATION_ALIAS_MAP.get(station_id.strip())

    def generate_decision_summary(
        self,
        station_id: str,
        risk_score: float,
        risk_level: str,
        recommendation_count: int,
        reason_codes: List[str],
        overall_status: str,
        missing_evidence: List[str],
    ) -> str:
        """
        Constructs a deterministic, non-causal, non-medical decision summary paragraph.
        """
        clean_reasons = [r for r in reason_codes if not r.startswith("ACTION_")]
        top_reasons_str = ", ".join(clean_reasons[:4]) if clean_reasons else "standard monitoring protocol"

        summary = (
            f"Anand Vihar 8118 environmental decision intelligence assessment yields a risk score "
            f"of {risk_score:.1f} ({risk_level} risk level) based on multi-horizon PM2.5 forecasts. "
            f"{recommendation_count} operational decision-support recommendation(s) generated for human "
            f"authority review. Primary assessment factors: [{top_reasons_str}]. "
            f"Overall pipeline status: {overall_status}."
        )

        if missing_evidence:
            summary += f" Missing evidence items noted for follow-up: {', '.join(missing_evidence)}."

        return summary

    def orchestrate(
        self, input_data: DecisionIntelligenceInput
    ) -> DecisionIntelligenceResult:
        """
        Executes end-to-end decision intelligence orchestration pipeline.
        """
        decision_result_id = f"dec_{uuid.uuid4().hex[:12]}"

        # 1. Station Scope Validation
        canonical_id = self.normalize_station_id(input_data.station_id)
        if not canonical_id or canonical_id != CANONICAL_STATION_ID:
            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return DecisionIntelligenceResult(
                decision_result_id=decision_result_id,
                station_id=input_data.station_id or "UNKNOWN",
                prediction_timestamp=input_data.prediction_timestamp or now_iso,
                created_timestamp=now_iso,
                expires_timestamp=now_iso,
                forecast_status="BLOCKED",
                risk_status="BLOCKED",
                action_status="BLOCKED",
                overall_data_quality_status="BLOCKED",
                forecast_reference={"forecast_result_id": input_data.forecast_result_id},
                risk_reference={"assessment_id": None},
                action_reference={"result_id": None},
                evidence_references={
                    "forecast_result_id": input_data.forecast_result_id,
                    "hotspot_id": input_data.hotspot_id,
                    "fusion_id": input_data.fusion_id,
                    "context_artifact_id": input_data.context_artifact_id,
                },
                risk_score=0.0,
                risk_level="UNSUPPORTED_STATION_SCOPE",
                recommendation_count=0,
                recommendations=[],
                missing_evidence=["canonical_station_scope"],
                decision_summary=f"Orchestration blocked: Station '{input_data.station_id}' is outside supported pilot scope (Anand Vihar 8118).",
                requires_human_review=True,
            )

        # 2. Timestamp Normalization & Creation Timestamp
        try:
            pred_dt = parse_utc_timestamp(input_data.prediction_timestamp)
            prediction_ts = pred_dt.isoformat().replace("+00:00", "Z")
        except Exception as e:
            now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            return DecisionIntelligenceResult(
                decision_result_id=decision_result_id,
                station_id=CANONICAL_STATION_ID,
                prediction_timestamp=input_data.prediction_timestamp or now_iso,
                created_timestamp=now_iso,
                expires_timestamp=now_iso,
                forecast_status="BLOCKED",
                risk_status="BLOCKED",
                action_status="BLOCKED",
                overall_data_quality_status="BLOCKED",
                forecast_reference={"forecast_result_id": input_data.forecast_result_id},
                risk_reference={"assessment_id": None},
                action_reference={"result_id": None},
                evidence_references={},
                risk_score=0.0,
                risk_level="BLOCKED",
                recommendation_count=0,
                recommendations=[],
                missing_evidence=["valid_prediction_timestamp"],
                decision_summary=f"Orchestration blocked due to invalid prediction timestamp: {e}",
                requires_human_review=True,
            )

        created_timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        assessment_ts = input_data.assessment_timestamp or prediction_ts

        # 3. Forecast Extraction / Resolution
        forecast_res_id = input_data.forecast_result_id
        forecast_dict = input_data.forecast_result
        if forecast_dict and isinstance(forecast_dict, dict):
            forecast_res_id = forecast_dict.get("forecast_result_id", forecast_res_id)
            if forecast_dict.get("status") == "BLOCKED":
                forecast_status = "BLOCKED"
            else:
                forecast_status = forecast_dict.get("data_quality_status", "READY")
            
            # Extract horizons if not explicitly provided
            horizons = forecast_dict.get("horizons", {})
            if input_data.predicted_pm25_1h is None and "+1h" in horizons:
                input_data.predicted_pm25_1h = horizons["+1h"].get("predicted_pm25")
                p1_intervals = horizons["+1h"].get("prediction_intervals", {}).get("90_pct", {})
                input_data.pm25_1h_lower_90 = p1_intervals.get("lower_bound")
                input_data.pm25_1h_upper_90 = p1_intervals.get("upper_bound")

            if input_data.predicted_pm25_3h is None and "+3h" in horizons:
                input_data.predicted_pm25_3h = horizons["+3h"].get("predicted_pm25")
                p3_intervals = horizons["+3h"].get("prediction_intervals", {}).get("90_pct", {})
                input_data.pm25_3h_lower_90 = p3_intervals.get("lower_bound")
                input_data.pm25_3h_upper_90 = p3_intervals.get("upper_bound")

            if input_data.predicted_pm25_6h is None and "+6h" in horizons:
                input_data.predicted_pm25_6h = horizons["+6h"].get("predicted_pm25")
                p6_intervals = horizons["+6h"].get("prediction_intervals", {}).get("90_pct", {})
                input_data.pm25_6h_lower_90 = p6_intervals.get("lower_bound")
                input_data.pm25_6h_upper_90 = p6_intervals.get("upper_bound")
        else:
            # Check presence of required predictions & bounds
            required_preds = [
                input_data.predicted_pm25_1h, input_data.pm25_1h_lower_90, input_data.pm25_1h_upper_90,
                input_data.predicted_pm25_3h, input_data.pm25_3h_lower_90, input_data.pm25_3h_upper_90,
                input_data.predicted_pm25_6h, input_data.pm25_6h_lower_90, input_data.pm25_6h_upper_90,
            ]
            if any(p is None for p in required_preds):
                forecast_status = "PARTIAL" if input_data.predicted_pm25_1h is not None else "BLOCKED"
            else:
                forecast_status = "READY"

        forecast_reference = {
            "forecast_result_id": forecast_res_id or f"fc_{uuid.uuid4().hex[:8]}",
            "status": forecast_status,
            "prediction_timestamp": prediction_ts,
        }

        # 4. Risk Assessment Resolution
        if input_data.risk_result is not None:
            risk_res = input_data.risk_result
        else:
            if forecast_status == "BLOCKED" or input_data.predicted_pm25_1h is None:
                risk_res = RiskAssessmentResult(
                    assessment_id=f"risk_{uuid.uuid4().hex[:12]}",
                    station_id=CANONICAL_STATION_ID,
                    assessment_timestamp=assessment_ts,
                    forecast_generated_timestamp=prediction_ts,
                    forecast_age_minutes=0.0,
                    risk_score=0.0,
                    risk_level="BLOCKED",
                    score_breakdown=RiskComponentBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
                    reason_codes=["FORECAST_DATA_UNAVAILABLE"],
                    evidence_references={"forecast_result_id": forecast_res_id},
                    data_quality_status="BLOCKED",
                    hotspot_missing=True,
                    context_missing=True,
                )
            else:
                risk_input = RiskAssessmentInput(
                    station_id=CANONICAL_STATION_ID,
                    assessment_timestamp=assessment_ts,
                    forecast_generated_timestamp=prediction_ts,
                    predicted_pm25_1h=float(input_data.predicted_pm25_1h),
                    pm25_1h_lower_90=float(input_data.pm25_1h_lower_90 or input_data.predicted_pm25_1h - 15.0),
                    pm25_1h_upper_90=float(input_data.pm25_1h_upper_90 or input_data.predicted_pm25_1h + 15.0),
                    predicted_pm25_3h=float(input_data.predicted_pm25_3h or input_data.predicted_pm25_1h),
                    pm25_3h_lower_90=float(input_data.pm25_3h_lower_90 or input_data.predicted_pm25_3h or input_data.predicted_pm25_1h - 20.0),
                    pm25_3h_upper_90=float(input_data.pm25_3h_upper_90 or input_data.predicted_pm25_3h or input_data.predicted_pm25_1h + 20.0),
                    predicted_pm25_6h=float(input_data.predicted_pm25_6h or input_data.predicted_pm25_1h),
                    pm25_6h_lower_90=float(input_data.pm25_6h_lower_90 or input_data.predicted_pm25_6h or input_data.predicted_pm25_1h - 25.0),
                    pm25_6h_upper_90=float(input_data.pm25_6h_upper_90 or input_data.predicted_pm25_6h or input_data.predicted_pm25_1h + 25.0),
                    hotspot_detected=input_data.hotspot_detected,
                    hotspot_id=input_data.hotspot_id,
                    hotspot_support_score=input_data.hotspot_support_score,
                    hotspot_spatial_extent=input_data.hotspot_spatial_extent,
                    hotspot_source_families=input_data.hotspot_source_families,
                    industrial_context=input_data.industrial_context,
                    major_road_context=input_data.major_road_context,
                    sensitive_receptor_context=input_data.sensitive_receptor_context,
                    forecast_result_id=forecast_res_id,
                    fusion_id=input_data.fusion_id,
                    context_artifact_id=input_data.context_artifact_id,
                )
                risk_res = self.risk_engine.assess_risk(risk_input)

        risk_status = risk_res.data_quality_status if risk_res.risk_level != "BLOCKED" else "BLOCKED"
        risk_reference = {
            "assessment_id": risk_res.assessment_id,
            "risk_score": risk_res.risk_score,
            "risk_level": risk_res.risk_level,
            "data_quality_status": risk_status,
        }

        # 5. Authority Action Recommendations Resolution
        if input_data.action_result is not None:
            action_res = input_data.action_result
        else:
            action_input = ActionRecommendationInput(
                risk_result=risk_res,
                industrial_context=input_data.industrial_context,
                major_road_context=input_data.major_road_context,
                sensitive_receptor_context=input_data.sensitive_receptor_context,
                hotspot_detected=input_data.hotspot_detected,
                hotspot_id=input_data.hotspot_id,
                hotspot_support_score=input_data.hotspot_support_score,
                hotspot_spatial_extent=input_data.hotspot_spatial_extent,
                hotspot_source_families=input_data.hotspot_source_families,
                forecast_result_id=forecast_res_id,
                fusion_id=input_data.fusion_id,
                context_artifact_id=input_data.context_artifact_id,
            )
            action_res = self.action_engine.recommend_actions(action_input)

        action_status = action_res.status
        action_reference = {
            "result_id": action_res.result_id,
            "recommendation_count": len(action_res.recommendations),
            "status": action_status,
        }

        # 6. Overall Data Quality Status Resolution (BLOCKED > PARTIAL > READY)
        overall_status = self.config.resolve_overall_status(
            [forecast_status, risk_status, action_status]
        )

        # 7. Earliest Expiry Timestamp Calculation
        expiry_candidates = []
        try:
            ass_dt = parse_utc_timestamp(risk_res.assessment_timestamp)
            expiry_candidates.append(ass_dt + timedelta(minutes=self.config.default_validity_minutes))
        except Exception:
            pass

        try:
            act_exp_dt = parse_utc_timestamp(action_res.expires_timestamp)
            expiry_candidates.append(act_exp_dt)
        except Exception:
            pass

        if expiry_candidates:
            earliest_exp = min(expiry_candidates)
            expires_timestamp = earliest_exp.isoformat().replace("+00:00", "Z")
        else:
            expires_timestamp = (pred_dt + timedelta(minutes=self.config.default_validity_minutes)).isoformat().replace("+00:00", "Z")

        # 8. Missing Evidence Identification
        missing_evidence: List[str] = []
        if risk_res.hotspot_missing or input_data.hotspot_detected is None:
            missing_evidence.append("hotspot_data")

        if risk_res.context_missing or (
            input_data.industrial_context is None
            and input_data.major_road_context is None
            and input_data.sensitive_receptor_context is None
        ):
            missing_evidence.append("geospatial_context_data")

        if forecast_status != "READY":
            missing_evidence.append("complete_conformal_forecast_horizons")

        # 9. Merged Evidence References
        merged_evidence: Dict[str, Optional[str]] = {
            "forecast_result_id": forecast_res_id or risk_res.evidence_references.get("forecast_result_id"),
            "assessment_id": risk_res.assessment_id,
            "action_result_id": action_res.result_id,
            "hotspot_id": input_data.hotspot_id or risk_res.evidence_references.get("hotspot_id"),
            "fusion_id": input_data.fusion_id or risk_res.evidence_references.get("fusion_id"),
            "context_artifact_id": input_data.context_artifact_id or risk_res.evidence_references.get("context_artifact_id"),
        }

        # 10. Generate Non-Causal Summary
        decision_summary = self.generate_decision_summary(
            station_id=CANONICAL_STATION_ID,
            risk_score=risk_res.risk_score,
            risk_level=risk_res.risk_level,
            recommendation_count=len(action_res.recommendations),
            reason_codes=risk_res.reason_codes,
            overall_status=overall_status,
            missing_evidence=missing_evidence,
        )

        # 11. Final Decision Intelligence Result
        return DecisionIntelligenceResult(
            decision_result_id=decision_result_id,
            station_id=CANONICAL_STATION_ID,
            prediction_timestamp=prediction_ts,
            created_timestamp=created_timestamp,
            expires_timestamp=expires_timestamp,
            forecast_status=forecast_status,
            risk_status=risk_status,
            action_status=action_status,
            overall_data_quality_status=overall_status,
            forecast_reference=forecast_reference,
            risk_reference=risk_reference,
            action_reference=action_reference,
            evidence_references=merged_evidence,
            risk_score=risk_res.risk_score,
            risk_level=risk_res.risk_level,
            recommendation_count=len(action_res.recommendations),
            recommendations=action_res.recommendations,
            missing_evidence=missing_evidence,
            decision_summary=decision_summary,
            requires_human_review=True,  # HARD RULE: Mandatory True (Correction 4)
            model_scope=self.config.model_scope,
            calculation_version=self.config.decision_config_version,
            non_medical_disclaimer=self.config.non_medical_disclaimer,
            non_causal_disclaimer=self.config.non_causal_disclaimer,
        )
