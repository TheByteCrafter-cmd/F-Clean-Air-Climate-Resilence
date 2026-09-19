"""
VayuDrishti — Real-Time-Safe Forecast Feature Assembler (Phase 1E-J2E.3.1)

Assembles leakage-safe, 27-feature vectors for short-term PM2.5 forecasting from historical
telemetry datasets or in-memory observation lists without external API calls or data fabrication.
"""

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ml.src.forecasting.config import ForecastingConfig
from ml.src.forecasting.feature_engineering import (
    align_weather_features,
    compute_cyclic_time_features,
    compute_lag_and_rolling_features,
)
from ml.src.forecasting.historical_ingestion import DELHI_PILOT_STATIONS
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

# Supported station normalization mapping
STATION_ALIAS_MAP = {
    "ANAND_VIHAR_8118": "ANAND_VIHAR_8118",
    "8118": "ANAND_VIHAR_8118",
    "LOC_8118": "ANAND_VIHAR_8118",
    "LOCATION_8118": "ANAND_VIHAR_8118",
}


@dataclass
class ForecastFeatureVector:
    """Encapsulates the assembled feature vector and its metadata provenance."""

    assembly_status: str  # READY, MISSING_HISTORY, WEATHER_STALE, INVALID_INPUT, UNSUPPORTED_STATION
    canonical_station_id: str
    requested_station_id: str
    prediction_timestamp: str
    features: Dict[str, float] = field(default_factory=dict)
    missing_feature_reasons: List[str] = field(default_factory=list)
    pm25_history_count: int = 0
    weather_observation_age_minutes: Optional[float] = None


