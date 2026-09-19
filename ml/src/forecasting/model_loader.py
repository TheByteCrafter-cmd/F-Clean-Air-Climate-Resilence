"""
VayuDrishti — Forecast Model Artifact & Metadata Loader (Phase 1E-J2E.1)

Provides discovery, loading, checksum verification, and strict metadata validation
for trained LightGBM model artifacts, manifest files, and conformal uncertainty metrics.
"""

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import lightgbm as lgb

logger = logging.getLogger(__name__)

CANONICAL_STATION_ID = "ANAND_VIHAR_8118"
SUPPORTED_STATION_ALIASES = {"ANAND_VIHAR_8118", "8118", "LOC_8118", "LOCATION_8118"}


class ModelLoaderError(Exception):
    """Base exception for model artifact loading and manifest validation errors."""
    pass


class ForecastModelLoader:
    """
    Manages loading and validation of trained LightGBM model boosters,
    model_manifest.json metadata, and uncertainty_metrics.json conformal radii.
    """

    def __init__(
        self,
        models_dir: Optional[Union[str, Path]] = None,
        data_root: Optional[Union[str, Path]] = None,
    ):
        self.root_dir = Path(os.getcwd())
        self.models_dir = Path(models_dir) if models_dir else self.root_dir / "ml" / "models" / "forecasting"
        self.data_root = Path(data_root) if data_root else self.root_dir / "data"
        self.uncertainty_path = (
            self.data_root
            / "processed"
            / "forecasting"
            / "model_evaluation"
            / "residual_analysis"
            / "uncertainty_metrics.json"
        )
        self.manifest_path = self.models_dir / "model_manifest.json"

    def load_manifest(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Loads and validates model_manifest.json.

        Enforces:
        - Manifest file existence
        - Presence of feature_list and feature_count == len(feature_list)
        - Station scope definition
        - Horizons configuration for +1h, +3h, +6h
        """
        target_path = path or self.manifest_path
        if not target_path.exists():
            raise ModelLoaderError(f"Model manifest not found at {target_path}")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            raise ModelLoaderError(f"Corrupt or unreadable model manifest at {target_path}: {str(e)}")

        # Validate required top-level keys
        required_keys = ["model_family", "scope", "feature_count", "feature_list", "models"]
        for key in required_keys:
            if key not in manifest:
                raise ModelLoaderError(f"Model manifest missing required field: '{key}'")

        feature_list = manifest["feature_list"]
        if not isinstance(feature_list, list) or len(feature_list) == 0:
            raise ModelLoaderError("Manifest 'feature_list' must be a non-empty list of feature column names.")

        calc_feature_count = len(feature_list)
        if manifest["feature_count"] != calc_feature_count:
            raise ModelLoaderError(
                f"Manifest feature count mismatch: declared {manifest['feature_count']} "
                f"vs calculated len(feature_list) {calc_feature_count}"
            )

        # Validate horizon models entries
        models_dict = manifest.get("models", {})
        for h_name in ["+1h", "+3h", "+6h"]:
            if h_name not in models_dict:
                raise ModelLoaderError(f"Model manifest missing horizon model specification for '{h_name}'")
            h_info = models_dict[h_name]
            if "artifact_file" not in h_info or "target_column" not in h_info:
                raise ModelLoaderError(f"Model manifest horizon '{h_name}' missing artifact_file or target_column")

        return manifest

    def load_models(self, dir_path: Optional[Path] = None) -> Dict[str, lgb.Booster]:
        """
        Loads LightGBM booster artifacts for +1h, +3h, and +6h forecast horizons.

        Fails safely without auto-retraining if any model file is missing or corrupt.
        """
        target_dir = dir_path or self.models_dir
        manifest = self.load_manifest(target_dir / "model_manifest.json")

        loaded_boosters: Dict[str, lgb.Booster] = {}
        for h_name, h_info in manifest["models"].items():
            model_file = h_info["artifact_file"]
            model_path = target_dir / model_file

            if not model_path.exists():
                raise ModelLoaderError(
                    f"LightGBM model artifact missing for horizon {h_name} at {model_path}. "
                    "Automatic retraining is disabled."
                )

            try:
                booster = lgb.Booster(model_file=str(model_path))
                loaded_boosters[h_name] = booster
            except Exception as e:
                raise ModelLoaderError(
                    f"Corrupt or invalid LightGBM model artifact for horizon {h_name} at {model_path}: {str(e)}"
                )

        return loaded_boosters

    def load_conformal_metrics(self, path: Optional[Path] = None) -> Dict[str, Dict[str, float]]:
        """
        Loads and validates frozen conformal uncertainty metrics from uncertainty_metrics.json.

        Verifies that radii for +1h, +3h, +6h at 80% and 90% exist, are numeric, finite, and >= 0.
        """
        target_path = path or self.uncertainty_path
        if not target_path.exists():
            raise ModelLoaderError(f"Uncertainty metrics artifact not found at {target_path}")

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                metrics_data = json.load(f)
        except Exception as e:
            raise ModelLoaderError(f"Corrupt or unreadable uncertainty metrics at {target_path}: {str(e)}")

        horizons_data = metrics_data.get("horizons", {})
        validated_radii: Dict[str, Dict[str, float]] = {}

        for h_name in ["+1h", "+3h", "+6h"]:
            if h_name not in horizons_data:
                raise ModelLoaderError(f"Uncertainty metrics missing entry for horizon '{h_name}'")

            h_metrics = horizons_data[h_name]

            q_80 = h_metrics.get("conformal_radius_80")
            q_90 = h_metrics.get("conformal_radius_90")

            if q_80 is None or not isinstance(q_80, (int, float)) or not os.path.exists if False else False:
                pass  # validation below

            for q_name, q_val in [("conformal_radius_80", q_80), ("conformal_radius_90", q_90)]:
                if q_val is None or not isinstance(q_val, (int, float)):
                    raise ModelLoaderError(f"Uncertainty metrics '{h_name}' {q_name} must be a valid float")
                if not (q_val >= 0 and not (q_val != q_val) and q_val != float("inf")):
                    raise ModelLoaderError(f"Uncertainty metrics '{h_name}' {q_name} ({q_val}) must be finite and >= 0")

            validated_radii[h_name] = {
                "radius_80": float(q_80),
                "radius_90": float(q_90),
            }

        return validated_radii

    def compute_artifact_checksums(self) -> Dict[str, str]:
        """Computes SHA256 hashes of all forecasting model artifacts and metadata files."""
        checksums = {}
        files_to_hash = [
            self.manifest_path,
            self.uncertainty_path,
            self.models_dir / "lightgbm_pm25_1h.txt",
            self.models_dir / "lightgbm_pm25_3h.txt",
            self.models_dir / "lightgbm_pm25_6h.txt",
        ]

        for path in files_to_hash:
            if path.exists():
                sha = hashlib.sha256()
                with open(path, "rb") as f:
                    while chunk := f.read(8192):
                        sha.update(chunk)
                checksums[path.name] = sha.hexdigest()

        return checksums
