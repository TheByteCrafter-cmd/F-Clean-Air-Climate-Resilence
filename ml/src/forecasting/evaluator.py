"""
VayuDrishti — Forecast Residual Evaluation & Uncertainty Calibration Engine (Phase 1E-J2D)

Provides residual diagnostics, error distribution analysis, baseline reconciliation,
and empirical uncertainty calibration via Split Conformal Prediction for trained LightGBM
air quality models (+1h, +3h, +6h) on the Anand Vihar 8118 pilot station.
"""

import csv
import json
import logging
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import lightgbm as lgb
import numpy as np

from ml.src.forecasting.baseline import PersistenceForecaster
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp
from ml.src.forecasting.trainer import LightGBMPilotTrainer

logger = logging.getLogger(__name__)

CONFORMAL_GUARANTEE_STATEMENT = (
    "Split conformal provides a finite-sample marginal coverage guarantee under "
    "its exchangeability assumptions. Because this pilot consists of temporally dependent "
    "air-quality observations, empirical holdout coverage is reported and should not "
    "be interpreted as an unconditional coverage guarantee."
)


def compute_conformal_quantile(
    validation_abs_residuals: np.ndarray, alpha: float
) -> float:
    """
    Computes finite-sample-aware conformal order-statistic quantile radius 'q'.

    Formula:
    n = len(validation_abs_residuals)
    k = ceil((n + 1) * (1 - alpha))
    k = min(k, n)
    q = sorted(validation_abs_residuals)[k - 1] (1-indexed k)

    The exact mathematical indexing convention is:
    k = min(ceil((N_val + 1) * (1 - alpha)), N_val) order statistic of sorted absolute validation residuals.
    """
    n = len(validation_abs_residuals)
    if n == 0:
        return 0.0

    sorted_res = np.sort(np.abs(validation_abs_residuals))
    k = int(math.ceil((n + 1) * (1.0 - alpha)))
    k = max(1, min(k, n))
    radius = float(sorted_res[k - 1])
    return round(radius, 4)


def compute_percentiles(values: np.ndarray) -> Dict[str, float]:
    """Computes distribution summary statistics and key percentiles."""
    if len(values) == 0:
        return {
            "mean": 0.0,
            "std": 0.0,
            "min": 0.0,
            "p5": 0.0,
            "p25": 0.0,
            "median": 0.0,
            "p75": 0.0,
            "p95": 0.0,
            "max": 0.0,
        }
    return {
        "mean": round(float(np.mean(values)), 4),
        "std": round(float(np.std(values)), 4),
        "min": round(float(np.min(values)), 4),
        "p5": round(float(np.percentile(values, 5)), 4),
        "p25": round(float(np.percentile(values, 25)), 4),
        "median": round(float(np.median(values)), 4),
        "p75": round(float(np.percentile(values, 75)), 4),
        "p95": round(float(np.percentile(values, 95)), 4),
        "max": round(float(np.max(values)), 4),
    }


