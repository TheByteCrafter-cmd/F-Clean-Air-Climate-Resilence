"""
VayuDrishti — Persistence Forecasting Baseline Engine (Phase 1E-J2B)

Provides deterministic persistence forecaster implementation for PM2.5 air quality
time-series, enforcing configurable maximum anchor age policies, station isolation,
and zero temporal leakage.
"""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from ml.src.forecasting.timestamp_utils import parse_utc_timestamp


class PersistenceForecaster:
    """
    Deterministic Persistence Forecaster.

    For prediction timestamp t and target horizon h (+1h, +3h, +6h):
    forecast(t+h) = latest valid PM2.5 observation at or before t (t_anchor <= t)

    If (t - t_anchor) > max_anchor_age_hours, prediction is marked unavailable (None).
    """

    def __init__(self, max_anchor_age_hours: float = 3.0):
        """
        Initializes PersistenceForecaster with configurable maximum anchor age threshold.

        :param max_anchor_age_hours: Maximum permissible age (in hours) of an observation
                                     to be used as a persistence anchor. Default is 3.0 hours.
        """
        if max_anchor_age_hours <= 0:
            raise ValueError("max_anchor_age_hours must be strictly positive.")
        self.max_anchor_age_hours = max_anchor_age_hours
        self.max_anchor_age_minutes = max_anchor_age_hours * 60.0

    def find_latest_anchor(
        self,
        station_history: List[Dict[str, Any]],
        prediction_timestamp_utc: datetime,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[float]]:
        """
        Finds the latest valid observation for a station at or before prediction_timestamp_utc.

        :param station_history: List of observation dicts for a SINGLE station, sorted by timestamp.
        :param prediction_timestamp_utc: UTC datetime at which prediction is being made (time t).
        :return: Tuple of (latest_observation_dict, anchor_age_minutes).
                 Returns (None, None) if no valid observation <= t exists within max_anchor_age.
        """
        best_obs: Optional[Dict[str, Any]] = None
        best_age_minutes: Optional[float] = None

        for obs in station_history:
            raw_ts = obs.get("parsed_timestamp")
            if not raw_ts:
                ts_str = obs.get("timestamp") or obs.get("prediction_timestamp")
                if not ts_str:
                    continue
                dt = parse_utc_timestamp(ts_str)
            else:
                dt = raw_ts

            # Strict temporal condition: observation MUST be <= prediction_timestamp_utc
            if dt > prediction_timestamp_utc:
                continue

            val = obs.get("pm25_t0") if "pm25_t0" in obs else obs.get("value")
            if val is None or math.isnan(val) or val < 0:
                continue

            age_seconds = (prediction_timestamp_utc - dt).total_seconds()
            if age_seconds < 0:
                continue  # Extra safety against future observations

            age_minutes = age_seconds / 60.0

            # Select the most recent valid observation (smallest non-negative age)
            if best_age_minutes is None or age_minutes < best_age_minutes:
                best_age_minutes = age_minutes
                best_obs = obs

        # Enforce maximum anchor age policy
        if best_age_minutes is not None and best_age_minutes <= self.max_anchor_age_minutes:
            return best_obs, round(best_age_minutes, 2)

        return None, None

    def generate_predictions(
        self,
        records: List[Dict[str, Any]],
        horizons_hours: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates persistence predictions for a dataset of station telemetry rows.

        :param records: List of record dictionaries containing station_id, timestamp/prediction_timestamp,
                        pm25_t0 / value, and target horizon values (e.g., pm25_t_plus_1h, etc.).
        :param horizons_hours: Target horizon list (default [1, 3, 6]).
        :return: List of prediction result dictionaries matching the persistence prediction schema.
        """
        target_horizons = horizons_hours or [1, 3, 6]

        # Group and sort history by station_id
        station_histories: Dict[str, List[Dict[str, Any]]] = {}
        for r in records:
            st_id = r.get("station_id")
            if not st_id:
                continue
            if st_id not in station_histories:
                station_histories[st_id] = []
            station_histories[st_id].append(r)

        # Ensure station histories are chronologically ordered
        for st_id, hist in station_histories.items():
            hist.sort(
                key=lambda x: x.get("parsed_timestamp")
                or parse_utc_timestamp(x.get("timestamp") or x.get("prediction_timestamp"))
            )

        predictions: List[Dict[str, Any]] = []

        for st_id, hist in station_histories.items():
            for rec in hist:
                raw_pred_ts = rec.get("prediction_timestamp") or rec.get("timestamp")
                if not raw_pred_ts:
                    continue
                pred_dt = rec.get("parsed_timestamp") or parse_utc_timestamp(raw_pred_ts)
                pred_iso = pred_dt.isoformat().replace("+00:00", "Z")

                # Find persistence anchor for time pred_dt
                anchor_obs, age_minutes = self.find_latest_anchor(hist, pred_dt)

                if anchor_obs:
                    raw_anchor_ts = anchor_obs.get("timestamp") or anchor_obs.get("prediction_timestamp")
                    anchor_dt = anchor_obs.get("parsed_timestamp") or parse_utc_timestamp(raw_anchor_ts)
                    anchor_iso = anchor_dt.isoformat().replace("+00:00", "Z")
                    pred_pm25 = float(anchor_obs.get("pm25_t0") if "pm25_t0" in anchor_obs else anchor_obs.get("value"))
                else:
                    anchor_iso = None
                    pred_pm25 = None

                for h in target_horizons:
                    target_key = f"pm25_t_plus_{h}h"
                    actual_pm25 = rec.get(target_key)
                    if actual_pm25 is not None:
                        actual_pm25 = float(actual_pm25)

                    abs_err = None
                    sq_err = None

                    if pred_pm25 is not None and actual_pm25 is not None:
                        abs_err = round(abs(pred_pm25 - actual_pm25), 4)
                        sq_err = round((pred_pm25 - actual_pm25) ** 2, 4)

                    predictions.append({
                        "station_id": st_id,
                        "prediction_timestamp": pred_iso,
                        "horizon": f"+{h}h",
                        "horizon_hours": h,
                        "anchor_timestamp": anchor_iso,
                        "anchor_age_minutes": age_minutes,
                        "prediction_pm25": pred_pm25,
                        "actual_pm25": actual_pm25,
                        "absolute_error": abs_err,
                        "squared_error": sq_err,
                    })

        return predictions
