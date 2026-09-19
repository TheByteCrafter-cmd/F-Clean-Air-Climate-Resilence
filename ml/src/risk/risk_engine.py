"""
VayuDrishti — Forecast-Aware Risk Assessment Engine (Phase 1E-J2E.4.1)

Computes transparent, auditable 0-100 environmental risk scores, risk level bands,
score component breakdowns, machine-readable reason codes, evidence references,
and data quality flags from validated forecast, hotspot, and context inputs.
"""

import math
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ml.src.forecasting.feature_assembler import STATION_ALIAS_MAP
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp
from ml.src.risk.risk_config import RiskConfig
from ml.src.risk.risk_schemas import (
    RiskAssessmentInput,
    RiskAssessmentResult,
    RiskComponentBreakdown,
)

logger = logging.getLogger(__name__)

CANONICAL_STATION_ID = "ANAND_VIHAR_8118"


class RiskAssessmentEngine:
    """
    Deterministic environmental risk assessment engine.
    Computes bounded 0-100 risk scores with 5 auditable components:
    1. Forecast Severity (0-40)
    2. Forecast Persistence (0-20)
    3. Uncertainty (0-15)
    4. Hotspot Corroboration (0-15)
    5. Spatial/Exposure Context (0-10)
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        self.config = config or RiskConfig()

    def normalize_station_id(self, station_id: str) -> Optional[str]:
        """Maps station alias to canonical station ID."""
        if not station_id:
            return None
        return STATION_ALIAS_MAP.get(station_id.strip())

    def assess_risk(self, input_data: RiskAssessmentInput) -> RiskAssessmentResult:
        """
        Executes deterministic environmental risk assessment for input_data.
        """
        assessment_id = f"risk_{uuid.uuid4().hex[:12]}"

        # 1. Station Scope Validation
        canonical_id = self.normalize_station_id(input_data.station_id)
        if not canonical_id or canonical_id != CANONICAL_STATION_ID:
            return RiskAssessmentResult(
                assessment_id=assessment_id,
                station_id=input_data.station_id or "UNKNOWN",
                assessment_timestamp=input_data.assessment_timestamp,
                forecast_generated_timestamp=input_data.forecast_generated_timestamp,
                forecast_age_minutes=0.0,
                risk_score=0.0,
                risk_level="UNSUPPORTED_STATION_SCOPE",
                score_breakdown=RiskComponentBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
                reason_codes=["UNSUPPORTED_STATION_SCOPE"],
                evidence_references={"forecast_result_id": input_data.forecast_result_id},
                data_quality_status="BLOCKED",
                hotspot_missing=True,
                context_missing=True,
            )

        # 2. Timestamp Syntax & Freshness Auditing (CORRECTION 2)
        try:
            assessment_dt = parse_utc_timestamp(input_data.assessment_timestamp)
            forecast_gen_dt = parse_utc_timestamp(input_data.forecast_generated_timestamp)
        except Exception as e:
            return RiskAssessmentResult(
                assessment_id=assessment_id,
                station_id=CANONICAL_STATION_ID,
                assessment_timestamp=input_data.assessment_timestamp,
                forecast_generated_timestamp=input_data.forecast_generated_timestamp,
                forecast_age_minutes=0.0,
                risk_score=0.0,
                risk_level="BLOCKED",
                score_breakdown=RiskComponentBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
                reason_codes=["INVALID_TIMESTAMP", f"Timestamp parse error: {e}"],
                evidence_references={"forecast_result_id": input_data.forecast_result_id},
                data_quality_status="BLOCKED",
                hotspot_missing=True,
                context_missing=True,
            )

        forecast_age_min = (assessment_dt - forecast_gen_dt).total_seconds() / 60.0
        if forecast_age_min < 0.0:
            return RiskAssessmentResult(
                assessment_id=assessment_id,
                station_id=CANONICAL_STATION_ID,
                assessment_timestamp=input_data.assessment_timestamp,
                forecast_generated_timestamp=input_data.forecast_generated_timestamp,
                forecast_age_minutes=round(forecast_age_min, 1),
                risk_score=0.0,
                risk_level="BLOCKED",
                score_breakdown=RiskComponentBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
                reason_codes=["INVALID_TIMESTAMP", "Forecast generated timestamp is in the future relative to assessment timestamp."],
                evidence_references={"forecast_result_id": input_data.forecast_result_id},
                data_quality_status="BLOCKED",
                hotspot_missing=True,
                context_missing=True,
            )

        if forecast_age_min > self.config.max_forecast_age_minutes:
            return RiskAssessmentResult(
                assessment_id=assessment_id,
                station_id=CANONICAL_STATION_ID,
                assessment_timestamp=input_data.assessment_timestamp,
                forecast_generated_timestamp=input_data.forecast_generated_timestamp,
                forecast_age_minutes=round(forecast_age_min, 1),
                risk_score=0.0,
                risk_level="BLOCKED",
                score_breakdown=RiskComponentBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
                reason_codes=["STALE_FORECAST", f"Forecast age {round(forecast_age_min, 1)} min > {self.config.max_forecast_age_minutes} min threshold"],
                evidence_references={"forecast_result_id": input_data.forecast_result_id},
                data_quality_status="BLOCKED",
                hotspot_missing=True,
                context_missing=True,
            )

        # 3. Forecast Telemetry Validation
        preds = [input_data.predicted_pm25_1h, input_data.predicted_pm25_3h, input_data.predicted_pm25_6h]
        if any(p is None or math.isnan(p) or math.isinf(p) for p in preds):
            return RiskAssessmentResult(
                assessment_id=assessment_id,
                station_id=CANONICAL_STATION_ID,
                assessment_timestamp=input_data.assessment_timestamp,
                forecast_generated_timestamp=input_data.forecast_generated_timestamp,
                forecast_age_minutes=round(forecast_age_min, 1),
                risk_score=0.0,
                risk_level="BLOCKED",
                score_breakdown=RiskComponentBreakdown(0.0, 0.0, 0.0, 0.0, 0.0),
                reason_codes=["MISSING_FORECAST_DATA"],
                evidence_references={"forecast_result_id": input_data.forecast_result_id},
                data_quality_status="BLOCKED",
                hotspot_missing=True,
                context_missing=True,
            )

        reasons: List[str] = []

        # A. Forecast Severity Component (0-40 pts) — CORRECTION 1
        p_peak = max(preds)
        p_mean = sum(preds) / 3.0
        p_eff = 0.6 * p_peak + 0.4 * p_mean

        severity_score = self.config.compute_severity_score(p_eff)
        if p_eff >= self.config.elevated_pm25_threshold:
            reasons.append("FORECAST_PM25_ELEVATED")

        # B. Forecast Persistence Component (0-20 pts) — CORRECTION 1
        elevated_count = sum(1 for p in preds if p >= self.config.elevated_pm25_threshold)
        if elevated_count == 3:
            persistence_score = 20.0
            reasons.append("FORECAST_PERSISTENT")
        elif elevated_count == 2:
            persistence_score = 10.0
            reasons.append("FORECAST_MODERATELY_PERSISTENT")
        else:
            persistence_score = 0.0
            reasons.append("FORECAST_SHORT_LIVED")

        # C. Uncertainty Component (0-15 pts) — CORRECTION 3
        # Relative 90% interval widths
        w_1h = (input_data.pm25_1h_upper_90 - input_data.pm25_1h_lower_90) / max(10.0, abs(input_data.predicted_pm25_1h))
        w_3h = (input_data.pm25_3h_upper_90 - input_data.pm25_3h_lower_90) / max(10.0, abs(input_data.predicted_pm25_3h))
        w_6h = (input_data.pm25_6h_upper_90 - input_data.pm25_6h_lower_90) / max(10.0, abs(input_data.predicted_pm25_6h))
        w_avg = (w_1h + w_3h + w_6h) / 3.0

        uncertainty_score = round(min(15.0, w_avg * 15.0), 2)
        if w_avg > 0.5:
            reasons.append("FORECAST_UNCERTAINTY_HIGH")

        # D. Hotspot Corroboration Component (0-15 pts) — CORRECTION 4
        hotspot_missing = (input_data.hotspot_support_score is None)
        hotspot_score = 0.0
        if not hotspot_missing and input_data.hotspot_support_score > 0.0:
            supp_score = min(100.0, max(0.0, float(input_data.hotspot_support_score)))
            hotspot_score = round(min(15.0, (supp_score / 100.0) * 15.0), 2)
            reasons.append("HOTSPOT_CORROBORATED")

        # E. Spatial / Exposure Context Component (0-10 pts)
        context_missing = not (
            input_data.industrial_context or input_data.major_road_context or input_data.sensitive_receptor_context
        )
        context_score = 0.0
        if input_data.industrial_context:
            context_score += self.config.context_modifiers["industrial_context"]
            reasons.append("INDUSTRIAL_CONTEXT_PRESENT")
        if input_data.major_road_context:
            context_score += self.config.context_modifiers["major_road_context"]
            reasons.append("MAJOR_ROAD_CONTEXT_PRESENT")
        if input_data.sensitive_receptor_context:
            context_score += self.config.context_modifiers["sensitive_receptor_context"]
            reasons.append("SENSITIVE_RECEPTOR_CONTEXT_PRESENT")

        context_score = round(min(10.0, context_score), 2)

        # 4. Total Bounded Score & Level Mapping — CORRECTION 3 Capping
        raw_total = severity_score + persistence_score + uncertainty_score + hotspot_score + context_score
        total_risk_score = round(min(100.0, raw_total), 2)
        risk_level = self.config.map_score_to_level(total_risk_score, severity_score)

        # 5. Data Quality Status — CORRECTION 5
        if hotspot_missing or context_missing:
            data_quality_status = "PARTIAL"
        else:
            data_quality_status = "READY"

        breakdown = RiskComponentBreakdown(
            forecast_severity=severity_score,
            forecast_persistence=persistence_score,
            uncertainty=uncertainty_score,
            hotspot_corroboration=hotspot_score,
            context=context_score,
        )

        evidence_refs = {
            "forecast_result_id": input_data.forecast_result_id,
            "hotspot_id": input_data.hotspot_id,
            "fusion_id": input_data.fusion_id,
            "context_artifact_id": input_data.context_artifact_id,
        }

        return RiskAssessmentResult(
            assessment_id=assessment_id,
            station_id=CANONICAL_STATION_ID,
            assessment_timestamp=input_data.assessment_timestamp,
            forecast_generated_timestamp=input_data.forecast_generated_timestamp,
            forecast_age_minutes=round(forecast_age_min, 1),
            risk_score=total_risk_score,
            risk_level=risk_level,
            score_breakdown=breakdown,
            reason_codes=reasons,
            evidence_references=evidence_refs,
            data_quality_status=data_quality_status,
            hotspot_missing=hotspot_missing,
            context_missing=context_missing,
            model_scope="Anand Vihar 8118 station-level pilot",
            calculation_version=self.config.config_version,
        )
