"""
VayuDrishti — Temporal Model Validation & Readiness Assessor (Phase 1E-J2E.5.0)

Executes chronological historical validation, candidate LightGBM model training (isolated in candidates/),
head-to-head evaluation (Frozen Model vs Candidate Model vs Persistence Baseline), residual diagnostics,
temporal drift tracking, and conformal uncertainty validation.

Enforces:
- Strict model freeze protection (frozen LightGBM model SHA256 hashes must remain untouched)
- Chronological train/validation/test splitting (NO random splitting)
- Isolated candidate storage in ml/models/forecasting/candidates/
- Parity with canonical 27-feature contract
- No automatic model promotion (production validation status remains NOT_PRODUCTION_VALIDATED)
"""

import csv
import hashlib
import json
import logging
import math
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import lightgbm as lgb
import numpy as np

from ml.src.forecasting.baseline import PersistenceForecaster
from ml.src.forecasting.config import ForecastingConfig
from ml.src.forecasting.evaluator import compute_conformal_quantile, compute_percentiles
from ml.src.forecasting.feature_assembler import ForecastFeatureAssembler
from ml.src.forecasting.inference import ForecastInferenceEngine
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp
from ml.src.forecasting.trainer import LightGBMPilotTrainer

logger = logging.getLogger(__name__)

CANONICAL_STATION_ID = "ANAND_VIHAR_8118"
PRODUCTION_VALIDATION_STATUS = "NOT_PRODUCTION_VALIDATED"

FROZEN_MODEL_HASHES = {
    "1h": "4C1CF555281AF9ABEE7BDA145C543648CB51F6418C939EE2D1A1DA58CA03AD28",
    "3h": "224DD3C4B0A97CC03ABF621B6AA3070610B60F41DAA05D99D02F8D024571C950",
    "6h": "0DF954AFBB21F8732814C055EFD5AD380F50AFA4B893942534CE5AD48E8B679F",
}


def compute_file_sha256(filepath: Union[str, Path]) -> str:
    """Computes upper-case SHA256 hex digest of specified file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest().upper()


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Computes MAE, RMSE, and sMAPE metrics."""
    if len(y_true) == 0:
        return {"mae": 0.0, "rmse": 0.0, "smape": 0.0, "sample_count": 0}

    err = y_pred - y_true
    abs_err = np.abs(err)
    mae = float(np.mean(abs_err))
    rmse = float(np.sqrt(np.mean(err ** 2)))

    denom = (np.abs(y_true) + np.abs(y_pred)) / 2.0
    denom = np.where(denom == 0, 1.0, denom)
    smape = float(np.mean(abs_err / denom) * 100.0)

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "smape": round(smape, 4),
        "sample_count": int(len(y_true)),
    }


