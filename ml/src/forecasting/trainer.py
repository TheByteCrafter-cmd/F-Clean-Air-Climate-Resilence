"""
VayuDrishti — LightGBM Air Quality Pilot Model Trainer (Phase 1E-J2C)

Provides deterministic, leakage-safe LightGBM regression model training and evaluation
for station-level PM2.5 forecasting over +1h, +3h, and +6h target horizons on real
historical telemetry (Anand Vihar 8118 station).
"""

import csv
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import lightgbm as lgb
import numpy as np

from ml.src.forecasting.baseline import PersistenceForecaster
from ml.src.forecasting.config import ForecastingConfig
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

# Mandatory Non-Feature Columns (Identifiers and Targets)
NON_FEATURE_COLUMNS = {
    "station_id",
    "prediction_timestamp",
    "station_name",
    "pm25_t0",
    "pm10_t0",
    "pm25_t_plus_1h",
    "pm25_t_plus_3h",
    "pm25_t_plus_6h",
    "pm10_t_plus_1h",
    "pm10_t_plus_3h",
    "pm10_t_plus_6h",
    "source_file",
}


def calculate_smape(actuals: np.ndarray, predictions: np.ndarray) -> Optional[float]:
    """Calculates Symmetric Mean Absolute Percentage Error (sMAPE) safely."""
    if len(actuals) == 0:
        return None
    denom = (np.abs(actuals) + np.abs(predictions)) / 2.0
    # Avoid zero division
    valid_mask = denom > 1e-6
    if not np.any(valid_mask):
        return None
    smape_val = np.mean(np.abs(actuals[valid_mask] - predictions[valid_mask]) / denom[valid_mask]) * 100.0
    return round(float(smape_val), 4)


