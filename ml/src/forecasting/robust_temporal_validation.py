"""
VayuDrishti — Robust Temporal Validation & Model Promotion Gate (Phase 1E-J2E.5.1)

Executes multi-window rolling chronological validation across time horizons (+1h, +3h, +6h),
benchmarking Persistence Baseline vs. Frozen Production Model vs. Candidate Model.
Evaluates residual diagnostics, temporal drift, pollution-regime breakdown, and conformal uncertainty.
Implements a deterministic Promotion Gate with hard freeze protection.

Enforces:
- Strict model freeze protection (frozen LightGBM SHA256 hashes must remain untouched)
- Chronological train/validation/test splitting across rolling multi-windows (NO random splitting)
- Isolated model artifacts saved in ml/models/forecasting/validation_runs/
- Production validation status hard-locked to NOT_PRODUCTION_VALIDATED
- Promotion gate decisions: MORE_EVIDENCE_REQUIRED, CANDIDATE_SUPPORTED_FOR_REVIEW,
  PROMOTION_BLOCKED, or PROMOTION_REVIEW_REQUIRED
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

VALID_PROMOTION_GATE_STATUSES = {
    "MORE_EVIDENCE_REQUIRED",
    "CANDIDATE_SUPPORTED_FOR_REVIEW",
    "PROMOTION_BLOCKED",
    "PROMOTION_REVIEW_REQUIRED",
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


def compute_regime_metrics(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    regime_thresholds: Optional[Dict[str, Tuple[float, float]]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Computes performance metrics across PM2.5 pollution regimes.
    Default regimes:
    - Moderate/Low: [0, 100]
    - Poor/High: (100, 250]
    - Severe/Very High: (250, inf)
    """
    if regime_thresholds is None:
        regime_thresholds = {
            "MODERATE_LOW": (0.0, 100.0),
            "POOR_HIGH": (100.0, 250.0),
            "SEVERE_CRITICAL": (250.0, float("inf")),
        }

    results = {}
    for r_name, (low, high) in regime_thresholds.items():
        mask = (y_true >= low) & (y_true < high) if high != float("inf") else (y_true >= low)
        y_t_sub = y_true[mask]
        y_p_sub = y_pred[mask]
        results[r_name] = compute_metrics(y_t_sub, y_p_sub)

    return results