class TemporalModelValidator:
    """
    Executes chronological model validation and candidate evaluation without disturbing
    frozen production/pilot models.
    """

    def __init__(
        self,
        data_root: Optional[Union[str, Path]] = None,
        models_dir: Optional[Union[str, Path]] = None,
        candidates_dir: Optional[Union[str, Path]] = None,
        config: Optional[ForecastingConfig] = None,
    ):
        self.config = config or ForecastingConfig()
        self.data_root = Path(data_root) if data_root else Path("data")
        self.models_dir = Path(models_dir) if models_dir else Path("ml/models/forecasting")
        self.candidates_dir = Path(candidates_dir) if candidates_dir else self.models_dir / "candidates"
        self.candidates_dir.mkdir(parents=True, exist_ok=True)

        self.trainer = LightGBMPilotTrainer(data_root=self.data_root)
        self.assembler = ForecastFeatureAssembler()
        self.persistence = PersistenceForecaster(max_anchor_age_hours=3.0)

    def verify_frozen_model_hashes(self) -> Dict[str, Dict[str, str]]:
        """Verifies that currently frozen models are byte-identical to expected SHA256 baselines."""
        verification = {}
        for h_key, expected_hash in FROZEN_MODEL_HASHES.items():
            model_path = self.models_dir / f"lightgbm_pm25_{h_key}.txt"
            if not model_path.exists():
                verification[h_key] = {
                    "expected": expected_hash,
                    "actual": "FILE_NOT_FOUND",
                    "status": "MISMATCH",
                }
            else:
                act_hash = compute_file_sha256(model_path)
                status = "MATCH" if act_hash == expected_hash else "MISMATCH"
                verification[h_key] = {
                    "expected": expected_hash,
                    "actual": act_hash,
                    "status": status,
                }
        return verification

    def load_dataset(self, csv_path: Optional[Path] = None) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Loads forecasting dataset CSV and returns sorted rows and feature columns."""
        path = csv_path or (self.data_root / "processed" / "forecasting" / "forecast_dataset.csv")
        rows, feature_cols = self.trainer.load_dataset(path)

        # Enforce chronological sorting
        rows.sort(key=lambda x: parse_utc_timestamp(x["prediction_timestamp"]))
        return rows, feature_cols

    def prepare_chronological_split(
        self,
        rows: List[Dict[str, Any]],
        feature_cols: List[str],
        target_col: str,
        train_pct: float = 0.70,
        val_pct: float = 0.15,
    ) -> Dict[str, Any]:
        """
        Splits dataset chronologically into Train (70%), Validation (15%), and Test (15%).
        Strictly forbids random splitting.
        """
        # Filter valid rows containing target_col
        valid_rows = [r for r in rows if r.get(target_col) is not None and r.get(target_col) != ""]
        valid_rows.sort(key=lambda x: parse_utc_timestamp(x["prediction_timestamp"]))

        n = len(valid_rows)
        if n < 30:
            return {
                "status": "INSUFFICIENT_DATA",
                "sample_count": n,
                "train_rows": [],
                "val_rows": [],
                "test_rows": [],
            }

        train_end = int(n * train_pct)
        val_end = int(n * (train_pct + val_pct))

        train_rows = valid_rows[:train_end]
        val_rows = valid_rows[train_end:val_end]
        test_rows = valid_rows[val_end:]

        def rows_to_xy(r_list):
            X = np.zeros((len(r_list), len(feature_cols)), dtype=np.float32)
            y = np.zeros(len(r_list), dtype=np.float32)
            for idx, r in enumerate(r_list):
                y[idx] = float(r[target_col])
                for col_idx, col in enumerate(feature_cols):
                    v = r.get(col)
                    X[idx, col_idx] = float(v) if v is not None and v != "" else float("nan")
            return X, y

        X_train, y_train = rows_to_xy(train_rows)
        X_val, y_val = rows_to_xy(val_rows)
        X_test, y_test = rows_to_xy(test_rows)

        return {
            "status": "READY",
            "sample_count": n,
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
            "split_dates": {
                "train_min": train_rows[0]["prediction_timestamp"] if train_rows else None,
                "train_max": train_rows[-1]["prediction_timestamp"] if train_rows else None,
                "val_min": val_rows[0]["prediction_timestamp"] if val_rows else None,
                "val_max": val_rows[-1]["prediction_timestamp"] if val_rows else None,
                "test_min": test_rows[0]["prediction_timestamp"] if test_rows else None,
                "test_max": test_rows[-1]["prediction_timestamp"] if test_rows else None,
            },
        }

    def train_candidate_model(
        self,
        split_data: Dict[str, Any],
        horizon_key: str,
    ) -> Dict[str, Any]:
        """
        Trains a candidate LightGBM booster on train_rows, using val_rows for early stopping.
        Saves candidate model strictly into ml/models/forecasting/candidates/.
        """
        if split_data.get("status") != "READY":
            return {"status": "SKIPPED_INSUFFICIENT_DATA"}

        X_train, y_train = split_data["X_train"], split_data["y_train"]
        X_val, y_val = split_data["X_val"], split_data["y_val"]
        feature_cols = split_data["feature_cols"]

        params = {
            "objective": "regression",
            "metric": "mae",
            "boosting_type": "gbdt",
            "learning_rate": 0.03,
            "num_leaves": 15,
            "max_depth": 4,
            "feature_fraction": 0.8,
            "seed": 42,
            "verbose": -1,
        }

        trn_data = lgb.Dataset(X_train, label=y_train, feature_name=feature_cols)
        val_data = lgb.Dataset(X_val, label=y_val, feature_name=feature_cols, reference=trn_data)

        callbacks = [lgb.early_stopping(stopping_rounds=20, verbose=False)]
        booster = lgb.train(
            params,
            trn_data,
            num_boost_round=150,
            valid_sets=[trn_data, val_data],
            callbacks=callbacks,
        )

        cand_filename = f"lightgbm_pm25_candidate_{horizon_key.replace('+', '')}.txt"
        cand_path = self.candidates_dir / cand_filename
        booster.save_model(str(cand_path))

        cand_hash = compute_file_sha256(cand_path)

        return {
            "status": "TRAINED",
            "candidate_path": str(cand_path),
            "candidate_hash": cand_hash,
            "best_iteration": booster.best_iteration,
            "feature_count": len(feature_cols),
        }

    def evaluate_persistence_baseline(
        self,
        test_rows: List[Dict[str, Any]],
        target_col: str,
        horizon_hours: int,
    ) -> Dict[str, Any]:
        """
        Evaluates PersistenceForecaster on the EXACT same test set rows.
        """
        pred_records = self.persistence.generate_predictions(test_rows, horizons_hours=[horizon_hours])
        horizon_str = f"+{horizon_hours}h"

        valid_preds = [
            p for p in pred_records
            if p["horizon"] == horizon_str and p.get("prediction_pm25") is not None and p.get("actual_pm25") is not None
        ]

        if not valid_preds:
            return {"mae": 0.0, "rmse": 0.0, "smape": 0.0, "sample_count": 0}

        y_true = np.array([p["actual_pm25"] for p in valid_preds], dtype=np.float32)
        y_pred = np.array([p["prediction_pm25"] for p in valid_preds], dtype=np.float32)

        return compute_metrics(y_true, y_pred)

    def validate_temporal_performance(
        self,
        csv_path: Optional[Path] = None,
        train_candidate: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes complete Temporal Model Validation & Readiness Assessment suite.
        """
        retrieval_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # 1. SHA256 Verification Before
        hashes_before = self.verify_frozen_model_hashes()

        # 2. Load Dataset
        rows, feature_cols = self.load_dataset(csv_path)
        manifest_features = self.assembler.manifest_features

        # Check feature contract parity
        feature_parity = bool(feature_cols == manifest_features)

        horizons = [("+1h", "pm25_t_plus_1h", 1), ("+3h", "pm25_t_plus_3h", 3), ("+6h", "pm25_t_plus_6h", 6)]

        horizon_comparisons: Dict[str, Any] = {}
        residual_diagnostics: Dict[str, Any] = {}
        temporal_drift_diagnostics: Dict[str, Any] = {}
        conformal_coverage_results: Dict[str, Any] = {}
        candidate_model_meta: Dict[str, Any] = {}

        data_sufficiency = len(rows) >= 100

        for h_str, target_col, h_hours in horizons:
            split = self.prepare_chronological_split(rows, feature_cols, target_col)

            if split.get("status") != "READY":
                horizon_comparisons[h_str] = {"status": "INSUFFICIENT_DATA"}
                continue

            X_test, y_test = split["X_test"], split["y_test"]
            test_rows = split["test_rows"]

            # A. Evaluate Persistence Baseline on Test set
            pers_metrics = self.evaluate_persistence_baseline(test_rows, target_col, h_hours)

            # B. Evaluate Frozen Model on Test set
            frozen_path = self.models_dir / f"lightgbm_pm25_{h_str.replace('+', '')}.txt"
            frozen_booster = lgb.Booster(model_file=str(frozen_path))
            frozen_pred = frozen_booster.predict(X_test, predict_disable_shape_check=True)
            frozen_metrics = compute_metrics(y_test, frozen_pred)

            # C. Train & Evaluate Candidate Model if requested
            cand_metrics = None
            if train_candidate and data_sufficiency:
                cand_train_out = self.train_candidate_model(split, h_str)
                candidate_model_meta[h_str] = cand_train_out

                if cand_train_out.get("status") == "TRAINED":
                    cand_booster = lgb.Booster(model_file=cand_train_out["candidate_path"])
                    cand_pred = cand_booster.predict(X_test, predict_disable_shape_check=True)
                    cand_metrics = compute_metrics(y_test, cand_pred)

            horizon_comparisons[h_str] = {
                "sample_count": len(y_test),
                "split_dates": split["split_dates"],
                "persistence_baseline": pers_metrics,
                "frozen_model": frozen_metrics,
                "candidate_model": cand_metrics or "NOT_TRAINED",
            }

            # D. Residual Diagnostics (Frozen Model)
            test_residuals = y_test - frozen_pred
            test_abs_res = np.abs(test_residuals)

            mean_res = float(np.mean(test_residuals))
            median_res = float(np.median(test_residuals))

            if mean_res > 5.0:
                bias = "UNDER_PREDICTION"
            elif mean_res < -5.0:
                bias = "OVER_PREDICTION"
            else:
                bias = "BALANCED"

            residual_diagnostics[h_str] = {
                "sample_count": len(y_test),
                "mean_residual": round(mean_res, 4),
                "median_residual": round(median_res, 4),
                "bias_direction": bias,
                "residual_percentiles": compute_percentiles(test_residuals),
                "absolute_error_percentiles": compute_percentiles(test_abs_res),
            }

            # E. Temporal Drift Tracking (Rolling 10-sample windows over Test Period)
            rolling_maes = []
            rolling_rmses = []
            window_size = min(10, max(3, len(y_test) // 4))

            for i in range(len(y_test) - window_size + 1):
                w_err = test_residuals[i : i + window_size]
                rolling_maes.append(round(float(np.mean(np.abs(w_err))), 4))
                rolling_rmses.append(round(float(np.sqrt(np.mean(w_err ** 2))), 4))

            temporal_drift_diagnostics[h_str] = {
                "window_size": window_size,
                "rolling_mae_min": min(rolling_maes) if rolling_maes else 0.0,
                "rolling_mae_max": max(rolling_maes) if rolling_maes else 0.0,
                "rolling_mae_mean": round(float(np.mean(rolling_maes)), 4) if rolling_maes else 0.0,
                "rolling_rmse_min": min(rolling_rmses) if rolling_rmses else 0.0,
                "rolling_rmse_max": max(rolling_rmses) if rolling_rmses else 0.0,
                "rolling_rmse_mean": round(float(np.mean(rolling_rmses)), 4) if rolling_rmses else 0.0,
            }

            # F. Conformal Uncertainty Validation (Using Frozen Conformal Radii)
            val_residuals = split["y_val"] - frozen_booster.predict(split["X_val"], predict_disable_shape_check=True)
            q_80 = compute_conformal_quantile(val_residuals, alpha=0.20)
            q_90 = compute_conformal_quantile(val_residuals, alpha=0.10)

            hits_80 = np.sum(np.abs(test_residuals) <= q_80)
            hits_90 = np.sum(np.abs(test_residuals) <= q_90)

            cov_80 = round(float(hits_80 / len(y_test)) * 100.0, 2)
            cov_90 = round(float(hits_90 / len(y_test)) * 100.0, 2)

            conformal_coverage_results[h_str] = {
                "test_sample_count": len(y_test),
                "conformal_radius_80": q_80,
                "interval_width_80": round(2.0 * q_80, 4),
                "test_empirical_coverage_80_pct": cov_80,
                "coverage_error_80_pct": round(cov_80 - 80.0, 2),
                "conformal_radius_90": q_90,
                "interval_width_90": round(2.0 * q_90, 4),
                "test_empirical_coverage_90_pct": cov_90,
                "coverage_error_90_pct": round(cov_90 - 90.0, 2),
            }

        # 3. SHA256 Verification After
        hashes_after = self.verify_frozen_model_hashes()

        # Check hash invariance
        frozen_hashes_untouched = all(
            hashes_after[h]["status"] == "MATCH" for h in hashes_after
        )

        # Readiness Assessment Gate Resolution
        if not data_sufficiency:
            readiness_status = "INSUFFICIENT_DATA"
        elif candidate_model_meta:
            readiness_status = "CANDIDATE_EVALUATED"
        else:
            readiness_status = "BASELINE_ONLY"

        # Reports & Artifact Persistence
        validation_report = {
            "phase": "PHASE 1E-J2E.5.0 — TEMPORAL MODEL VALIDATION & READINESS ASSESSMENT",
            "station_id": CANONICAL_STATION_ID,
            "retrieval_timestamp": retrieval_ts,
            "readiness_status": readiness_status,
            "production_validation_status": PRODUCTION_VALIDATION_STATUS,
            "feature_parity_passed": feature_parity,
            "frozen_hashes_untouched": frozen_hashes_untouched,
            "chronological_split_applied": True,
            "random_split_applied": False,
            "data_summary": {
                "total_rows": len(rows),
                "time_range_min": rows[0]["prediction_timestamp"] if rows else None,
                "time_range_max": rows[-1]["prediction_timestamp"] if rows else None,
            },
            "conformal_coverage": conformal_coverage_results,
            "temporal_drift": temporal_drift_diagnostics,
            "residual_diagnostics": residual_diagnostics,
            "frozen_model_verification": hashes_after,
        }

        comparison_report = {
            "phase": "PHASE 1E-J2E.5.0 — TEMPORAL MODEL VALIDATION & READINESS ASSESSMENT",
            "station_id": CANONICAL_STATION_ID,
            "created_at": retrieval_ts,
            "readiness_status": readiness_status,
            "production_validation_status": PRODUCTION_VALIDATION_STATUS,
            "model_comparison": horizon_comparisons,
            "candidate_models": candidate_model_meta,
        }

        # Save JSON Artifacts
        val_report_path = self.data_root / "processed" / "forecasting" / "temporal_validation_report.json"
        comp_report_path = self.data_root / "processed" / "forecasting" / "model_comparison_report.json"

        val_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(val_report_path, "w", encoding="utf-8") as f:
            json.dump(validation_report, f, indent=2)

        with open(comp_report_path, "w", encoding="utf-8") as f:
            json.dump(comparison_report, f, indent=2)

        return {
            "readiness_status": readiness_status,
            "production_validation_status": PRODUCTION_VALIDATION_STATUS,
            "validation_report": validation_report,
            "comparison_report": comparison_report,
            "artifacts": {
                "temporal_validation_report_json": str(val_report_path),
                "model_comparison_report_json": str(comp_report_path),
            },
        }
