"""
VayuDrishti — Controlled Live Pilot Readiness & Freshness Orchestrator (Phase 1E-J2E.4.9)

Orchestrates the end-to-end controlled live pilot verification flow:
OpenAQ Live + Open-Meteo Live -> Feature Assembler -> Forecast Inference ->
Risk Assessment -> Action Recommendation -> Decision Intelligence Orchestrator.

Enforces:
- Deterministic readiness and freshness status gates (READY, PARTIAL, BLOCKED)
- Explicit data_mode ('CONTROLLED_LIVE' vs 'OFFLINE_TEST')
- Permanent production_validation_status ('NOT_PRODUCTION_VALIDATED')
- Credential-safe behavior when OPENAQ_API_KEY is missing
- Atomic JSON caching to data/processed/decision/live_pilot_decision.json
- Zero model retraining, zero model hash modification, zero frontend modification
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ml.src.actions.action_engine import ActionRecommendationEngine
from ml.src.actions.action_schemas import ActionRecommendationInput
from ml.src.decision.decision_engine import DecisionIntelligenceEngine
from ml.src.decision.decision_schemas import DecisionIntelligenceInput, DecisionIntelligenceResult
from ml.src.forecasting.feature_assembler import ForecastFeatureAssembler
from ml.src.forecasting.inference import ForecastInferenceEngine
from ml.src.forecasting.live_air_quality import LiveAirQualityProvider
from ml.src.forecasting.live_weather import LiveWeatherProvider
from ml.src.forecasting.pipeline import ForecastPipelineService, LiveForecastResult
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp
from ml.src.risk.risk_engine import RiskAssessmentEngine
from ml.src.risk.risk_schemas import RiskAssessmentInput

logger = logging.getLogger(__name__)

CANONICAL_STATION_ID = "ANAND_VIHAR_8118"
DEFAULT_ARTIFACT_PATH = "data/processed/decision/live_pilot_decision.json"
DEFAULT_LIVE_CACHE_DIR = "data/processed/forecasting/live"
PRODUCTION_VALIDATION_STATUS = "NOT_PRODUCTION_VALIDATED"


@dataclass
class FreshnessMetadata:
    """Encapsulates telemetry freshness and availability auditing metrics."""

    air_quality_fresh: bool
    weather_fresh: bool
    overall_live_fresh: bool
    air_quality_age_minutes: Optional[float]
    weather_age_minutes: Optional[float]
    air_quality_latest_timestamp: Optional[str]
    weather_latest_timestamp: Optional[str]
    air_quality_status: str
    weather_status: str
    max_aq_age_allowed_minutes: float = 120.0
    max_weather_age_allowed_minutes: float = 60.0


@dataclass
class ControlledLivePilotResult:
    """Encapsulates the end-to-end controlled live pilot evaluation artifact."""

    data_mode: str  # CONTROLLED_LIVE, OFFLINE_TEST
    production_validation_status: str  # NOT_PRODUCTION_VALIDATED
    station_id: str
    prediction_timestamp: str
    retrieval_timestamp: str
    overall_status: str  # READY, PARTIAL, BLOCKED
    freshness_metadata: Dict[str, Any]
    status_reasons: List[str]
    forecast_result: Dict[str, Any]
    risk_result: Dict[str, Any]
    action_result: Dict[str, Any]
    decision_result: Dict[str, Any]
    cache_provenance: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Converts the result dataclass into a JSON-serializable dictionary."""
        return asdict(self)


