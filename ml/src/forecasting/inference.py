"""
VayuDrishti — Forecast Inference Core Engine (Phase 1E-J2E.1)

Provides deterministic single-row forecast inference for +1h, +3h, and +6h PM2.5 horizons,
enforcing canonical station scope (ANAND_VIHAR_8118), dynamic feature schema ordering,
and unclipped Split Conformal prediction interval attachment.
"""

import math
import numpy as np
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ml.src.forecasting.model_loader import (
    CANONICAL_STATION_ID,
    SUPPORTED_STATION_ALIASES,
    ForecastModelLoader,
    ModelLoaderError,
)
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)


class InferenceError(Exception):
    """Base exception for forecast inference failures."""
    def __init__(self, error_code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.details = details or {}


class ForecastInferenceEngine:
    """
    Forecasting Inference Engine.

    Loads model boosters, manifest, and conformal radii. Validates station scope,
    prediction timestamp, and input feature row completeness before generating
    predictions and attaching unclipped conformal intervals.
    """

    def __init__(
        self,
        loader: Optional[ForecastModelLoader] = None,
        models_dir: Optional[Union[str, Path]] = None,
        data_root: Optional[Union[str, Path]] = None,
    ):
        self.loader = loader or ForecastModelLoader(models_dir=models_dir, data_root=data_root)
        self._initialize_core()

    def _initialize_core(self):
        """Loads and validates manifests, models, and conformal radii."""
        self.manifest = self.loader.load_manifest()
        self.feature_list = self.manifest["feature_list"]
        self.feature_count = self.manifest["feature_count"]
        self.boosters = self.loader.load_models()
        self.conformal_radii = self.loader.load_conformal_metrics()

    def validate_station_scope(self, station_id: str) -> str:
        """
        Validates station scope against canonical station ID and supported aliases.

        Returns canonical station ID if valid; raises InferenceError with UNSUPPORTED_STATION_SCOPE if invalid.
        """
        if not station_id or not isinstance(station_id, str):
            raise InferenceError(
                error_code="UNSUPPORTED_STATION_SCOPE",
                message="Station ID must be a non-empty string.",
                details={"provided_station_id": station_id},
            )

        norm_id = station_id.strip().upper()
        if norm_id not in SUPPORTED_STATION_ALIASES:
            raise InferenceError(
                error_code="UNSUPPORTED_STATION_SCOPE",
                message=(
                    f"Station '{station_id}' is not supported. Current inference scope is strictly "
                    f"limited to Anand Vihar 8118 pilot station ({CANONICAL_STATION_ID})."
                ),
                details={
                    "provided_station_id": station_id,
                    "canonical_station_id": CANONICAL_STATION_ID,
                    "supported_aliases": list(SUPPORTED_STATION_ALIASES),
                },
            )

        return CANONICAL_STATION_ID

    def validate_timestamp(self, timestamp: str) -> str:
        """Validates prediction timestamp syntax and timezone normalization."""
        if not timestamp or not isinstance(timestamp, str):
            raise InferenceError(
                error_code="INVALID_TIMESTAMP",
                message="Prediction timestamp must be a non-empty string.",
                details={"provided_timestamp": timestamp},
            )

        try:
            dt = parse_utc_timestamp(timestamp)
            return dt.isoformat().replace("+00:00", "Z")
        except Exception as e:
            raise InferenceError(
                error_code="INVALID_TIMESTAMP",
                message=f"Invalid or malformed UTC timestamp '{timestamp}': {str(e)}",
                details={"provided_timestamp": timestamp},
            )

    def prepare_feature_vector(self, feature_row: Dict[str, Any]) -> np.ndarray:
        """
        Validates presence of all required manifest features and constructs
        a 2D numpy array ordered EXACTLY according to manifest feature_list.
        """
        if not isinstance(feature_row, dict):
            raise InferenceError(
                error_code="INVALID_FEATURE_FORMAT",
                message="Input feature_row must be a dictionary.",
            )

        missing_features = [col for col in self.feature_list if col not in feature_row]
        if missing_features:
            raise InferenceError(
                error_code="MISSING_FEATURES",
                message=f"Input feature row missing {len(missing_features)} required features.",
                details={
                    "missing_features": missing_features,
                    "required_count": self.feature_count,
                    "provided_count": len(feature_row),
                },
            )

        X = np.zeros((1, self.feature_count), dtype=np.float32)

        invalid_value_errors = []
        for i, col in enumerate(self.feature_list):
            val = feature_row[col]
            if val is None or val == "" or val == "NaN":
                invalid_value_errors.append((col, val, "Missing/null value forbidden for inference row"))
                continue
            try:
                v_float = float(val)
                if math.isnan(v_float) or math.isinf(v_float):
                    invalid_value_errors.append((col, val, "NaN or Infinite float forbidden"))
                else:
                    X[0, i] = v_float
            except (ValueError, TypeError):
                invalid_value_errors.append((col, val, "Non-numeric value"))

        if invalid_value_errors:
            raise InferenceError(
                error_code="INVALID_FEATURE_VALUES",
                message=f"Input feature row contains {len(invalid_value_errors)} invalid values.",
                details={"invalid_features": invalid_value_errors},
            )

        return X

    def predict(
        self,
        station_id: str,
        prediction_timestamp: str,
        feature_row: Dict[str, Any],
        horizons: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes deterministic single-row forecast inference for requested horizons.

        Returns structured forecast result with unclipped 80% and 90% prediction intervals.
        """
        # 1. Validate Scope & Timestamp
        canonical_id = self.validate_station_scope(station_id)
        norm_timestamp = self.validate_timestamp(prediction_timestamp)

        # 2. Validate & Order Feature Vector
        X = self.prepare_feature_vector(feature_row)

        target_horizons = horizons or ["+1h", "+3h", "+6h"]
        horizon_results: Dict[str, Any] = {}

        for h_name in target_horizons:
            if h_name not in self.boosters:
                raise InferenceError(
                    error_code="UNSUPPORTED_HORIZON",
                    message=f"Requested horizon '{h_name}' is not supported by loaded models.",
                )

            booster = self.boosters[h_name]
            raw_pred_arr = booster.predict(X)

            # Sanity Check Prediction Numeric & Finite
            if len(raw_pred_arr) == 0 or not np.isfinite(raw_pred_arr[0]):
                raise InferenceError(
                    error_code="PREDICTION_SANITY_FAILURE",
                    message=f"Non-numeric or non-finite prediction output for horizon {h_name}.",
                )

            raw_pred = round(float(raw_pred_arr[0]), 4)
            is_negative = bool(raw_pred < 0.0)

            # Conformal Radii Attachment
            radii = self.conformal_radii.get(h_name, {"radius_80": 0.0, "radius_90": 0.0})
            q_80 = radii["radius_80"]
            q_90 = radii["radius_90"]

            lower_80 = round(raw_pred - q_80, 4)
            upper_80 = round(raw_pred + q_80, 4)

            lower_90 = round(raw_pred - q_90, 4)
            upper_90 = round(raw_pred + q_90, 4)

            # Sanity check bounds
            if lower_80 > upper_80 or lower_90 > upper_90:
                raise InferenceError(
                    error_code="INTERVAL_SANITY_FAILURE",
                    message=f"Interval lower bound exceeds upper bound for horizon {h_name}.",
                )

            h_meta = self.manifest["models"][h_name]

            horizon_results[h_name] = {
                "horizon": h_name,
                "target_column": h_meta["target_column"],
                "predicted_pm25": raw_pred,
                "prediction_negative": is_negative,
                "prediction_intervals": {
                    "80_pct": {
                        "confidence_level": "80%",
                        "conformal_radius": q_80,
                        "lower_bound": lower_80,
                        "upper_bound": upper_80,
                        "interval_width": round(2.0 * q_80, 4),
                    },
                    "90_pct": {
                        "confidence_level": "90%",
                        "conformal_radius": q_90,
                        "lower_bound": lower_90,
                        "upper_bound": upper_90,
                        "interval_width": round(2.0 * q_90, 4),
                    },
                },
            }

        return {
            "status": "SUCCESS",
            "scope": self.manifest["scope"],
            "canonical_station_id": canonical_id,
            "requested_station_id": station_id,
            "prediction_timestamp": norm_timestamp,
            "feature_count": self.feature_count,
            "horizons": horizon_results,
        }
