"""
VayuDrishti — Forecasting Target Builder

Constructs strictly future-looking target horizons (+1h, +3h, +6h) for primary (PM2.5)
and secondary (PM10) target pollutants.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from ml.src.forecasting.config import ForecastingConfig
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp


def compute_target_horizons(
    station_history: List[Dict[str, Any]],
    current_dt: Optional[Union[datetime, int]] = None,
    config: Optional[ForecastingConfig] = None,
    current_idx: Optional[int] = None,
) -> Dict[str, Optional[float]]:
    """
    Constructs target values for horizons +1h, +3h, +6h from station observation history.

    CRITICAL TARGET RULE:
    For prediction timestamp t, target +h MUST look for observation at exactly t + h hours (future).
    If target observation is not present or invalid, target field evaluates to None.
    """
    cfg = config or ForecastingConfig()
    idx_or_dt = current_dt if current_dt is not None else current_idx
    if idx_or_dt is None:
        idx_or_dt = 0

    if isinstance(idx_or_dt, int):
        curr_obs = station_history[idx_or_dt]
        curr_dt = curr_obs.get("parsed_timestamp") or parse_utc_timestamp(curr_obs["timestamp"])
    else:
        curr_dt = idx_or_dt

    if curr_dt.tzinfo is None:
        curr_dt = curr_dt.replace(tzinfo=timezone.utc)

    # Index future observations for the same station (> current_dt)
    future_time_map_pm25: Dict[int, float] = {}
    future_time_map_pm10: Dict[int, float] = {}

    for obs in station_history:
        obs_dt = obs.get("parsed_timestamp") or parse_utc_timestamp(obs["timestamp"])
        if obs_dt > curr_dt:
            diff_h = round((obs_dt - curr_dt).total_seconds() / 3600.0, 2)
            if abs(diff_h - round(diff_h)) < 0.05:
                int_h = int(round(diff_h))
                pol = str(obs.get("pollutant", "PM2.5")).upper().replace(".", "").replace(" ", "")
                val = float(obs["value"])
                if pol == "PM25" or pol == "PM2.5":
                    if int_h not in future_time_map_pm25:
                        future_time_map_pm25[int_h] = val
                elif pol == "PM10":
                    if int_h not in future_time_map_pm10:
                        future_time_map_pm10[int_h] = val

    targets: Dict[str, Optional[float]] = {}

    # Primary Target: PM2.5
    for h in cfg.target_horizons_hours:
        target_name = f"pm25_t_plus_{h}h"
        val = future_time_map_pm25.get(h)
        targets[target_name] = round(val, 2) if val is not None and val >= 0.0 else None

    # Secondary Target: PM10
    for h in cfg.target_horizons_hours:
        target_name = f"pm10_t_plus_{h}h"
        val = future_time_map_pm10.get(h)
        targets[target_name] = round(val, 2) if val is not None and val >= 0.0 else None

    return targets
