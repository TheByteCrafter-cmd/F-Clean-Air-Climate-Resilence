"""
VayuDrishti — Feature Engineering Engine

Generates deterministic, leakage-safe historical PM2.5 lag features, backward rolling
window statistics, cyclic temporal features, station metadata, and weather alignment.
"""

import math
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, List, Optional
from ml.src.forecasting.config import ForecastingConfig
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp


def compute_cyclic_time_features(dt: datetime) -> Dict[str, float]:
    """
    Computes deterministic cyclic sine/cosine encodings for hour, day of week, and month.
    Preserves temporal continuity without exploding categorical dummy variables.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    hour = dt.hour
    dow = dt.weekday()  # 0=Monday, 6=Sunday
    month = dt.month    # 1=January, 12=December

    hour_sin = round(math.sin(2.0 * math.pi * hour / 24.0), 5)
    hour_cos = round(math.cos(2.0 * math.pi * hour / 24.0), 5)

    dow_sin = round(math.sin(2.0 * math.pi * dow / 7.0), 5)
    dow_cos = round(math.cos(2.0 * math.pi * dow / 7.0), 5)

    month_sin = round(math.sin(2.0 * math.pi * (month - 1) / 12.0), 5)
    month_cos = round(math.cos(2.0 * math.pi * (month - 1) / 12.0), 5)

    return {
        "hour_sin": hour_sin,
        "hour_cos": hour_cos,
        "day_of_week_sin": dow_sin,
        "day_of_week_cos": dow_cos,
        "month_sin": month_sin,
        "month_cos": month_cos,
    }


def compute_lag_and_rolling_features(
    station_history: List[Dict[str, Any]],
    current_idx: int,
    config: Optional[ForecastingConfig] = None,
) -> Dict[str, Any]:
    """
    Computes historical PM2.5 lag features and backward-looking rolling statistics for station.

    CRITICAL LEAKAGE RULE:
    Only observations at index <= current_idx (timestamp <= t) are evaluated.
    Rolling windows are backward-looking ONLY ([t - W, t]). Never centered.
    """
    cfg = config or ForecastingConfig()
    curr_obs = station_history[current_idx]
    curr_dt = curr_obs.get("parsed_timestamp") or parse_utc_timestamp(curr_obs["timestamp"])

    # Subset history strictly <= current_dt
    past_obs: List[Dict[str, Any]] = []
    for obs in station_history[: current_idx + 1]:
        obs_dt = obs.get("parsed_timestamp") or parse_utc_timestamp(obs["timestamp"])
        if obs_dt <= curr_dt:
            past_obs.append(obs)

    # Map past observations by timestamp difference in hours
    time_map: Dict[int, float] = {}
    for obs in past_obs:
        obs_dt = obs.get("parsed_timestamp") or parse_utc_timestamp(obs["timestamp"])
        diff_h = round((curr_dt - obs_dt).total_seconds() / 3600.0, 2)
        # Store exact or integer hour diff
        if abs(diff_h - round(diff_h)) < 0.05:
            time_map[int(round(diff_h))] = float(obs["value"])

    features: Dict[str, Any] = {}

    # 1. Historical Lag Features
    for lag_h in cfg.lag_hours:
        feat_name = f"pm25_lag_{lag_h}h"
        val = time_map.get(lag_h)
        features[feat_name] = round(val, 2) if val is not None else None

    # 2. Historical Rolling Window Statistics
    for window_h in cfg.rolling_windows_hours:
        mean_name = f"pm25_roll_mean_{window_h}h"
        med_name = f"pm25_roll_median_{window_h}h"

        window_vals: List[float] = []
        for obs in past_obs:
            obs_dt = obs.get("parsed_timestamp") or parse_utc_timestamp(obs["timestamp"])
            diff_h = (curr_dt - obs_dt).total_seconds() / 3600.0
            if 0.0 <= diff_h <= float(window_h):
                try:
                    val = float(obs["value"])
                    if val >= 0.0:
                        window_vals.append(val)
                except (ValueError, TypeError):
                    pass

        if len(window_vals) >= cfg.min_rolling_obs:
            features[mean_name] = round(sum(window_vals) / len(window_vals), 2)
            features[med_name] = round(float(median(window_vals)), 2)
        else:
            features[mean_name] = None
            features[med_name] = None

    return features


def align_weather_features(
    prediction_dt: datetime,
    station_lat: float,
    station_lon: float,
    weather_records: List[Dict[str, Any]],
    config: Optional[ForecastingConfig] = None,
) -> Dict[str, Any]:
    """
    Aligns Open-Meteo weather features to prediction timestamp t.

    CRITICAL LEAKAGE RULE:
    Only weather observations at or before prediction_dt (<= t) within allowed
    tolerance window are considered. Future weather (> t) is strictly rejected.
    """
    cfg = config or ForecastingConfig()
    max_tol_min = cfg.weather_tolerance_minutes

    if not weather_records:
        return {
            "temperature_2m": None,
            "relative_humidity_2m": None,
            "wind_speed_10m": None,
            "wind_direction_10m": None,
            "wind_u": None,
            "wind_v": None,
            "surface_pressure": None,
            "boundary_layer_height": None,
        }

    # Filter candidate weather records <= prediction_dt within tolerance window
    valid_candidates: List[Tuple[float, Dict[str, Any]]] = []

    for w in weather_records:
        raw_t = w.get("timestamp") or w.get("datetime")
        if not raw_t:
            continue
        try:
            w_dt = parse_utc_timestamp(raw_t)
        except ValueError:
            continue

        # Strictly past or present (<= prediction_dt)
        time_diff_min = (prediction_dt - w_dt).total_seconds() / 60.0
        if 0.0 <= time_diff_min <= max_tol_min:
            valid_candidates.append((time_diff_min, w))

    if not valid_candidates:
        return {
            "temperature_2m": None,
            "relative_humidity_2m": None,
            "wind_speed_10m": None,
            "wind_direction_10m": None,
            "wind_u": None,
            "wind_v": None,
            "surface_pressure": None,
            "boundary_layer_height": None,
        }

    # Select closest candidate in past window
    best_candidate = min(valid_candidates, key=lambda x: x[0])[1]

    # Extract weather fields
    temp = best_candidate.get("temperature_2m") or best_candidate.get("temp")
    rh = best_candidate.get("relative_humidity_2m") or best_candidate.get("humidity")
    w_spd = best_candidate.get("wind_speed_10m") or best_candidate.get("wind_speed")
    w_dir = best_candidate.get("wind_direction_10m") or best_candidate.get("wind_direction")
    press = best_candidate.get("surface_pressure") or best_candidate.get("pressure")
    blh = best_candidate.get("boundary_layer_height") or best_candidate.get("pblh")

    # Compute wind Cartesian components (meteorological convention)
    u_comp = None
    v_comp = None
    if w_spd is not None and w_dir is not None:
        try:
            spd = float(w_spd)
            deg = float(w_dir)
            rad = math.radians(deg)
            u_comp = round(-spd * math.sin(rad), 2)
            v_comp = round(-spd * math.cos(rad), 2)
        except (ValueError, TypeError):
            pass

    return {
        "temperature_2m": round(float(temp), 2) if temp is not None else None,
        "relative_humidity_2m": round(float(rh), 2) if rh is not None else None,
        "wind_speed_10m": round(float(w_spd), 2) if w_spd is not None else None,
        "wind_direction_10m": round(float(w_dir), 2) if w_dir is not None else None,
        "wind_u": u_comp,
        "wind_v": v_comp,
        "surface_pressure": round(float(press), 2) if press is not None else None,
        "boundary_layer_height": round(float(blh), 2) if blh is not None else None,
    }
