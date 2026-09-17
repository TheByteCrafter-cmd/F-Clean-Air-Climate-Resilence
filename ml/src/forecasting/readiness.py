"""
VayuDrishti — Forecasting Dataset Readiness Assessor

Evaluates real historical data artifacts against formal engineering readiness criteria
to determine if sufficient temporal continuity exists for supervised model training.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from ml.src.forecasting.config import ForecastingConfig
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp, detect_irregular_intervals


class ForecastingReadinessAssessor:
    """Evaluates whether dataset artifacts meet minimum criteria for model training."""

    def __init__(self, config: Optional[ForecastingConfig] = None):
        self.config = config or ForecastingConfig()

    def assess_readiness(
        self,
        records: List[Dict[str, Any]],
        dataset_rows: List[Dict[str, Any]],
        weather_records: Optional[List[Dict[str, Any]]] = None,
        leakage_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Assesses data readiness against deterministic thresholds:
        - Stations count >= min_stations_readiness (3)
        - Unique timestamps >= min_timestamps_readiness (48 hours)
        - Usable target rows (+1h, +3h, +6h) >= min_usable_rows_readiness (100)
        - Zero leakage test failures
        """
        cfg = self.config

        if not records or not dataset_rows:
            return {
                "readiness_status": "NOT_READY",
                "training_ready": False,
                "readiness_reasons": ["Dataset is empty. No historical observation records available."],
                "metrics": {
                    "total_stations": 0,
                    "total_timestamps": 0,
                    "usable_rows_1h": 0,
                    "usable_rows_3h": 0,
                    "usable_rows_6h": 0,
                },
            }

        # 1. Station metrics
        station_ids = sorted(list({r["station_id"] for r in dataset_rows if "station_id" in r}))
        total_stations = len(station_ids)

        # 2. Timestamp metrics
        timestamps = sorted(list({r["prediction_timestamp"] for r in dataset_rows if "prediction_timestamp" in r}))
        total_timestamps = len(timestamps)

        min_ts = timestamps[0] if timestamps else None
        max_ts = timestamps[-1] if timestamps else None

        time_range_hours = 0.0
        if min_ts and max_ts:
            dt_min = parse_utc_timestamp(min_ts)
            dt_max = parse_utc_timestamp(max_ts)
            time_range_hours = round((dt_max - dt_min).total_seconds() / 3600.0, 2)

        # 3. Usable target rows
        usable_1h = sum(1 for r in dataset_rows if r.get("pm25_t_plus_1h") is not None)
        usable_3h = sum(1 for r in dataset_rows if r.get("pm25_t_plus_3h") is not None)
        usable_6h = sum(1 for r in dataset_rows if r.get("pm25_t_plus_6h") is not None)

        # 4. Missingness percentages
        missing_pm25_count = sum(1 for r in dataset_rows if r.get("pm25_t0") is None)
        pct_missing_pm25 = round((missing_pm25_count / len(dataset_rows)) * 100.0, 2)

        missing_wx_count = sum(1 for r in dataset_rows if r.get("temperature_2m") is None)
        pct_missing_wx = round((missing_wx_count / len(dataset_rows)) * 100.0, 2)

        # 5. Temporal gap analysis
        gap_info = detect_irregular_intervals(records)

        # 6. Readiness decision logic
        reasons: List[str] = []

        if total_stations < cfg.min_stations_readiness:
            reasons.append(
                f"Insufficient station count ({total_stations} < {cfg.min_stations_readiness} required)."
            )

        if total_timestamps < cfg.min_timestamps_readiness:
            reasons.append(
                f"Insufficient historical timestamps ({total_timestamps} < {cfg.min_timestamps_readiness} required). "
                f"Historical time range is only {time_range_hours} hours."
            )

        if usable_1h < cfg.min_usable_rows_readiness:
            reasons.append(
                f"Insufficient usable target rows for +1h horizon ({usable_1h} < {cfg.min_usable_rows_readiness} required)."
            )

        if usable_3h < cfg.min_usable_rows_readiness:
            reasons.append(
                f"Insufficient usable target rows for +3h horizon ({usable_3h} < {cfg.min_usable_rows_readiness} required)."
            )

        if usable_6h < cfg.min_usable_rows_readiness:
            reasons.append(
                f"Insufficient usable target rows for +6h horizon ({usable_6h} < {cfg.min_usable_rows_readiness} required)."
            )

        if leakage_results and not leakage_results.get("leakage_passed", True):
            reasons.append("Temporal leakage verification failed.")

        if not reasons:
            readiness_status = "READY"
            training_ready = True
        elif total_timestamps >= 12 and usable_1h >= 20:
            readiness_status = "PARTIALLY_READY"
            training_ready = False
        else:
            readiness_status = "NOT_READY"
            training_ready = False

        return {
            "readiness_status": readiness_status,
            "training_ready": training_ready,
            "readiness_reasons": reasons,
            "metrics": {
                "total_stations": total_stations,
                "total_timestamps": total_timestamps,
                "min_observation_timestamp": min_ts,
                "max_observation_timestamp": max_ts,
                "time_range_hours": time_range_hours,
                "median_gap_hours": gap_info.get("median_gap_hours"),
                "usable_rows_plus_1h": usable_1h,
                "usable_rows_plus_3h": usable_3h,
                "usable_rows_plus_6h": usable_6h,
                "pct_missing_pm25": pct_missing_pm25,
                "pct_missing_weather": pct_missing_wx,
                "leakage_test_passed": leakage_results.get("leakage_passed") if leakage_results else None,
            },
            "thresholds": {
                "min_stations_required": cfg.min_stations_readiness,
                "min_timestamps_required": cfg.min_timestamps_readiness,
                "min_usable_rows_required": cfg.min_usable_rows_readiness,
            }
        }