class ControlledLivePilotOrchestrator:
    """
    Orchestrates controlled live pilot verification and freshness auditing across
    the entire VayuDrishti intelligence pipeline.
    """

    def __init__(
        self,
        pipeline_service: Optional[ForecastPipelineService] = None,
        risk_engine: Optional[RiskAssessmentEngine] = None,
        action_engine: Optional[ActionRecommendationEngine] = None,
        decision_engine: Optional[DecisionIntelligenceEngine] = None,
        artifact_path: Optional[Union[str, Path]] = None,
        live_cache_dir: Optional[Union[str, Path]] = None,
    ):
        self.pipeline_service = pipeline_service or ForecastPipelineService()
        self.risk_engine = risk_engine or RiskAssessmentEngine()
        self.action_engine = action_engine or ActionRecommendationEngine()
        self.decision_engine = decision_engine or DecisionIntelligenceEngine(
            risk_engine=self.risk_engine,
            action_engine=self.action_engine,
        )
        self.artifact_path = Path(artifact_path or DEFAULT_ARTIFACT_PATH)
        self.live_cache_dir = Path(live_cache_dir or DEFAULT_LIVE_CACHE_DIR)

    def _atomic_save_artifact(self, data: Dict[str, Any]) -> bool:
        """Atomically saves the pilot decision artifact JSON to disk."""
        self.artifact_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.artifact_path.parent / f"{self.artifact_path.name}.tmp_{os.getpid()}_{int(time.time()*1000)}"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.artifact_path)
            return True
        except Exception as e:
            logger.error(f"Failed to save live pilot artifact: {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            return False

    def evaluate_pilot(
        self,
        station_id: str = CANONICAL_STATION_ID,
        prediction_timestamp: Optional[str] = None,
        data_mode: str = "CONTROLLED_LIVE",
        aq_fixtures: Optional[List[Dict[str, Any]]] = None,
        weather_fixtures: Optional[List[Dict[str, Any]]] = None,
        save_artifact: bool = True,
    ) -> ControlledLivePilotResult:
        """
        Executes a controlled live pilot evaluation across Forecast -> Risk -> Action -> Decision Intelligence.
        """
        retrieval_dt = datetime.now(timezone.utc)
        retrieval_ts = retrieval_dt.isoformat().replace("+00:00", "Z")
        mode_str = data_mode.upper()
        if mode_str not in ("CONTROLLED_LIVE", "OFFLINE_TEST"):
            mode_str = "CONTROLLED_LIVE"

        # Determine pipeline execution mode for underlying providers
        provider_mode = "LIVE" if mode_str == "CONTROLLED_LIVE" else "OFFLINE_TEST"

        # 1. Execute Forecast Pipeline Service
        live_forecast_res: LiveForecastResult = self.pipeline_service.execute_live_pipeline(
            station_id=station_id,
            prediction_timestamp=prediction_timestamp,
            mode=provider_mode,
            aq_fixtures=aq_fixtures,
            weather_fixtures=weather_fixtures,
        )

        effective_pred_ts = live_forecast_res.prediction_timestamp

        # 2. Freshness Auditing & Metadata Construction
        aq_status = live_forecast_res.status
        if aq_status in ("LIVE_AQ_UNAVAILABLE", "LIVE_AQ_STALE"):
            aq_fresh = False
        elif aq_status in ("READY", "WEATHER_STALE"):
            aq_fresh = True
        else:
            aq_fresh = False

        weather_age = live_forecast_res.weather_age_minutes
        if weather_age is None or weather_age > 60.0 or live_forecast_res.status == "WEATHER_STALE":
            weather_fresh = False
            w_status = "WEATHER_STALE"
        else:
            weather_fresh = True
            w_status = "READY"

        overall_live_fresh = bool(aq_fresh and weather_fresh)

        freshness_meta = FreshnessMetadata(
            air_quality_fresh=aq_fresh,
            weather_fresh=weather_fresh,
            overall_live_fresh=overall_live_fresh,
            air_quality_age_minutes=live_forecast_res.air_quality_age_minutes,
            weather_age_minutes=weather_age,
            air_quality_latest_timestamp=live_forecast_res.air_quality_source_timestamp,
            weather_latest_timestamp=live_forecast_res.weather_source_timestamp,
            air_quality_status=aq_status,
            weather_status=w_status,
            max_aq_age_allowed_minutes=120.0,
            max_weather_age_allowed_minutes=60.0,
        )

        # 3. Status Gate Precedence Resolution (BLOCKED > PARTIAL > READY)
        status_reasons: List[str] = []

        if live_forecast_res.diagnostic_flags.get("missing_feature_reasons"):
            status_reasons.extend(live_forecast_res.diagnostic_flags["missing_feature_reasons"])

        if mode_str == "CONTROLLED_LIVE" and not aq_fresh:
            if not os.getenv("OPENAQ_API_KEY"):
                status_reasons.append("CONTROLLED LIVE EXECUTION BLOCKED — OPENAQ_API_KEY NOT CONFIGURED")

        # Determine overall quality gate status
        if live_forecast_res.status in ("UNSUPPORTED_STATION", "INVALID_INPUT", "INFERENCE_ERROR"):
            overall_status = "BLOCKED"
        elif live_forecast_res.status == "LIVE_AQ_UNAVAILABLE":
            overall_status = "BLOCKED"
        elif live_forecast_res.status in ("LIVE_AQ_STALE", "WEATHER_STALE", "MISSING_HISTORY"):
            overall_status = "PARTIAL"
        elif live_forecast_res.status == "READY":
            overall_status = "READY"
        else:
            overall_status = "BLOCKED"

        # 4. Construct Decision Intelligence Input Payload
        horizons = live_forecast_res.forecast_results or {}
        p1 = horizons.get("+1h", {})
        p3 = horizons.get("+3h", {})
        p6 = horizons.get("+6h", {})

        p1_val = p1.get("predicted_pm25")
        p1_90 = p1.get("prediction_intervals", {}).get("90_pct", {})
        p1_low = p1_90.get("lower_bound")
        p1_high = p1_90.get("upper_bound")

        p3_val = p3.get("predicted_pm25")
        p3_90 = p3.get("prediction_intervals", {}).get("90_pct", {})
        p3_low = p3_90.get("lower_bound")
        p3_high = p3_90.get("upper_bound")

        p6_val = p6.get("predicted_pm25")
        p6_90 = p6.get("prediction_intervals", {}).get("90_pct", {})
        p6_low = p6_90.get("lower_bound")
        p6_high = p6_90.get("upper_bound")

        forecast_summary_dict = {
            "forecast_result_id": f"fc_live_{int(retrieval_dt.timestamp())}",
            "status": live_forecast_res.status,
            "canonical_station_id": live_forecast_res.canonical_station_id,
            "prediction_timestamp": effective_pred_ts,
            "data_quality_status": overall_status,
            "horizons": horizons,
            "diagnostic_flags": live_forecast_res.diagnostic_flags,
        }

        decision_input = DecisionIntelligenceInput(
            station_id=station_id,
            prediction_timestamp=effective_pred_ts,
            assessment_timestamp=effective_pred_ts,
            forecast_result_id=forecast_summary_dict["forecast_result_id"],

            forecast_result=forecast_summary_dict,
            predicted_pm25_1h=p1_val,
            pm25_1h_lower_90=p1_low,
            pm25_1h_upper_90=p1_high,
            predicted_pm25_3h=p3_val,
            pm25_3h_lower_90=p3_low,
            pm25_3h_upper_90=p3_high,
            predicted_pm25_6h=p6_val,
            pm25_6h_lower_90=p6_low,
            pm25_6h_upper_90=p6_high,
        )

        # 5. Execute Decision Intelligence Engine Composition
        decision_res: DecisionIntelligenceResult = self.decision_engine.orchestrate(decision_input)

        # 6. Extract Intermediate Risk & Action Summaries for Auditing
        risk_summary = {
            "assessment_id": decision_res.risk_reference.get("assessment_id"),
            "risk_score": decision_res.risk_score,
            "risk_level": decision_res.risk_level,
            "data_quality_status": decision_res.risk_status,
        }

        action_summary = {
            "result_id": decision_res.action_reference.get("result_id"),
            "recommendation_count": decision_res.recommendation_count,
            "status": decision_res.action_status,
            "recommendations": [r.model_dump() if hasattr(r, "model_dump") else r for r in decision_res.recommendations],
        }

        # 7. Assemble Controlled Live Pilot Result
        pilot_result = ControlledLivePilotResult(
            data_mode=mode_str,
            production_validation_status=PRODUCTION_VALIDATION_STATUS,
            station_id=live_forecast_res.canonical_station_id,
            prediction_timestamp=effective_pred_ts,
            retrieval_timestamp=retrieval_ts,
            overall_status=overall_status,
            freshness_metadata=asdict(freshness_meta),
            status_reasons=status_reasons,
            forecast_result=forecast_summary_dict,
            risk_result=risk_summary,
            action_result=action_summary,
            decision_result=decision_res.model_dump() if hasattr(decision_res, "model_dump") else decision_res.__dict__,
            cache_provenance={
                "live_cache_dir": str(self.live_cache_dir),
                "artifact_path": str(self.artifact_path),
                "air_quality_source": "OpenAQ_v3_Live" if mode_str == "CONTROLLED_LIVE" else "OpenAQ_v3_Offline",
                "weather_source": "Open-Meteo_Live" if mode_str == "CONTROLLED_LIVE" else "Open-Meteo_Offline",
            },
        )

        # 8. Persist Artifact
        if save_artifact:
            self._atomic_save_artifact(pilot_result.to_dict())

        return pilot_result