class LightGBMPilotTrainer:
    """Manages data loading, chronological splitting, LightGBM training, and evaluation."""

    def __init__(
        self,
        data_root: Optional[Union[str, Path]] = None,
        config: Optional[ForecastingConfig] = None,
        random_state: int = 42,
    ):
        self.config = config or ForecastingConfig()
        self.data_root = Path(data_root) if data_root else Path(os.getcwd()) / "data"
        self.models_dir = Path(os.getcwd()) / "ml" / "models" / "forecasting"
        self.eval_dir = self.data_root / "processed" / "forecasting" / "model_evaluation"

        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.eval_dir.mkdir(parents=True, exist_ok=True)

        self.random_state = random_state

    def derive_feature_columns(self, all_columns: List[str]) -> List[str]:
        """Dynamically derives feature column names from dataset header."""
        feature_cols = [col for col in all_columns if col not in NON_FEATURE_COLUMNS]
        return feature_cols

    def load_dataset(
        self, csv_path: Optional[Path] = None
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Loads processed forecast dataset CSV and derives feature columns."""
        target_path = csv_path or (self.data_root / "processed" / "forecasting" / "forecast_dataset.csv")

        if not target_path.exists():
            raise FileNotFoundError(f"Forecast dataset not found at {target_path}")

        with open(target_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            all_cols = reader.fieldnames or []
            rows = list(reader)

        feature_cols = self.derive_feature_columns(all_cols)
        logger.info(f"Loaded {len(rows)} dataset rows. Derived {len(feature_cols)} feature columns: {feature_cols}")

        return rows, feature_cols

    def prepare_split_data(
        self,
        rows: List[Dict[str, Any]],
        feature_cols: List[str],
        target_col: str,
        train_pct: float = 0.70,
        val_pct: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Filters valid target rows and splits chronologically into train, val, and test.
        """
        # 1. Filter valid target rows
        valid_rows = []
        for r in rows:
            target_val = r.get(target_col)
            if target_val not in (None, "", "NaN"):
                try:
                    val_float = float(target_val)
                    row_copy = dict(r)
                    row_copy["_target_float"] = val_float
                    valid_rows.append(row_copy)
                except (ValueError, TypeError):
                    pass

        # Sort chronologically by prediction_timestamp
        valid_rows.sort(key=lambda x: parse_utc_timestamp(x["prediction_timestamp"]))

        n_total = len(valid_rows)
        if n_total < 20:
            raise ValueError(f"Insufficient valid target rows ({n_total}) for target {target_col}")

        n_train = int(n_total * train_pct)
        n_val = int(n_total * val_pct)
        n_test = n_total - n_train - n_val

        train_rows = valid_rows[:n_train]
        val_rows = valid_rows[n_train : n_train + n_val]
        test_rows = valid_rows[n_train + n_val :]

        def extract_x_y(row_list: List[Dict[str, Any]]) -> Tuple[np.ndarray, np.ndarray]:
            X = np.zeros((len(row_list), len(feature_cols)), dtype=np.float32)
            y = np.zeros(len(row_list), dtype=np.float32)

            for i, r in enumerate(row_list):
                y[i] = r["_target_float"]
                for j, col in enumerate(feature_cols):
                    v = r.get(col)
                    if v in (None, "", "NaN"):
                        X[i, j] = np.nan
                    else:
                        try:
                            X[i, j] = float(v)
                        except (ValueError, TypeError):
                            X[i, j] = np.nan
            return X, y

        X_train, y_train = extract_x_y(train_rows)
        X_val, y_val = extract_x_y(val_rows)
        X_test, y_test = extract_x_y(test_rows)

        return {
            "target_col": target_col,
            "total_usable_rows": n_total,
            "feature_cols": feature_cols,
            "train_rows": train_rows,
            "val_rows": val_rows,
            "test_rows": test_rows,
            "X_train": X_train,
            "y_train": y_train,
            "X_val": X_val,
            "y_val": y_val,
            "X_test": X_test,
            "y_test": y_test,
            "train_range": (train_rows[0]["prediction_timestamp"], train_rows[-1]["prediction_timestamp"]),
            "val_range": (val_rows[0]["prediction_timestamp"], val_rows[-1]["prediction_timestamp"]),
            "test_range": (test_rows[0]["prediction_timestamp"], test_rows[-1]["prediction_timestamp"]),
        }

    def train_horizon_model(
        self,
        horizon_name: str,
        target_col: str,
        split_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Trains LightGBM model for a single horizon using validation set early stopping
        and evaluates holdout test set performance against persistence baseline.
        """
        feature_cols = split_data["feature_cols"]
        X_train, y_train = split_data["X_train"], split_data["y_train"]
        X_val, y_val = split_data["X_val"], split_data["y_val"]
        X_test, y_test = split_data["X_test"], split_data["y_test"]
        test_rows = split_data["test_rows"]

        # LightGBM Dataset creation
        lgb_train = lgb.Dataset(X_train, label=y_train, feature_name=feature_cols, free_raw_data=False)
        lgb_val = lgb.Dataset(X_val, label=y_val, feature_name=feature_cols, reference=lgb_train, free_raw_data=False)

        params = {
            "objective": "regression",
            "metric": "rmse",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": -1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": self.random_state,
            "verbosity": -1,
        }

        callbacks = [
            lgb.early_stopping(stopping_rounds=30, first_metric_only=True, verbose=False),
            lgb.log_evaluation(period=0),
        ]

        t0 = time.time()
        gbm = lgb.train(
            params,
            lgb_train,
            num_boost_round=300,
            valid_sets=[lgb_val],
            callbacks=callbacks,
        )
        t_duration = round(time.time() - t0, 3)

        best_iter = gbm.best_iteration if gbm.best_iteration > 0 else 300

        # Predictions across splits
        pred_train = gbm.predict(X_train, num_iteration=best_iter)
        pred_val = gbm.predict(X_val, num_iteration=best_iter)
        pred_test = gbm.predict(X_test, num_iteration=best_iter)

        # Prediction Sanity Check (Correction 3 requirement)
        sanity_check = {
            "is_numeric": bool(np.issubdtype(pred_test.dtype, np.number)),
            "is_finite": bool(np.all(np.isfinite(pred_test))),
            "has_nans": bool(np.isnan(pred_test).any()),
            "count": len(pred_test),
            "expected_count": len(y_test),
            "negative_predictions_count": int(np.sum(pred_test < 0.0)),
        }

        def compute_metrics(act: np.ndarray, pred: np.ndarray) -> Dict[str, Any]:
            mae = round(float(np.mean(np.abs(act - pred))), 4)
            rmse = round(float(np.sqrt(np.mean((act - pred) ** 2))), 4)
            smape = calculate_smape(act, pred)
            return {"mae": mae, "rmse": rmse, "smape": smape, "sample_count": len(act)}

        train_metrics = compute_metrics(y_train, pred_train)
        val_metrics = compute_metrics(y_val, pred_val)
        test_metrics = compute_metrics(y_test, pred_test)

        # Evaluate Persistence Baseline on identical Test set rows
        horizon_h = int(horizon_name.replace("+", "").replace("h", ""))
        forecaster = PersistenceForecaster(max_anchor_age_hours=3.0)

        # Prepare test rows for PersistenceForecaster
        pers_preds = forecaster.generate_predictions(test_rows, horizons_hours=[horizon_h])
        valid_pers = [p for p in pers_preds if p["horizon"] == f"+{horizon_h}h" and p["absolute_error"] is not None]

        if valid_pers:
            pers_mae = round(sum(p["absolute_error"] for p in valid_pers) / len(valid_pers), 4)
            pers_rmse = round((sum(p["squared_error"] for p in valid_pers) / len(valid_pers)) ** 0.5, 4)
            pers_smape = calculate_smape(
                np.array([p["actual_pm25"] for p in valid_pers]),
                np.array([p["prediction_pm25"] for p in valid_pers]),
            )
        else:
            pers_mae, pers_rmse, pers_smape = None, None, None

        # Improvement percentages over Persistence
        if pers_mae and pers_mae > 0:
            mae_improvement_pct = round(((pers_mae - test_metrics["mae"]) / pers_mae) * 100.0, 2)
        else:
            mae_improvement_pct = None

        if pers_rmse and pers_rmse > 0:
            rmse_improvement_pct = round(((pers_rmse - test_metrics["rmse"]) / pers_rmse) * 100.0, 2)
        else:
            rmse_improvement_pct = None

        # Feature Importance (Gain-based)
        raw_importance = gbm.feature_importance(importance_type="gain")
        importance_list = [
            {"feature": col, "importance": round(float(imp), 4), "importance_type": "gain"}
            for col, imp in zip(feature_cols, raw_importance)
        ]
        importance_list.sort(key=lambda x: x["importance"], reverse=True)

        # Save Model Artifact
        model_filename = f"lightgbm_pm25_{horizon_name.replace('+', '')}.txt"
        model_path = self.models_dir / model_filename
        gbm.save_model(str(model_path))

        # Overfitting Diagnostic Flag
        overfitting_flag = bool(test_metrics["rmse"] > 1.5 * train_metrics["rmse"])

        return {
            "horizon": horizon_name,
            "target_col": target_col,
            "model_path": str(model_path),
            "model_filename": model_filename,
            "best_iteration": best_iter,
            "training_duration_seconds": t_duration,
            "feature_count": len(feature_cols),
            "feature_list": feature_cols,
            "sanity_check": sanity_check,
            "split_metrics": {
                "train": train_metrics,
                "validation": val_metrics,
                "test": test_metrics,
            },
            "persistence_comparison": {
                "persistence_mae": pers_mae,
                "lightgbm_mae": test_metrics["mae"],
                "mae_improvement_pct": mae_improvement_pct,
                "persistence_rmse": pers_rmse,
                "lightgbm_rmse": test_metrics["rmse"],
                "rmse_improvement_pct": rmse_improvement_pct,
                "persistence_smape": pers_smape,
                "lightgbm_smape": test_metrics["smape"],
            },
            "overfitting_diagnostic": {
                "flagged": overfitting_flag,
                "train_rmse": train_metrics["rmse"],
                "validation_rmse": val_metrics["rmse"],
                "test_rmse": test_metrics["rmse"],
                "ratio_test_train_rmse": round(test_metrics["rmse"] / train_metrics["rmse"], 2) if train_metrics["rmse"] > 0 else None,
            },
            "feature_importance": importance_list,
            "test_predictions": [
                {
                    "station_id": r["station_id"],
                    "prediction_timestamp": r["prediction_timestamp"],
                    "horizon": horizon_name,
                    "actual_pm25": float(r["_target_float"]),
                    "predicted_pm25": round(float(p), 4),
                    "absolute_error": round(float(abs(r["_target_float"] - p)), 4),
                    "squared_error": round(float((r["_target_float"] - p) ** 2), 4),
                    "model_name": f"lightgbm_pm25_{horizon_name.replace('+', '')}",
                }
                for r, p in zip(test_rows, pred_test)
            ],
            "split_ranges": {
                "train": split_data["train_range"],
                "val": split_data["val_range"],
                "test": split_data["test_range"],
            },
        }

    def run_training_pipeline(
        self, csv_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Executes full training pipeline across +1h, +3h, and +6h target horizons."""
        rows, feature_cols = self.load_dataset(csv_path)

        horizons_config = [
            ("+1h", "pm25_t_plus_1h"),
            ("+3h", "pm25_t_plus_3h"),
            ("+6h", "pm25_t_plus_6h"),
        ]

        model_results: Dict[str, Any] = {}
        all_test_predictions: List[Dict[str, Any]] = []
        all_feature_importances: List[Dict[str, Any]] = []

        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        for h_name, target_col in horizons_config:
            logger.info(f"Preparing data and training LightGBM model for horizon {h_name} ({target_col})...")
            split_data = self.prepare_split_data(rows, feature_cols, target_col)
            result = self.train_horizon_model(h_name, target_col, split_data)

            model_results[h_name] = result
            all_test_predictions.extend(result["test_predictions"])

            for imp in result["feature_importance"]:
                imp_copy = dict(imp)
                imp_copy["horizon"] = h_name
                all_feature_importances.append(imp_copy)

        # Save Evaluation Artifacts under data/processed/forecasting/model_evaluation/
        metrics_json_path = self.eval_dir / "lightgbm_metrics.json"
        predictions_csv_path = self.eval_dir / "lightgbm_test_predictions.csv"
        importance_csv_path = self.eval_dir / "lightgbm_feature_importance.csv"
        manifest_json_path = self.models_dir / "model_manifest.json"

        # 1. Metrics JSON
        summary_metrics = {
            "phase": "1E-J2C — LIGHTGBM PILOT MODEL TRAINING",
            "scope_statement": "Station-level pilot result on real Anand Vihar historical data.",
            "creation_timestamp": now_utc,
            "lightgbm_version": lgb.__version__,
            "random_state": self.random_state,
            "dataset_reference": "data/processed/forecasting/forecast_dataset.csv",
            "derived_feature_count": len(feature_cols),
            "feature_columns": feature_cols,
            "horizon_models": {
                h: {
                    "model_filename": res["model_filename"],
                    "best_iteration": res["best_iteration"],
                    "usable_rows": len(res["test_predictions"]) + len(res["split_metrics"]["train"]) + len(res["split_metrics"]["validation"]),
                    "split_counts": {
                        "train": res["split_metrics"]["train"]["sample_count"],
                        "val": res["split_metrics"]["validation"]["sample_count"],
                        "test": res["split_metrics"]["test"]["sample_count"],
                    },
                    "test_metrics": res["split_metrics"]["test"],
                    "persistence_comparison": res["persistence_comparison"],
                    "overfitting_diagnostic": res["overfitting_diagnostic"],
                    "sanity_check": res["sanity_check"],
                }
                for h, res in model_results.items()
            },
        }

        with open(metrics_json_path, "w", encoding="utf-8") as f:
            json.dump(summary_metrics, f, indent=2)

        # 2. Predictions CSV
        if all_test_predictions:
            with open(predictions_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(all_test_predictions[0].keys()))
                writer.writeheader()
                writer.writerows(all_test_predictions)

        # 3. Importance CSV
        if all_feature_importances:
            with open(importance_csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(all_feature_importances[0].keys()))
                writer.writeheader()
                writer.writerows(all_feature_importances)

        # 4. Model Manifest JSON
        manifest_data = {
            "model_family": "LightGBM Regression",
            "scope": "Anand Vihar 8118 Pilot Station Only",
            "scope_statement": "Station-level pilot model trained and evaluated on real historical Anand Vihar data.",
            "created_at": now_utc,
            "lightgbm_version": lgb.__version__,
            "random_state": self.random_state,
            "feature_count": len(feature_cols),
            "feature_list": feature_cols,
            "models": {
                h: {
                    "artifact_file": res["model_filename"],
                    "artifact_path": res["model_path"],
                    "target_column": res["target_col"],
                    "best_iteration": res["best_iteration"],
                    "test_rmse": res["split_metrics"]["test"]["rmse"],
                    "test_mae": res["split_metrics"]["test"]["mae"],
                    "mae_improvement_pct": res["persistence_comparison"]["mae_improvement_pct"],
                }
                for h, res in model_results.items()
            },
        }
        with open(manifest_json_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        return {
            "scope_statement": "Station-level pilot result on real Anand Vihar historical data.",
            "feature_count": len(feature_cols),
            "feature_columns": feature_cols,
            "horizon_models": model_results,
            "summary_metrics": summary_metrics,
            "artifacts": {
                "models_dir": str(self.models_dir),
                "model_manifest": str(manifest_json_path),
                "metrics_json": str(metrics_json_path),
                "predictions_csv": str(predictions_csv_path),
                "importance_csv": str(importance_csv_path),
            },
        }