class ForecastResidualEvaluator:
    """
    Manages residual analysis, Split Conformal prediction interval calibration,
    baseline reconciliation, and artifact generation for trained forecasting models.
    """

    def __init__(
        self,
        data_root: Optional[Union[str, Path]] = None,
        models_dir: Optional[Union[str, Path]] = None,
        eval_dir: Optional[Union[str, Path]] = None,
    ):
        self.data_root = Path(data_root) if data_root else Path(os.getcwd()) / "data"
        self.models_dir = Path(models_dir) if models_dir else Path(os.getcwd()) / "ml" / "models" / "forecasting"
        self.eval_dir = Path(eval_dir) if eval_dir else self.data_root / "processed" / "forecasting" / "model_evaluation"
        self.residual_dir = self.eval_dir / "residual_analysis"

        self.residual_dir.mkdir(parents=True, exist_ok=True)
        self.trainer = LightGBMPilotTrainer(data_root=self.data_root)

    def evaluate_residuals_and_uncertainty(
        self, csv_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Executes full residual evaluation and Split Conformal calibration pipeline.
        """
        dataset_csv = csv_path or (self.data_root / "processed" / "forecasting" / "forecast_dataset.csv")
        rows, feature_cols = self.trainer.load_dataset(dataset_csv)

        horizons = [("+1h", "pm25_t_plus_1h"), ("+3h", "pm25_t_plus_3h"), ("+6h", "pm25_t_plus_6h")]

        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        residual_records: List[Dict[str, Any]] = []
        residual_summary: Dict[str, Any] = {}
        residual_diagnostics: Dict[str, Any] = {}
        uncertainty_metrics: Dict[str, Any] = {}
        horizon_widths: Dict[str, Dict[str, float]] = {}

        for h_name, target_col in horizons:
            model_filename = f"lightgbm_pm25_{h_name.replace('+', '')}.txt"
            model_path = self.models_dir / model_filename
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found at {model_path}")

            gbm = lgb.Booster(model_file=str(model_path))

            split_data = self.trainer.prepare_split_data(rows, feature_cols, target_col)
            X_val, y_val, val_rows = split_data["X_val"], split_data["y_val"], split_data["val_rows"]
            X_test, y_test, test_rows = split_data["X_test"], split_data["y_test"], split_data["test_rows"]

            pred_val = gbm.predict(X_val, predict_disable_shape_check=True)
            pred_test = gbm.predict(X_test, predict_disable_shape_check=True)

            # Residuals
            val_residuals = y_val - pred_val  # positive = under-prediction
            val_abs_res = np.abs(val_residuals)

            test_residuals = y_test - pred_test
            test_abs_res = np.abs(test_residuals)

            # Conformal Quantiles derived ONLY from Validation Abs Residuals
            q_80 = compute_conformal_quantile(val_abs_res, alpha=0.20)
            q_90 = compute_conformal_quantile(val_abs_res, alpha=0.10)

            width_80 = round(2.0 * q_80, 4)
            width_90 = round(2.0 * q_90, 4)

            horizon_widths[h_name] = {
                "radius_80": q_80,
                "width_80": width_80,
                "radius_90": q_90,
                "width_90": width_90,
            }

            # Build Validation Records
            for r, act, prd, res, abs_err in zip(val_rows, y_val, pred_val, val_residuals, val_abs_res):
                lower_80 = round(float(prd - q_80), 4)
                upper_80 = round(float(prd + q_80), 4)
                hit_80 = bool(lower_80 <= act <= upper_80)

                lower_90 = round(float(prd - q_90), 4)
                upper_90 = round(float(prd + q_90), 4)
                hit_90 = bool(lower_90 <= act <= upper_90)

                residual_records.append({
                    "station_id": r["station_id"],
                    "prediction_timestamp": r["prediction_timestamp"],
                    "horizon": h_name,
                    "split": "validation",
                    "actual_pm25": round(float(act), 4),
                    "predicted_pm25": round(float(prd), 4),
                    "residual": round(float(res), 4),
                    "absolute_error": round(float(abs_err), 4),
                    "squared_error": round(float(abs_err ** 2), 4),
                    "conformal_lower_80": lower_80,
                    "conformal_upper_80": upper_80,
                    "hit_80": hit_80,
                    "conformal_lower_90": lower_90,
                    "conformal_upper_90": upper_90,
                    "hit_90": hit_90,
                })

            # Build Test Records
            test_hits_80 = 0
            test_hits_90 = 0
            for r, act, prd, res, abs_err in zip(test_rows, y_test, pred_test, test_residuals, test_abs_res):
                lower_80 = round(float(prd - q_80), 4)
                upper_80 = round(float(prd + q_80), 4)
                hit_80 = bool(lower_80 <= act <= upper_80)
                if hit_80:
                    test_hits_80 += 1

                lower_90 = round(float(prd - q_90), 4)
                upper_90 = round(float(prd + q_90), 4)
                hit_90 = bool(lower_90 <= act <= upper_90)
                if hit_90:
                    test_hits_90 += 1

                residual_records.append({
                    "station_id": r["station_id"],
                    "prediction_timestamp": r["prediction_timestamp"],
                    "horizon": h_name,
                    "split": "test",
                    "actual_pm25": round(float(act), 4),
                    "predicted_pm25": round(float(prd), 4),
                    "residual": round(float(res), 4),
                    "absolute_error": round(float(abs_err), 4),
                    "squared_error": round(float(abs_err ** 2), 4),
                    "conformal_lower_80": lower_80,
                    "conformal_upper_80": upper_80,
                    "hit_80": hit_80,
                    "conformal_lower_90": lower_90,
                    "conformal_upper_90": upper_90,
                    "hit_90": hit_90,
                })

            # Coverage & Error on Test Set
            n_test = len(y_test)
            emp_cov_80 = round((test_hits_80 / n_test) * 100.0, 2) if n_test > 0 else 0.0
            cov_err_80 = round(emp_cov_80 - 80.0, 2)

            emp_cov_90 = round((test_hits_90 / n_test) * 100.0, 2) if n_test > 0 else 0.0
            cov_err_90 = round(emp_cov_90 - 90.0, 2)

            uncertainty_metrics[h_name] = {
                "conformal_radius_80": q_80,
                "average_interval_width_80": width_80,
                "median_interval_width_80": width_80,
                "test_empirical_coverage_80_pct": emp_cov_80,
                "coverage_error_80_pct": cov_err_80,
                "conformal_radius_90": q_90,
                "average_interval_width_90": width_90,
                "median_interval_width_90": width_90,
                "test_empirical_coverage_90_pct": emp_cov_90,
                "coverage_error_90_pct": cov_err_90,
                "validation_sample_count": len(y_val),
                "test_sample_count": n_test,
            }

            # Summary Metrics for Val & Test
            val_mae = round(float(np.mean(val_abs_res)), 4)
            val_rmse = round(float(np.sqrt(np.mean(val_residuals ** 2))), 4)
            test_mae = round(float(np.mean(test_abs_res)), 4)
            test_rmse = round(float(np.sqrt(np.mean(test_residuals ** 2))), 4)

            residual_summary[h_name] = {
                "validation": {
                    "sample_count": len(y_val),
                    "mae": val_mae,
                    "rmse": val_rmse,
                    "residual_percentiles": compute_percentiles(val_residuals),
                    "absolute_error_percentiles": compute_percentiles(val_abs_res),
                },
                "test": {
                    "sample_count": len(y_test),
                    "mae": test_mae,
                    "rmse": test_rmse,
                    "residual_percentiles": compute_percentiles(test_residuals),
                    "absolute_error_percentiles": compute_percentiles(test_abs_res),
                },
            }

            # Temporal Breakdown (Test Set)
            hours_breakdown: Dict[int, Dict[str, Any]] = {}
            for h in range(24):
                mask = [parse_utc_timestamp(r["prediction_timestamp"]).hour == h for r in test_rows]
                if any(mask):
                    sub_act = y_test[mask]
                    sub_prd = pred_test[mask]
                    sub_res = test_residuals[mask]
                    hours_breakdown[h] = {
                        "count": int(np.sum(mask)),
                        "mean_actual": round(float(np.mean(sub_act)), 2),
                        "mean_predicted": round(float(np.mean(sub_prd)), 2),
                        "mean_residual": round(float(np.mean(sub_res)), 4),
                        "mae": round(float(np.mean(np.abs(sub_res))), 4),
                        "rmse": round(float(np.sqrt(np.mean(sub_res ** 2))), 4),
                    }

            day_breakdown: Dict[int, Dict[str, Any]] = {}
            for d in range(7):
                mask = [parse_utc_timestamp(r["prediction_timestamp"]).weekday() == d for r in test_rows]
                if any(mask):
                    sub_act = y_test[mask]
                    sub_prd = pred_test[mask]
                    sub_res = test_residuals[mask]
                    day_breakdown[d] = {
                        "count": int(np.sum(mask)),
                        "mean_actual": round(float(np.mean(sub_act)), 2),
                        "mean_predicted": round(float(np.mean(sub_prd)), 2),
                        "mean_residual": round(float(np.mean(sub_res)), 4),
                        "mae": round(float(np.mean(np.abs(sub_res))), 4),
                        "rmse": round(float(np.sqrt(np.mean(sub_res ** 2))), 4),
                    }

            # High-Pollution Analysis (Test set actual_pm25 > 200)
            high_poll_mask = y_test > 200.0
            if any(high_poll_mask):
                hp_act = y_test[high_poll_mask]
                hp_prd = pred_test[high_poll_mask]
                hp_res = test_residuals[high_poll_mask]
                high_pollution_metrics = {
                    "threshold_pm25": 200.0,
                    "sample_count": int(np.sum(high_poll_mask)),
                    "pct_of_test_samples": round(float(np.sum(high_poll_mask) / n_test) * 100.0, 2),
                    "mean_actual": round(float(np.mean(hp_act)), 2),
                    "mean_predicted": round(float(np.mean(hp_prd)), 2),
                    "mean_residual": round(float(np.mean(hp_res)), 4),
                    "mae": round(float(np.mean(np.abs(hp_res))), 4),
                    "rmse": round(float(np.sqrt(np.mean(hp_res ** 2))), 4),
                }
            else:
                high_pollution_metrics = {
                    "threshold_pm25": 200.0,
                    "sample_count": 0,
                    "pct_of_test_samples": 0.0,
                    "mean_actual": None,
                    "mean_predicted": None,
                    "mean_residual": None,
                    "mae": None,
                    "rmse": None,
                }

            # Systematic Bias Assessment
            mean_test_res = float(np.mean(test_residuals))
            if mean_test_res > 5.0:
                bias_direction = "UNDER_PREDICTION (Model tends to output values lower than actual PM2.5)"
            elif mean_test_res < -5.0:
                bias_direction = "OVER_PREDICTION (Model tends to output values higher than actual PM2.5)"
            else:
                bias_direction = "BALANCED (Mean residual within [-5.0, +5.0] ug/m3)"

            residual_diagnostics[h_name] = {
                "systematic_bias": {
                    "mean_residual": round(mean_test_res, 4),
                    "median_residual": round(float(np.median(test_residuals)), 4),
                    "bias_direction": bias_direction,
                },
                "high_pollution_analysis": high_pollution_metrics,
                "temporal_breakdown": {
                    "by_hour_of_day": hours_breakdown,
                    "by_day_of_week": day_breakdown,
                },
            }

        # Save Residuals CSV
        residuals_csv_path = self.residual_dir / "residuals.csv"
        with open(residuals_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(residual_records[0].keys()))
            writer.writeheader()
            writer.writerows(residual_records)

        # Save Residual Summary JSON
        residual_summary_path = self.residual_dir / "residual_summary.json"
        with open(residual_summary_path, "w", encoding="utf-8") as f:
            json.dump({
                "phase": "1E-J2D — RESIDUAL ANALYSIS, UNCERTAINTY & RELIABILITY ESTIMATION",
                "scope_statement": "Station-level pilot residual diagnostics on real Anand Vihar historical data.",
                "created_at": now_utc,
                "horizons": residual_summary,
            }, f, indent=2)

        # Save Residual Diagnostics JSON
        residual_diag_path = self.residual_dir / "residual_diagnostics.json"
        with open(residual_diag_path, "w", encoding="utf-8") as f:
            json.dump({
                "phase": "1E-J2D — RESIDUAL ANALYSIS, UNCERTAINTY & RELIABILITY ESTIMATION",
                "created_at": now_utc,
                "horizons": residual_diagnostics,
            }, f, indent=2)

        # Uncertainty Metrics JSON
        uncertainty_json_path = self.residual_dir / "uncertainty_metrics.json"
        uncertainty_payload = {
            "phase": "1E-J2D — RESIDUAL ANALYSIS, UNCERTAINTY & RELIABILITY ESTIMATION",
            "conformal_guarantee_disclaimer": CONFORMAL_GUARANTEE_STATEMENT,
            "indexing_convention": (
                "k = min(ceil((N_val + 1) * (1 - alpha)), N_val) order statistic of sorted "
                "absolute validation residuals."
            ),
            "created_at": now_utc,
            "horizons": uncertainty_metrics,
            "interval_widths_by_horizon": horizon_widths,
        }
        with open(uncertainty_json_path, "w", encoding="utf-8") as f:
            json.dump(uncertainty_payload, f, indent=2)

        # Calibration Report JSON
        calib_report_path = self.residual_dir / "calibration_report.json"
        calibration_report = {
            "status": "COMPLETED",
            "conformal_guarantee_statement": CONFORMAL_GUARANTEE_STATEMENT,
            "calibration_summary": {
                h: {
                    "80_pct_target": {
                        "radius": metrics["conformal_radius_80"],
                        "width": metrics["average_interval_width_80"],
                        "test_empirical_coverage_pct": metrics["test_empirical_coverage_80_pct"],
                        "coverage_error_pct": metrics["coverage_error_80_pct"],
                    },
                    "90_pct_target": {
                        "radius": metrics["conformal_radius_90"],
                        "width": metrics["average_interval_width_90"],
                        "test_empirical_coverage_pct": metrics["test_empirical_coverage_90_pct"],
                        "coverage_error_pct": metrics["coverage_error_90_pct"],
                    },
                }
                for h, metrics in uncertainty_metrics.items()
            },
            "operational_guidelines": [
                "Intervals lower and upper bounds are unclipped to preserve mathematical calibration semantics.",
                "Interval widths within each horizon are constant (2 * q) derived from validation residuals.",
                "Empirical coverage on holdout test set reflects actual performance under observed temporal distribution shifts.",
            ],
        }
        with open(calib_report_path, "w", encoding="utf-8") as f:
            json.dump(calibration_report, f, indent=2)

        # Baseline Reconciliation
        reconciliation_path = self.residual_dir / "baseline_reconciliation.json"
        reconciliation = self.reconcile_baselines()
        with open(reconciliation_path, "w", encoding="utf-8") as f:
            json.dump(reconciliation, f, indent=2)

        return {
            "status": "COMPLETED",
            "conformal_guarantee_disclaimer": CONFORMAL_GUARANTEE_STATEMENT,
            "uncertainty_metrics": uncertainty_metrics,
            "horizon_widths": horizon_widths,
            "residual_summary": residual_summary,
            "residual_diagnostics": residual_diagnostics,
            "reconciliation": reconciliation,
            "artifacts": {
                "residuals_csv": str(residuals_csv_path),
                "residual_summary_json": str(residual_summary_path),
                "residual_diagnostics_json": str(residual_diag_path),
                "uncertainty_metrics_json": str(uncertainty_json_path),
                "calibration_report_json": str(calib_report_path),
                "baseline_reconciliation_json": str(reconciliation_path),
            },
        }

    def reconcile_baselines(self) -> Dict[str, Any]:
        """
        Reconciles Phase 1E-J2B baseline evaluation with Phase 1E-J2C/J2D persistence evaluation.
        """
        j2b_path = self.data_root / "processed" / "forecasting" / "baseline" / "baseline_metrics.json"
        j2c_path = self.eval_dir / "lightgbm_metrics.json"

        j2b_data = {}
        if j2b_path.exists():
            with open(j2b_path, "r", encoding="utf-8") as f:
                j2b_data = json.load(f)

        j2c_data = {}
        if j2c_path.exists():
            with open(j2c_path, "r", encoding="utf-8") as f:
                j2c_data = json.load(f)

        reconciled_horizons = {}
        for h_name in ["+1h", "+3h", "+6h"]:
            j2b_h = j2b_data.get("horizons", {}).get(h_name, {})
            j2c_h = j2c_data.get("horizon_models", {}).get(h_name, {})

            pers_comp = j2c_h.get("persistence_comparison", {})
            lgb_test = j2c_h.get("test_metrics", {})

            reconciled_horizons[h_name] = {
                "j2b_full_station_baseline": {
                    "sample_count": j2b_h.get("sample_count"),
                    "mae": j2b_h.get("mae"),
                    "rmse": j2b_h.get("rmse"),
                    "smape": j2b_h.get("smape"),
                },
                "j2c_holdout_test_baseline": {
                    "sample_count": lgb_test.get("sample_count"),
                    "mae": pers_comp.get("persistence_mae"),
                    "rmse": pers_comp.get("persistence_rmse"),
                    "smape": pers_comp.get("persistence_smape"),
                },
                "j2c_lightgbm_model": {
                    "sample_count": lgb_test.get("sample_count"),
                    "mae": lgb_test.get("mae"),
                    "rmse": lgb_test.get("rmse"),
                    "smape": lgb_test.get("smape"),
                },
                "sample_count_difference_note": (
                    "J2B evaluated over full station telemetry (648 timestamps), while J2C/J2D persistence "
                    "is evaluated strictly on the identical holdout test set rows (97/95/94 timestamps)."
                ),
            }

        return {
            "reconciliation_status": "RECONCILED",
            "explanation": (
                "J2C and J2D baseline persistence metrics evaluate the persistence forecaster on the "
                "exact same holdout test set instances used to evaluate the LightGBM models, ensuring a fair "
                "head-to-head benchmark comparison."
            ),
            "horizons": reconciled_horizons,
        }
