"""
VayuDrishti — Forecasting Evaluation & Benchmark Engine (Phase 1E-J2B)

Provides evaluation metrics (MAE, RMSE, sMAPE), chronological dataset partitioning,
and baseline benchmark execution with data readiness gate enforcement.
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ml.src.forecasting.baseline import PersistenceForecaster
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp


def compute_mae(actuals: List[float], predictions: List[float]) -> float:
    """Computes Mean Absolute Error (MAE)."""
    if not actuals or len(actuals) != len(predictions):
        return 0.0
    errors = [abs(a - p) for a, p in zip(actuals, predictions)]
    return round(sum(errors) / len(errors), 4)


def compute_rmse(actuals: List[float], predictions: List[float]) -> float:
    """Computes Root Mean Squared Error (RMSE)."""
    if not actuals or len(actuals) != len(predictions):
        return 0.0
    squared_errors = [(a - p) ** 2 for a, p in zip(actuals, predictions)]
    mean_sq = sum(squared_errors) / len(squared_errors)
    return round(math.sqrt(mean_sq), 4)


def compute_smape(actuals: List[float], predictions: List[float]) -> float:
    """
    Computes Symmetric Mean Absolute Percentage Error (sMAPE).
    Formula: 100% * (1/n) * sum( |a - p| / ((|a| + |p|) / 2) )
    Handles zeros safely.
    """
    if not actuals or len(actuals) != len(predictions):
        return 0.0

    terms: List[float] = []
    for a, p in zip(actuals, predictions):
        denom = (abs(a) + abs(p)) / 2.0
        if denom == 0.0:
            terms.append(0.0)
        else:
            terms.append(abs(a - p) / denom)

    smape_val = (sum(terms) / len(terms)) * 100.0
    return round(smape_val, 4)


def split_chronologically(
    records: List[Dict[str, Any]],
    dev_pct: float = 0.70,
    val_pct: float = 0.15,
    test_pct: float = 0.15,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Splits records chronologically into development, validation, and holdout test periods.
    Guarantees no future timestamps leak into earlier evaluation splits.
    """
    if not records:
        return [], [], []

    # Sort records strictly by prediction_timestamp / timestamp
    sorted_recs = sorted(
        records,
        key=lambda x: x.get("parsed_timestamp")
        or parse_utc_timestamp(x.get("prediction_timestamp") or x.get("timestamp"))
    )

    n = len(sorted_recs)
    dev_end = int(n * dev_pct)
    val_end = dev_end + int(n * val_pct)

    dev_split = sorted_recs[:dev_end]
    val_split = sorted_recs[dev_end:val_end]
    test_split = sorted_recs[val_end:]

    return dev_split, val_split, test_split


