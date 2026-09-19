"""
VayuDrishti — Live Forecast Pipeline Orchestrator (Phase 1E-J2E.3.2)

Orchestrates controlled live telemetry refresh, atomic persistence caching, freshness auditing,
feature assembly, READY-gate enforcement, and model inference execution.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ml.src.forecasting.feature_assembler import ForecastFeatureAssembler, ForecastFeatureVector
from ml.src.forecasting.inference import ForecastInferenceEngine, InferenceError
from ml.src.forecasting.live_air_quality import LiveAirQualityProvider
from ml.src.forecasting.live_weather import LiveWeatherProvider
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

CANONICAL_STATION_ID = "ANAND_VIHAR_8118"


@dataclass
class LiveForecastResult:
    """Encapsulates the end-to-end operational live forecast result."""

    status: str  # READY, LIVE_AQ_UNAVAILABLE, LIVE_AQ_STALE, WEATHER_STALE, MISSING_HISTORY, UNSUPPORTED_STATION, INVALID_INPUT, INFERENCE_ERROR
    canonical_station_id: str
    prediction_timestamp: str
    air_quality_source_timestamp: Optional[str] = None
    weather_source_timestamp: Optional[str] = None
    air_quality_age_minutes: Optional[float] = None
    weather_age_minutes: Optional[float] = None
    assembly_status: Optional[str] = None
    forecast_results: Optional[Dict[str, Any]] = None
    diagnostic_flags: Dict[str, Any] = field(default_factory=dict)


class ForecastPipelineService:
    """
    Internal service orchestrating live data refresh, atomic local caching, freshness checks,
    feature assembly, READY gate enforcement, and model inference.
    """

    def __init__(
        self,
        aq_provider: Optional[LiveAirQualityProvider] = None,
        weather_provider: Optional[LiveWeatherProvider] = None,
        feature_assembler: Optional[ForecastFeatureAssembler] = None,
        inference_engine: Optional[ForecastInferenceEngine] = None,
        live_cache_dir: Optional[Union[str, Path]] = None,
        mode: str = "LIVE",
    ):
        self.mode = mode.upper()
        self.aq_provider = aq_provider or LiveAirQualityProvider(mode=self.mode)
        self.weather_provider = weather_provider or LiveWeatherProvider(mode=self.mode)
        self.feature_assembler = feature_assembler or ForecastFeatureAssembler()
        self.inference_engine = inference_engine or ForecastInferenceEngine()
        self.cache_dir = Path(live_cache_dir) if live_cache_dir else Path("data/processed/forecasting/live")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _write_atomic_cache(self, filename: str, data: Any) -> bool:
        """Writes JSON payload atomically using temporary file rename to prevent corrupted reads."""
        target_path = self.cache_dir / filename
        temp_path = self.cache_dir / f"{filename}.tmp_{os.getpid()}_{int(time.time()*1000)}"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_path, target_path)
            return True
        except Exception as e:
            logger.error(f"Failed to write atomic cache {filename}: {e}")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            return False

    def execute_live_pipeline(
        self,
        station_id: str = CANONICAL_STATION_ID,
        prediction_timestamp: Optional[str] = None,
        mode: Optional[str] = None,
        aq_fixtures: Optional[List[Dict[str, Any]]] = None,
        weather_fixtures: Optional[List[Dict[str, Any]]] = None,
    ) -> LiveForecastResult:
        """
        Executes end-to-end live forecast refresh, feature assembly, and inference pipeline.
        """
        start_time = time.time()
        exec_mode = (mode or self.mode).upper()

        # Update provider modes if overridden
        self.aq_provider.mode = exec_mode
        self.weather_provider.mode = exec_mode

        # 1. Scope Guardrail
        canonical_id = self.feature_assembler.normalize_station_id(station_id)
        if not canonical_id or canonical_id != CANONICAL_STATION_ID:
            return LiveForecastResult(
                status="UNSUPPORTED_STATION",
                canonical_station_id=canonical_id or "UNKNOWN",
                prediction_timestamp=prediction_timestamp or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                assembly_status="UNSUPPORTED_STATION",
                diagnostic_flags={
                    "model_scope": "station_level_pilot",
                    "data_scope": "live_operational_input",
                    "model_validation_scope": "January 2025 Anand Vihar pilot",
                    "missing_feature_reasons": [f"Station '{station_id}' is unsupported. Canonical station scope: ANAND_VIHAR_8118."],
                },
            )

        # 2. Retrieve Live Telemetry
        aq_res = self.aq_provider.fetch_recent_pm25_history(
            prediction_timestamp=prediction_timestamp,
            fixture_records=aq_fixtures,
        )

        weather_res = self.weather_provider.fetch_recent_weather(
            prediction_timestamp=prediction_timestamp,
            fixture_records=weather_fixtures,
        )

        # 3. Persist Atomic Local Cache
        aq_records = aq_res.get("records", [])
        weather_records = weather_res.get("records", [])

        if aq_records:
            self._write_atomic_cache("live_air_quality.json", aq_records)
        if weather_records:
            self._write_atomic_cache("live_weather.json", weather_records)

        manifest_data = {
            "retrieval_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "mode": exec_mode,
            "station_id": CANONICAL_STATION_ID,
            "sensor_id": aq_res.get("sensor_id"),
            "aq_record_count": len(aq_records),
            "weather_record_count": len(weather_records),
            "aq_latest_timestamp": aq_res.get("latest_timestamp"),
            "weather_latest_timestamp": weather_res.get("latest_timestamp"),
            "aq_source_age_minutes": aq_res.get("source_age_minutes"),
            "weather_source_age_minutes": weather_res.get("source_age_minutes"),
            "aq_status": aq_res.get("status"),
            "weather_status": weather_res.get("status"),
        }
        self._write_atomic_cache("live_refresh_manifest.json", manifest_data)

        # Determine Effective Prediction Timestamp
        effective_ts = prediction_timestamp
        if not effective_ts:
            if aq_res.get("latest_timestamp"):
                effective_ts = aq_res["latest_timestamp"]
            else:
                effective_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        all_reasons: List[str] = []
        all_reasons.extend(aq_res.get("reasons", []))
        all_reasons.extend(weather_res.get("reasons", []))

        # Check Source Freshness & Availability Gates
        if aq_res.get("status") == "INVALID_INPUT":
            return LiveForecastResult(
                status="INVALID_INPUT",
                canonical_station_id=CANONICAL_STATION_ID,
                prediction_timestamp=effective_ts,
                air_quality_source_timestamp=aq_res.get("latest_timestamp"),
                weather_source_timestamp=weather_res.get("latest_timestamp"),
                air_quality_age_minutes=aq_res.get("source_age_minutes"),
                weather_age_minutes=weather_res.get("source_age_minutes"),
                assembly_status="INVALID_INPUT",
                diagnostic_flags={
                    "model_scope": "station_level_pilot",
                    "data_scope": "live_operational_input",
                    "model_validation_scope": "January 2025 Anand Vihar pilot",
                    "missing_feature_reasons": all_reasons,
                },
            )

        if aq_res.get("status") == "LIVE_AQ_UNAVAILABLE":
            return LiveForecastResult(
                status="LIVE_AQ_UNAVAILABLE",
                canonical_station_id=CANONICAL_STATION_ID,
                prediction_timestamp=effective_ts,
                air_quality_source_timestamp=aq_res.get("latest_timestamp"),
                weather_source_timestamp=weather_res.get("latest_timestamp"),
                air_quality_age_minutes=aq_res.get("source_age_minutes"),
                weather_age_minutes=weather_res.get("source_age_minutes"),
                assembly_status="MISSING_HISTORY",
                diagnostic_flags={
                    "model_scope": "station_level_pilot",
                    "data_scope": "live_operational_input",
                    "model_validation_scope": "January 2025 Anand Vihar pilot",
                    "missing_feature_reasons": all_reasons,
                },
            )

        if aq_res.get("status") == "LIVE_AQ_STALE":
            return LiveForecastResult(
                status="LIVE_AQ_STALE",
                canonical_station_id=CANONICAL_STATION_ID,
                prediction_timestamp=effective_ts,
                air_quality_source_timestamp=aq_res.get("latest_timestamp"),
                weather_source_timestamp=weather_res.get("latest_timestamp"),
                air_quality_age_minutes=aq_res.get("source_age_minutes"),
                weather_age_minutes=weather_res.get("source_age_minutes"),
                assembly_status="WEATHER_STALE" if weather_res.get("status") == "WEATHER_STALE" else "READY",
                diagnostic_flags={
                    "model_scope": "station_level_pilot",
                    "data_scope": "live_operational_input",
                    "model_validation_scope": "January 2025 Anand Vihar pilot",
                    "missing_feature_reasons": all_reasons,
                },
            )

        if weather_res.get("status") == "WEATHER_STALE":
            return LiveForecastResult(
                status="WEATHER_STALE",
                canonical_station_id=CANONICAL_STATION_ID,
                prediction_timestamp=effective_ts,
                air_quality_source_timestamp=aq_res.get("latest_timestamp"),
                weather_source_timestamp=weather_res.get("latest_timestamp"),
                air_quality_age_minutes=aq_res.get("source_age_minutes"),
                weather_age_minutes=weather_res.get("source_age_minutes"),
                assembly_status="WEATHER_STALE",
                diagnostic_flags={
                    "model_scope": "station_level_pilot",
                    "data_scope": "live_operational_input",
                    "model_validation_scope": "January 2025 Anand Vihar pilot",
                    "missing_feature_reasons": all_reasons,
                },
            )

        # 4. Feature Assembly
        feature_vector: ForecastFeatureVector = self.feature_assembler.assemble_features(
            station_id=CANONICAL_STATION_ID,
            prediction_timestamp=effective_ts,
            air_quality_records=aq_records,
            weather_records=weather_records,
        )

        all_reasons.extend(feature_vector.missing_feature_reasons)

        # 5. READY Gate Enforcement
        if feature_vector.assembly_status != "READY":
            gate_status = feature_vector.assembly_status
            return LiveForecastResult(
                status=gate_status,
                canonical_station_id=CANONICAL_STATION_ID,
                prediction_timestamp=effective_ts,
                air_quality_source_timestamp=aq_res.get("latest_timestamp"),
                weather_source_timestamp=weather_res.get("latest_timestamp"),
                air_quality_age_minutes=aq_res.get("source_age_minutes"),
                weather_age_minutes=weather_res.get("source_age_minutes"),
                assembly_status=gate_status,
                diagnostic_flags={
                    "model_scope": "station_level_pilot",
                    "data_scope": "live_operational_input",
                    "model_validation_scope": "January 2025 Anand Vihar pilot",
                    "missing_feature_reasons": all_reasons,
                },
            )

        # 6. Model Inference Execution
        try:
            inference_out = self.inference_engine.predict(
                station_id=CANONICAL_STATION_ID,
                prediction_timestamp=effective_ts,
                feature_row=feature_vector.features,
            )
        except InferenceError as e:
            logger.error(f"Inference error in live pipeline: {e}")
            return LiveForecastResult(
                status="INFERENCE_ERROR",
                canonical_station_id=CANONICAL_STATION_ID,
                prediction_timestamp=effective_ts,
                air_quality_source_timestamp=aq_res.get("latest_timestamp"),
                weather_source_timestamp=weather_res.get("latest_timestamp"),
                air_quality_age_minutes=aq_res.get("source_age_minutes"),
                weather_age_minutes=weather_res.get("source_age_minutes"),
                assembly_status="READY",
                diagnostic_flags={
                    "model_scope": "station_level_pilot",
                    "data_scope": "live_operational_input",
                    "model_validation_scope": "January 2025 Anand Vihar pilot",
                    "missing_feature_reasons": [f"Inference engine failure: {e.message}"],
                },
            )

        exec_duration_ms = round((time.time() - start_time) * 1000.0, 2)

        return LiveForecastResult(
            status="READY",
            canonical_station_id=CANONICAL_STATION_ID,
            prediction_timestamp=effective_ts,
            air_quality_source_timestamp=aq_res.get("latest_timestamp"),
            weather_source_timestamp=weather_res.get("latest_timestamp"),
            air_quality_age_minutes=aq_res.get("source_age_minutes"),
            weather_age_minutes=weather_res.get("source_age_minutes"),
            assembly_status="READY",
            forecast_results=inference_out.get("horizons"),
            diagnostic_flags={
                "model_scope": "station_level_pilot",
                "data_scope": "live_operational_input",
                "model_validation_scope": "January 2025 Anand Vihar pilot",
                "missing_feature_reasons": [],
                "forecast_generation_time_ms": exec_duration_ms,
            },
        )