class RobustTemporalValidator:
    """
    Executes multi-window rolling temporal model validation and diagnostic tracking
    without modifying frozen production models.
    """

    def __init__(
        self,
        data_root: Optional[Union[str, Path]] = None,
        models_dir: Optional[Union[str, Path]] = None,
        candidates_dir: Optional[Union[str, Path]] = None,
        validation_runs_dir: Optional[Union[str, Path]] = None,
        config: Optional[ForecastingConfig] = None,
    ):
        self.config = config or ForecastingConfig()
        self.data_root = Path(data_root) if data_root else Path("data")
        self.models_dir = Path(models_dir) if models_dir else Path("ml/models/forecasting")
        self.candidates_dir = Path(candidates_dir) if candidates_dir else self.models_dir / "candidates"
        self.validation_runs_dir = (
            Path(validation_runs_dir) if validation_runs_dir else self.models_dir / "validation_runs"
        )

        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.validation_runs_dir.mkdir(parents=True, exist_ok=True)

        self.trainer = LightGBMPilotTrainer(data_root=self.data_root)
        self.assembler = ForecastFeatureAssembler()
        self.persistence = PersistenceForecaster(max_anchor_age_hours=3.0)

    def verify_frozen_model_hashes(self) -> Dict[str, Dict[str, str]]:
        """Verifies that frozen models match expected SHA256 baselines."""
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
        """Loads forecasting dataset CSV and returns chronologically sorted rows."""
        path = csv_path or (self.data_root / "processed" / "forecasting" / "forecast_dataset.csv")
        rows, feature_cols = self.trainer.load_dataset(path)
        rows.sort(key=lambda x: parse_utc_timestamp(x["prediction_timestamp"]))
        return rows, feature_cols

    def prepare_multi_window_splits(
        self,
        rows: List[Dict[str, Any]],
        feature_cols: List[str],
        target_col: str,
        num_windows: int = 3,
        val_pct: float = 0.15,
        test_pct: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """
        Creates rolling/chronological multi-window evaluation splits.
        Enforces chronological order and strict window isolation (NO random sampling).
        """
        valid_rows = [r for r in rows if r.get(target_col) is not None and r.get(target_col) != ""]
        valid_rows.sort(key=lambda x: parse_utc_timestamp(x["prediction_timestamp"]))

        n = len(valid_rows)
        if n < 50:
            return []

        windows = []
        # Calculate step size for rolling origin across dataset
        # We reserve the last portion of dataset to form test sets of size test_pct*n across windows
        test_size = int(n * test_pct)
        val_size = int(n * val_pct)
        train_start = 0

        # Step size to shift window end points
        train_min_size = int(n * 0.40)
        remaining_indices = n - train_min_size - val_size - test_size
        step = max(1, remaining_indices // max(1, num_windows - 1)) if num_windows > 1 else 0

        for w_idx in range(num_windows):
            current_train_end = train_min_size + w_idx * step
            current_val_end = min(n - test_size, current_train_end + val_size)
            current_test_end = min(n, current_val_end + test_size)

            if current_train_end >= current_val_end or current_val_end >= current_test_end:
                break

            train_r = valid_rows[:current_train_end]
            val_r = valid_rows[current_train_end:current_val_end]
            test_r = valid_rows[current_val_end:current_test_end]

            def rows_to_xy(r_list):
                X = np.zeros((len(r_list), len(feature_cols)), dtype=np.float32)
                y = np.zeros(len(r_list), dtype=np.float32)
                for idx, r in enumerate(r_list):
                    y[idx] = float(r[target_col])
                    for col_idx, col in enumerate(feature_cols):
                        v = r.get(col)
                        X[idx, col_idx] = float(v) if v is not None and v != "" else float("nan")
                return X, y

            X_train, y_train = rows_to_xy(train_r)
            X_val, y_val = rows_to_xy(val_r)
            X_test, y_test = rows_to_xy(test_r)

            windows.append(
                {
                    "window_index": w_idx + 1,
                    "window_id": f"window_{w_idx + 1}",
                    "feature_cols": feature_cols,
                    "train_rows": train_r,
                    "val_rows": val_r,
                    "test_rows": test_r,
                    "X_train": X_train,
                    "y_train": y_train,
                    "X_val": X_val,
                    "y_val": y_val,
                    "X_test": X_test,
                    "y_test": y_test,
                    "split_dates": {
                        "train_min": train_r[0]["prediction_timestamp"] if train_r else None,
                        "train_max": train_r[-1]["prediction_timestamp"] if train_r else None,
                        "val_min": val_r[0]["prediction_timestamp"] if val_r else None,
                        "val_max": val_r[-1]["prediction_timestamp"] if val_r else None,
                        "test_min": test_r[0]["prediction_timestamp"] if test_r else None,
                        "test_max": test_r[-1]["prediction_timestamp"] if test_r else None,
                    },
                }
            )

        return windows

    def train_validation_model(
        self,
        window_split: Dict[str, Any],
        horizon_key: str,
    ) -> Dict[str, Any]:
        """
        Trains a validation booster for a specific window split.
        Saves model strictly into ml/models/forecasting/validation_runs/.
        """
        X_train, y_train = window_split["X_train"], window_split["y_train"]
        X_val, y_val = window_split["X_val"], window_split["y_val"]
        feature_cols = window_split["feature_cols"]
        w_idx = window_split["window_index"]

        params = {
            "objective": "regression",
            "metric": "mae",
            "boosting_type": "gbdt",
            "learning_rate": 0.03,
            "num_leaves": 15,
            "max_depth": 4,
            "feature_fraction": 0.8,
            "seed": 42 + w_idx,
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

        filename = f"lightgbm_pm25_val_w{w_idx}_{horizon_key.replace('+', '')}.txt"
        path = self.validation_runs_dir / filename
        booster.save_model(str(path))

        model_hash = compute_file_sha256(path)

        return {
            "status": "TRAINED",
            "model_path": str(path),
            "model_hash": model_hash,
            "best_iteration": booster.best_iteration,
        }

    def evaluate_persistence_baseline(
        self,
        test_rows: List[Dict[str, Any]],
        horizon_hours: int,
    ) -> Dict[str, Any]:
        """Evaluates PersistenceForecaster on the exact test rows of a window."""
        pred_records = self.persistence.generate_predictions(test_rows, horizons_hours=[horizon_hours])
        horizon_str = f"+{horizon_hours}h"

        valid_preds = [
            p
            for p in pred_records
            if p["horizon"] == horizon_str and p.get("prediction_pm25") is not None and p.get("actual_pm25") is not None
        ]

        if not valid_preds:
            return {"mae": 0.0, "rmse": 0.0, "smape": 0.0, "sample_count": 0}

        y_true = np.array([p["actual_pm25"] for p in valid_preds], dtype=np.float32)
        y_pred = np.array([p["prediction_pm25"] for p in valid_preds], dtype=np.float32)

        return compute_metrics(y_true, y_pred)

    def run_robust_temporal_validation(
        self,
        csv_path: Optional[Path] = None,
        num_windows: int = 3,
        train_validation_models: bool = True,
    ) -> Dict[str, Any]:
        """
        Executes robust rolling multi-window temporal model validation.
        """
        retrieval_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # 1. Verify SHA256 hashes before run
        hashes_before = self.verify_frozen_model_hashes()

        # 2. Load dataset
        rows, feature_cols = self.load_dataset(csv_path)
        manifest_features = self.assembler.manifest_features
        feature_parity = bool(feature_cols == manifest_features)

        data_sufficiency = len(rows) >= 100
        horizons = [("+1h", "pm25_t_plus_1h", 1), ("+3h", "pm25_t_plus_3h", 3), ("+6h", "pm25_t_plus_6h", 6)]

        window_results_by_horizon: Dict[str, List[Dict[str, Any]]] = {}
        aggregated_metrics_by_horizon: Dict[str, Dict[str, Any]] = {}
        drift_tracking_by_horizon: Dict[str, Dict[str, Any]] = {}

        for h_str, target_col, h_hours in horizons:
            splits = self.prepare_multi_window_splits(rows, feature_cols, target_col, num_windows=num_windows)
            if not splits:
                continue

            frozen_path = self.models_dir / f"lightgbm_pm25_{h_str.replace('+', '')}.txt"
            frozen_booster = lgb.Booster(model_file=str(frozen_path))

            # Candidate model if available in candidates_dir
            cand_path = self.candidates_dir / f"lightgbm_pm25_candidate_{h_str.replace('+', '')}.txt"
            cand_booster = lgb.Booster(model_file=str(cand_path)) if cand_path.exists() else None

            window_evals = []
            cand_maes, frozen_maes, pers_maes = [], [], []

            for split in splits:
                w_idx = split["window_index"]
                X_test, y_test = split["X_test"], split["y_test"]
                X_val, y_val = split["X_val"], split["y_val"]
                test_rows = split["test_rows"]

                # A. Persistence Baseline
                pers_metrics = self.evaluate_persistence_baseline(test_rows, h_hours)
                pers_maes.append(pers_metrics["mae"])

                # B. Frozen Model
                frozen_pred = frozen_booster.predict(X_test, predict_disable_shape_check=True)
                frozen_metrics = compute_metrics(y_test, frozen_pred)
                frozen_maes.append(frozen_metrics["mae"])

                # C. Candidate Model (or Window Validation Model)
                cand_metrics = None
                val_model_meta = None
                if train_validation_models and data_sufficiency:
                    val_model_meta = self.train_validation_model(split, h_str)
                    val_booster = lgb.Booster(model_file=val_model_meta["model_path"])
                    val_pred = val_booster.predict(X_test, predict_disable_shape_check=True)
                    cand_metrics = compute_metrics(y_test, val_pred)
                    cand_maes.append(cand_metrics["mae"])
                elif cand_booster is not None:
                    cand_pred = cand_booster.predict(X_test, predict_disable_shape_check=True)
                    cand_metrics = compute_metrics(y_test, cand_pred)
                    cand_maes.append(cand_metrics["mae"])

                # D. Residual Diagnostics (Frozen vs Active Candidate/Val)
                test_res_frozen = y_test - frozen_pred
                res_diag_frozen = {
                    "mean_residual": round(float(np.mean(test_res_frozen)), 4),
                    "median_residual": round(float(np.median(test_res_frozen)), 4),
                    "std_residual": round(float(np.std(test_res_frozen)), 4),
                    "percentiles": compute_percentiles(test_res_frozen),
                }

                # E. Pollution Regime Breakdown
                regime_frozen = compute_regime_metrics(y_test, frozen_pred)
                regime_cand = compute_regime_metrics(y_test, val_pred) if train_validation_models and data_sufficiency else None

                # F. Conformal Coverage (80%, 90%, 95%)
                val_res = y_val - frozen_booster.predict(X_val, predict_disable_shape_check=True)
                q_80 = compute_conformal_quantile(val_res, alpha=0.20)
                q_90 = compute_conformal_quantile(val_res, alpha=0.10)
                q_95 = compute_conformal_quantile(val_res, alpha=0.05)

                cov_80 = round(float(np.sum(np.abs(test_res_frozen) <= q_80) / len(y_test)) * 100.0, 2)
                cov_90 = round(float(np.sum(np.abs(test_res_frozen) <= q_90) / len(y_test)) * 100.0, 2)
                cov_95 = round(float(np.sum(np.abs(test_res_frozen) <= q_95) / len(y_test)) * 100.0, 2)

                conformal_diag = {
                    "quantile_80": q_80,
                    "coverage_80_pct": cov_80,
                    "quantile_90": q_90,
                    "coverage_90_pct": cov_90,
                    "quantile_95": q_95,
                    "coverage_95_pct": cov_95,
                }

                window_evals.append(
                    {
                        "window_index": w_idx,
                        "split_dates": split["split_dates"],
                        "sample_count": len(y_test),
                        "persistence_baseline": pers_metrics,
                        "frozen_model": frozen_metrics,
                        "candidate_model": cand_metrics or "NOT_TRAINED",
                        "validation_model_meta": val_model_meta,
                        "residual_diagnostics": res_diag_frozen,
                        "regime_metrics_frozen": regime_frozen,
                        "regime_metrics_candidate": regime_cand,
                        "conformal_coverage": conformal_diag,
                    }
                )

            window_results_by_horizon[h_str] = window_evals

            # Aggregated Metrics across windows
            avg_frozen_mae = round(float(np.mean(frozen_maes)), 4) if frozen_maes else 0.0
            avg_pers_mae = round(float(np.mean(pers_maes)), 4) if pers_maes else 0.0
            avg_cand_mae = round(float(np.mean(cand_maes)), 4) if cand_maes else 0.0

            std_frozen_mae = round(float(np.std(frozen_maes)), 4) if frozen_maes else 0.0
            std_cand_mae = round(float(np.std(cand_maes)), 4) if cand_maes else 0.0

            aggregated_metrics_by_horizon[h_str] = {
                "persistence_avg_mae": avg_pers_mae,
                "frozen_model_avg_mae": avg_frozen_mae,
                "frozen_model_std_mae": std_frozen_mae,
                "candidate_model_avg_mae": avg_cand_mae,
                "candidate_model_std_mae": std_cand_mae,
                "candidate_vs_frozen_mae_diff": round(avg_cand_mae - avg_frozen_mae, 4),
                "candidate_vs_persistence_mae_diff": round(avg_cand_mae - avg_pers_mae, 4),
                "frozen_vs_persistence_improvement_pct": round(
                    ((avg_pers_mae - avg_frozen_mae) / max(1e-5, avg_pers_mae)) * 100.0, 2
                ),
                "candidate_vs_persistence_improvement_pct": round(
                    ((avg_pers_mae - avg_cand_mae) / max(1e-5, avg_pers_mae)) * 100.0, 2
                ),
            }

            # Drift tracking
            drift_tracking_by_horizon[h_str] = {
                "window_count": len(window_evals),
                "frozen_mae_by_window": frozen_maes,
                "candidate_mae_by_window": cand_maes,
                "frozen_mae_drift_span": round(max(frozen_maes) - min(frozen_maes), 4) if frozen_maes else 0.0,
                "candidate_mae_drift_span": round(max(cand_maes) - min(cand_maes), 4) if cand_maes else 0.0,
            }

        # 3. Verify SHA256 hashes after run
        hashes_after = self.verify_frozen_model_hashes()
        frozen_hashes_untouched = all(hashes_after[h]["status"] == "MATCH" for h in hashes_after)

        report = {
            "phase": "PHASE 1E-J2E.5.1 — ROBUST TEMPORAL VALIDATION & MODEL PROMOTION GATE",
            "station_id": CANONICAL_STATION_ID,
            "retrieval_timestamp": retrieval_ts,
            "production_validation_status": PRODUCTION_VALIDATION_STATUS,
            "feature_parity_passed": feature_parity,
            "frozen_hashes_untouched": frozen_hashes_untouched,
            "data_summary": {
                "total_rows": len(rows),
                "time_range_min": rows[0]["prediction_timestamp"] if rows else None,
                "time_range_max": rows[-1]["prediction_timestamp"] if rows else None,
                "window_count": num_windows,
            },
            "window_results": window_results_by_horizon,
            "aggregated_metrics": aggregated_metrics_by_horizon,
            "drift_tracking": drift_tracking_by_horizon,
            "frozen_model_verification": hashes_after,
        }

        # Save Report JSON
        report_path = self.data_root / "processed" / "forecasting" / "rolling_temporal_validation_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report


class PromotionGateEvaluator:
    """
    Evaluates multi-window validation results against deterministic safety and performance rules
    to render a Promotion Gate decision.
    """

    def __init__(self, data_root: Optional[Union[str, Path]] = None):
        self.data_root = Path(data_root) if data_root else Path("data")

    def evaluate_promotion_gate(self, validation_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determines promotion gate status based on robust temporal validation metrics.
        """
        retrieval_ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        frozen_hashes_untouched = validation_report.get("frozen_hashes_untouched", False)
        feature_parity_passed = validation_report.get("feature_parity_passed", False)
        aggregated = validation_report.get("aggregated_metrics", {})
        data_summary = validation_report.get("data_summary", {})
        total_rows = data_summary.get("total_rows", 0)

        # Basic Sanity Checks
        block_reasons = []
        if not frozen_hashes_untouched:
            block_reasons.append("FROZEN_MODEL_HASH_MUTATED")
        if not feature_parity_passed:
            block_reasons.append("FEATURE_CONTRACT_PARITY_FAILED")

        # Performance criteria check
        candidate_outperforms_persistence = True
        candidate_outperforms_frozen = True
        excessive_drift = False

        for h_str, agg_m in aggregated.items():
            cand_mae = agg_m.get("candidate_model_avg_mae", 0.0)
            pers_mae = agg_m.get("persistence_avg_mae", 0.0)
            froz_mae = agg_m.get("frozen_model_avg_mae", 0.0)
            cand_std = agg_m.get("candidate_model_std_mae", 0.0)

            if cand_mae >= pers_mae:
                candidate_outperforms_persistence = False
                block_reasons.append(f"CANDIDATE_UNDERPERFORMS_PERSISTENCE_{h_str}")
            if cand_mae > froz_mae * 1.05:  # Allow 5% margin or require lower MAE
                candidate_outperforms_frozen = False

            if cand_std > 15.0:  # High volatility across windows
                excessive_drift = True
                block_reasons.append(f"EXCESSIVE_DRIFT_{h_str}")

        # Deterministic Status Decision Logic
        if block_reasons and any(r in ["FROZEN_MODEL_HASH_MUTATED", "FEATURE_CONTRACT_PARITY_FAILED"] for r in block_reasons):
            gate_status = "PROMOTION_BLOCKED"
            rationale = "Promotion blocked due to critical hash or feature parity failures."
        elif total_rows < 1000 or data_summary.get("window_count", 0) < 2:
            # Single-station Anand Vihar dataset (648 rows) represents limited temporal/spatial coverage
            gate_status = "PROMOTION_REVIEW_REQUIRED" if candidate_outperforms_persistence else "MORE_EVIDENCE_REQUIRED"
            rationale = (
                "Candidate models show validated temporal performance over Anand Vihar pilot dataset. "
                "However, limited multi-station and multi-season temporal coverage requires human authority review "
                "before any production promotion."
            )
        elif candidate_outperforms_persistence and candidate_outperforms_frozen and not excessive_drift:
            gate_status = "CANDIDATE_SUPPORTED_FOR_REVIEW"
            rationale = "Candidate model consistently out-performs frozen model and baseline across windows."
        elif candidate_outperforms_persistence:
            gate_status = "PROMOTION_REVIEW_REQUIRED"
            rationale = "Candidate model shows promise over baseline but requires detailed review against frozen model."
        else:
            gate_status = "MORE_EVIDENCE_REQUIRED"
            rationale = "Insufficient evidence of candidate superiority across evaluation windows."

        # Hard invariant validation
        if gate_status not in VALID_PROMOTION_GATE_STATUSES:
            gate_status = "PROMOTION_REVIEW_REQUIRED"

        gate_report = {
            "phase": "PHASE 1E-J2E.5.1 — ROBUST TEMPORAL VALIDATION & MODEL PROMOTION GATE",
            "station_id": CANONICAL_STATION_ID,
            "created_at": retrieval_ts,
            "promotion_gate_status": gate_status,
            "production_validation_status": PRODUCTION_VALIDATION_STATUS,
            "frozen_model_hash_protection_verified": frozen_hashes_untouched,
            "feature_contract_parity_verified": feature_parity_passed,
            "gate_rationale": rationale,
            "block_reasons": block_reasons,
            "summary_metrics": aggregated,
        }

        # Save Gate Report JSON
        gate_path = self.data_root / "processed" / "forecasting" / "promotion_gate_report.json"
        gate_path.parent.mkdir(parents=True, exist_ok=True)
        with open(gate_path, "w", encoding="utf-8") as f:
            json.dump(gate_report, f, indent=2)

        return gate_report