class ForecastFeatureAssembler:
    """
    Assembles production feature vectors for the LightGBM forecasting model.
    Enforces dynamic manifest contract, canonical station coordinates, 60-minute weather
    staleness default, and strict zero-temporal-leakage rules.
    """

    def __init__(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        config: Optional[ForecastingConfig] = None,
        manifest_path: Optional[Union[str, Path]] = None,
        max_weather_staleness_minutes: Optional[float] = None,
    ):
        self.config = config or ForecastingConfig()
        self.data_dir = Path(data_dir) if data_dir else Path("data/processed/forecasting")
        self.max_weather_staleness_minutes = (
            max_weather_staleness_minutes
            if max_weather_staleness_minutes is not None
            else self.config.weather_tolerance_minutes
        )

        # Load canonical station metadata from project registry
        self.station_metadata = self._load_canonical_station_metadata()

        # Load manifest feature list
        self.manifest_path = (
            Path(manifest_path)
            if manifest_path
            else Path("ml/models/forecasting/model_manifest.json")
        )
        self.manifest_features = self._load_manifest_features()

    def _load_canonical_station_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Loads canonical station registry from DELHI_PILOT_STATIONS."""
        metadata = {}
        for st in DELHI_PILOT_STATIONS:
            metadata[st["station_id"]] = st
        return metadata

    def _load_manifest_features(self) -> List[str]:
        """Loads required feature list from model_manifest.json."""
        if not self.manifest_path.exists():
            logger.warning(f"Manifest not found at {self.manifest_path}. Using fallback list.")
            return []
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("feature_list", [])
        except Exception as e:
            logger.error(f"Failed to read model manifest: {e}")
            return []

    def normalize_station_id(self, station_id: str) -> Optional[str]:
        """Maps station alias to canonical station ID."""
        if not station_id:
            return None
        return STATION_ALIAS_MAP.get(station_id.strip())

    def load_air_quality_history(self) -> List[Dict[str, Any]]:
        """Loads historical air quality telemetry from historical_air_quality.csv."""
        csv_path = self.data_dir / "historical_air_quality.csv"
        records = []
        if not csv_path.exists():
            return records
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)
        except Exception as e:
            logger.error(f"Error loading historical air quality CSV: {e}")
        return records

    def load_weather_history(self) -> List[Dict[str, Any]]:
        """Loads historical weather telemetry from historical_weather.csv."""
        csv_path = self.data_dir / "historical_weather.csv"
        records = []
        if not csv_path.exists():
            return records
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)
        except Exception as e:
            logger.error(f"Error loading historical weather CSV: {e}")
        return records

    def assemble_features(
        self,
        station_id: str,
        prediction_timestamp: str,
        air_quality_records: Optional[List[Dict[str, Any]]] = None,
        weather_records: Optional[List[Dict[str, Any]]] = None,
    ) -> ForecastFeatureVector:
        """
        Assembles feature vector for station_id at prediction_timestamp t.

        Strict leakage safety:
        All air quality observations must have timestamp <= t.
        All weather observations must have timestamp <= t.
        """
        canonical_id = self.normalize_station_id(station_id)
        if not canonical_id or canonical_id not in self.station_metadata:
            return ForecastFeatureVector(
                assembly_status="UNSUPPORTED_STATION",
                canonical_station_id=canonical_id or "UNKNOWN",
                requested_station_id=station_id,
                prediction_timestamp=prediction_timestamp,
                missing_feature_reasons=[
                    f"Station '{station_id}' is unsupported. Canonical station scope: ANAND_VIHAR_8118."
                ],
            )

        # Parse prediction timestamp
        try:
            prediction_dt = parse_utc_timestamp(prediction_timestamp)
        except Exception as e:
            return ForecastFeatureVector(
                assembly_status="INVALID_INPUT",
                canonical_station_id=canonical_id,
                requested_station_id=station_id,
                prediction_timestamp=prediction_timestamp,
                missing_feature_reasons=[f"Invalid prediction_timestamp '{prediction_timestamp}': {e}"],
            )

        # Load or use provided telemetry
        aq_data = (
            air_quality_records
            if air_quality_records is not None
            else self.load_air_quality_history()
        )
        weather_data = (
            weather_records
            if weather_records is not None
            else self.load_weather_history()
        )

        reasons: List[str] = []

        # 1. Canonical Station Coordinates from Registry
        st_meta = self.station_metadata[canonical_id]
        canonical_lat = float(st_meta["latitude"])
        canonical_lon = float(st_meta["longitude"])

        # 2. Filter & Sort Air Quality Records (<= prediction_dt)
        station_history: List[Dict[str, Any]] = []
        for rec in aq_data:
            rec_st = rec.get("station_id") or rec.get("location_id")
            norm_rec_st = self.normalize_station_id(str(rec_st)) if rec_st else None
            if norm_rec_st != canonical_id:
                continue

            pollutant = rec.get("pollutant") or rec.get("parameter")
            if pollutant and pollutant.upper() not in ("PM2.5", "PM25"):
                continue

            raw_t = rec.get("timestamp") or rec.get("datetime")
            if not raw_t:
                continue

            try:
                rec_dt = parse_utc_timestamp(raw_t)
            except ValueError:
                continue

            # Strict temporal leakage protection (<= prediction_dt)
            if rec_dt <= prediction_dt:
                station_history.append(
                    {
                        "timestamp": raw_t,
                        "parsed_timestamp": rec_dt,
                        "value": float(rec["value"]),
                    }
                )

        station_history.sort(key=lambda x: x["parsed_timestamp"])

        # Calculate lag and rolling features
        pm25_features: Dict[str, Any] = {}
        history_count = len(station_history)
        if history_count == 0:
            reasons.append("No historical PM2.5 observations available at or before prediction timestamp")
        else:
            current_idx = len(station_history) - 1
            pm25_features = compute_lag_and_rolling_features(
                station_history=station_history,
                current_idx=current_idx,
                config=self.config,
            )

            # Audit individual lag & rolling feature availability
            for lag_h in self.config.lag_hours:
                feat_key = f"pm25_lag_{lag_h}h"
                if pm25_features.get(feat_key) is None:
                    reasons.append(f"{feat_key} unavailable")

            for w_h in self.config.rolling_windows_hours:
                mean_key = f"pm25_roll_mean_{w_h}h"
                med_key = f"pm25_roll_median_{w_h}h"
                if pm25_features.get(mean_key) is None:
                    reasons.append(f"{mean_key} insufficient valid observations")
                if pm25_features.get(med_key) is None:
                    reasons.append(f"{med_key} insufficient valid observations")

        # 3. Align Weather Features with Staleness Diagnostics
        aligned_config = ForecastingConfig(
            weather_tolerance_minutes=self.max_weather_staleness_minutes
        )
        weather_features = align_weather_features(
            prediction_dt=prediction_dt,
            station_lat=canonical_lat,
            station_lon=canonical_lon,
            weather_records=weather_data,
            config=aligned_config,
        )

        # Audit weather observation age
        best_weather_age_min: Optional[float] = None
        valid_weather_candidates = []
        for w in weather_data:
            raw_t = w.get("timestamp") or w.get("datetime")
            if not raw_t:
                continue
            try:
                w_dt = parse_utc_timestamp(raw_t)
            except ValueError:
                continue

            diff_min = (prediction_dt - w_dt).total_seconds() / 60.0
            if diff_min >= 0.0:  # <= prediction_dt
                valid_weather_candidates.append((diff_min, w))

        if valid_weather_candidates:
            best_weather_age_min = min(valid_weather_candidates, key=lambda x: x[0])[0]

        weather_stale = False
        if best_weather_age_min is None:
            weather_stale = True
            reasons.append("No past weather observations available at or before prediction timestamp")
        elif best_weather_age_min > self.max_weather_staleness_minutes:
            weather_stale = True
            reasons.append(
                f"weather observation age = {round(best_weather_age_min, 1)} minutes > {self.max_weather_staleness_minutes} minute threshold"
            )

        # Check if any weather feature value is None
        for w_feat, w_val in weather_features.items():
            if w_val is None and not any("weather" in r for r in reasons):
                reasons.append(f"{w_feat} unavailable")

        # 4. Cyclic Temporal Features
        cyclic_features = compute_cyclic_time_features(prediction_dt)

        # 5. Assemble Full Feature Vector
        raw_features: Dict[str, Any] = {
            "latitude": round(canonical_lat, 4),
            "longitude": round(canonical_lon, 4),
            **pm25_features,
            **weather_features,
            **cyclic_features,
        }

        # Order features according to model_manifest.json
        ordered_features: Dict[str, float] = {}
        missing_manifest_features = False

        target_feature_list = self.manifest_features or list(raw_features.keys())
        for feat in target_feature_list:
            val = raw_features.get(feat)
            if val is None:
                missing_manifest_features = True
                ordered_features[feat] = float("nan")
            else:
                ordered_features[feat] = float(val)

        # Determine Primary Assembly Status
        history_missing = any("lag" in r or "roll" in r or "PM2.5" in r for r in reasons)

        if history_missing:
            status = "MISSING_HISTORY"
        elif weather_stale:
            status = "WEATHER_STALE"
        elif missing_manifest_features:
            status = "MISSING_HISTORY"
        else:
            status = "READY"

        return ForecastFeatureVector(
            assembly_status=status,
            canonical_station_id=canonical_id,
            requested_station_id=station_id,
            prediction_timestamp=prediction_timestamp,
            features=ordered_features if status == "READY" else {},
            missing_feature_reasons=reasons,
            pm25_history_count=history_count,
            weather_observation_age_minutes=best_weather_age_min,
        )