class BaselineEvaluator:
    """
    Baseline Benchmark Evaluator.

    Reads forecast_data_readiness.json, enforces readiness gates, executes
    persistence forecasting over real or synthetic telemetry, computes metrics,
    and persists benchmark artifacts.
    """

    def __init__(self, data_root: Optional[Union[str, Path]] = None):
        self.data_root = Path(data_root) if data_root else Path("data")
        self.processed_dir = self.data_root / "processed" / "forecasting"
        self.baseline_dir = self.processed_dir / "baseline"
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        self.forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)

    def load_readiness_artifact(self) -> Dict[str, Any]:
        """Loads forecast_data_readiness.json from processed data directory."""
        readiness_path = self.processed_dir / "forecast_data_readiness.json"
        if not readiness_path.exists():
            return {
                "readiness_status": "NOT_READY",
                "training_ready": False,
                "readiness_reasons": ["forecast_data_readiness.json missing."],
                "metrics": {"total_stations": 0, "total_timestamps": 0},
            }
        with open(readiness_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_benchmark(
        self,
        custom_records: Optional[List[Dict[str, Any]]] = None,
        override_readiness_check: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes baseline benchmark evaluation.

        If readiness status is NOT_READY and override_readiness_check is False:
        - Stops benchmark execution
        - Persists baseline_readiness.json declaring BLOCKED status
        - Avoids fabricating fake production metrics.
        """
        readiness_info = self.load_readiness_artifact()
        readiness_status = readiness_info.get("readiness_status", "NOT_READY")

        readiness_artifact_path = self.baseline_dir / "baseline_readiness.json"
        manifest_artifact_path = self.baseline_dir / "baseline_evaluation_manifest.json"
        metrics_artifact_path = self.baseline_dir / "baseline_metrics.json"
        predictions_artifact_path = self.baseline_dir / "persistence_predictions.csv"

        # Check Readiness Gate
        if readiness_status == "NOT_READY" and not override_readiness_check:
            blocked_report = {
                "benchmark_status": "BASELINE BLOCKED BY DATA READINESS",
                "readiness_status": "NOT_READY",
                "readiness_reasons": readiness_info.get("readiness_reasons", []),
                "overall_status": "BLOCKED",
                "evaluated_stations": [],
                "evaluated_horizons": [],
                "missing_requirements": readiness_info.get("readiness_reasons", []),
                "remediation_guidelines": [
                    "Acquire historical CAAQMS telemetry spanning >= 48 hours for Delhi pilot stations.",
                    "Ensure >= 100 usable PM2.5 target rows exist for +1h, +3h, and +6h horizons.",
                ],
            }

            with open(readiness_artifact_path, "w", encoding="utf-8") as f:
                json.dump(blocked_report, f, indent=2)

            with open(manifest_artifact_path, "w", encoding="utf-8") as f:
                json.dump({
                    "manifest_version": "1.0-blocked",
                    "status": "BASELINE BLOCKED BY DATA READINESS",
                    "readiness_status": "NOT_READY",
                    "reason": "Insufficient historical data coverage.",
                }, f, indent=2)

            with open(metrics_artifact_path, "w", encoding="utf-8") as f:
                json.dump({
                    "overall_status": "BLOCKED",
                    "data_readiness_status": "NOT_READY",
                    "horizons": {},
                    "excluded_stations": [],
                    "excluded_horizons": ["+1h", "+3h", "+6h"],
                }, f, indent=2)

            # Write empty CSV header
            with open(predictions_artifact_path, "w", encoding="utf-8") as f:
                f.write("station_id,prediction_timestamp,horizon,anchor_timestamp,anchor_age_minutes,prediction_pm25,actual_pm25,absolute_error,squared_error\n")

            return blocked_report

        # If READY or PARTIALLY_READY (or override_readiness_check used for testing)
        records = custom_records or []
        predictions = self.forecaster.generate_predictions(records)

        # Compute horizon-level metrics
        horizon_metrics: Dict[str, Dict[str, Any]] = {}
        for h_name in ["+1h", "+3h", "+6h"]:
            h_preds = [p for p in predictions if p["horizon"] == h_name and p["prediction_pm25"] is not None and p["actual_pm25"] is not None]
            if h_preds:
                actuals = [p["actual_pm25"] for p in h_preds]
                preds = [p["prediction_pm25"] for p in h_preds]
                mae = compute_mae(actuals, preds)
                rmse = compute_rmse(actuals, preds)
                smape = compute_smape(actuals, preds)

                station_list = sorted(list({p["station_id"] for p in h_preds}))
                timestamps = [p["prediction_timestamp"] for p in h_preds]

                horizon_metrics[h_name] = {
                    "horizon": h_name,
                    "sample_count": len(h_preds),
                    "mae": mae,
                    "rmse": rmse,
                    "smape": smape,
                    "evaluated_stations": station_list,
                    "start_utc": min(timestamps) if timestamps else None,
                    "end_utc": max(timestamps) if timestamps else None,
                }
            else:
                horizon_metrics[h_name] = {
                    "horizon": h_name,
                    "sample_count": 0,
                    "mae": None,
                    "rmse": None,
                    "smape": None,
                    "evaluated_stations": [],
                    "start_utc": None,
                    "end_utc": None,
                }

        eval_report = {
            "benchmark_status": "COMPLETED",
            "readiness_status": readiness_status,
            "overall_status": "READY" if readiness_status == "READY" else "PARTIALLY_READY",
            "horizons": horizon_metrics,
            "total_predictions": len(predictions),
            "valid_evaluation_pairs": sum(h.get("sample_count", 0) for h in horizon_metrics.values()),
        }

        with open(metrics_artifact_path, "w", encoding="utf-8") as f:
            json.dump(eval_report, f, indent=2)

        with open(readiness_artifact_path, "w", encoding="utf-8") as f:
            json.dump({
                "benchmark_status": "COMPLETED",
                "readiness_status": readiness_status,
                "overall_status": "READY",
            }, f, indent=2)

        return eval_report
