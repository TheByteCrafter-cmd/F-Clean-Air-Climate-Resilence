"""
VayuDrishti — Forecasting Dataset Builder

Orchestrates offline loading, timestamp normalization, feature engineering, target horizon
generation, quality validation, readiness assessment, and artifact persistence.
"""

import csv
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ml.src.forecasting.config import ForecastingConfig
from ml.src.forecasting.feature_engineering import (
    align_weather_features,
    compute_cyclic_time_features,
    compute_lag_and_rolling_features,
)
from ml.src.forecasting.readiness import ForecastingReadinessAssessor
from ml.src.forecasting.target_builder import compute_target_horizons
from ml.src.forecasting.timestamp_utils import (
    parse_utc_timestamp,
    sort_and_deduplicate_records,
)
from ml.src.forecasting.validation import (
    ForecastingDataValidator,
    verify_zero_temporal_leakage,
)

logger = logging.getLogger(__name__)


class ForecastingDatasetBuilder:
    """Orchestrates dataset construction for short-term air quality forecasting."""

    def __init__(
        self,
        data_root: Optional[Union[str, Path]] = None,
        config: Optional[ForecastingConfig] = None,
    ):
        self.config = config or ForecastingConfig()
        self.data_root = Path(data_root) if data_root else Path(os.getcwd()) / "data"
        self.processed_dir = self.data_root / "processed"
        self.forecasting_dir = self.processed_dir / "forecasting"
        self.forecasting_dir.mkdir(parents=True, exist_ok=True)

        self.validator = ForecastingDataValidator(self.config)
        self.readiness_assessor = ForecastingReadinessAssessor(self.config)

    def load_openaq_records(self, provenance_files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Scans data/processed/ for OpenAQ observation JSONL artifacts."""
        records: List[Dict[str, Any]] = []
        if not self.processed_dir.exists():
            return records

        for f_path in self.processed_dir.glob("openaq_*.jsonl"):
            if provenance_files is not None:
                rel_path = str(f_path.relative_to(self.data_root.parent)).replace("\\", "/")
                if rel_path not in provenance_files:
                    provenance_files.append(rel_path)
            try:
                with open(f_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            rec = json.loads(line_str)
                            rec["source_file"] = str(f_path)
                            records.append(rec)
            except Exception as e:
                logger.warning(f"Failed to read OpenAQ file {f_path}: {e}")

        return records

    def load_weather_records(self, provenance_files: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Scans data/processed/ for Open-Meteo weather JSONL artifacts."""
        records: List[Dict[str, Any]] = []
        if not self.processed_dir.exists():
            return records

        for f_path in self.processed_dir.glob("open_meteo_*.jsonl"):
            if provenance_files is not None:
                rel_path = str(f_path.relative_to(self.data_root.parent)).replace("\\", "/")
                if rel_path not in provenance_files:
                    provenance_files.append(rel_path)
            try:
                with open(f_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if line_str:
                            rec = json.loads(line_str)
                            records.append(rec)
            except Exception as e:
                logger.warning(f"Failed to read weather file {f_path}: {e}")

        return records

    def build_dataset_rows(
        self,
        openaq_records: List[Dict[str, Any]],
        weather_records: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Pure deterministic dataset construction function.
        Groups observations by station, computes features <= t, and shifts target horizons > t.
        """
        weather = weather_records or []
        sorted_records = sort_and_deduplicate_records(openaq_records)

        if not sorted_records:
            return []

        # Group observations by station_id
        station_groups: Dict[str, List[Dict[str, Any]]] = {}
        for r in sorted_records:
            st_id = r["station_id"]
            if st_id not in station_groups:
                station_groups[st_id] = []
            station_groups[st_id].append(r)

        dataset_rows: List[Dict[str, Any]] = []

        for st_id, st_obs_list in station_groups.items():
            # Group records for this station by unique prediction timestamp
            ts_map: Dict[datetime, Dict[str, Any]] = {}
            for r in st_obs_list:
                dt = r.get("parsed_timestamp") or parse_utc_timestamp(r["timestamp"])
                if dt not in ts_map:
                    ts_map[dt] = {"timestamp": dt, "pm25": None, "pm10": None, "meta": r}
                pol = str(r.get("pollutant", "PM2.5")).upper().replace(".", "").replace(" ", "")
                if pol in ["PM25", "PM2.5"]:
                    ts_map[dt]["pm25"] = float(r["value"])
                elif pol == "PM10":
                    ts_map[dt]["pm10"] = float(r["value"])

            sorted_dts = sorted(list(ts_map.keys()))

            # Prepare historical PM2.5 observation list for lag/rolling calculations
            pm25_history: List[Dict[str, Any]] = []
            for dt in sorted_dts:
                item = ts_map[dt]
                if item["pm25"] is not None:
                    pm25_history.append({
                        "station_id": st_id,
                        "timestamp": item["timestamp"].isoformat().replace("+00:00", "Z"),
                        "parsed_timestamp": item["timestamp"],
                        "pollutant": "PM2.5",
                        "value": item["pm25"]
                    })

            for curr_dt in sorted_dts:
                curr_item = ts_map[curr_dt]
                curr_iso = curr_dt.isoformat().replace("+00:00", "Z")
                meta = curr_item["meta"]

                lat = meta.get("latitude") or (meta.get("location", {}).get("latitude") if isinstance(meta.get("location"), dict) else None)
                lon = meta.get("longitude") or (meta.get("location", {}).get("longitude") if isinstance(meta.get("location"), dict) else None)
                addr = meta.get("address") or (meta.get("location", {}).get("address") if isinstance(meta.get("location"), dict) else None)

                if lat is None or lon is None:
                    continue

                lat = float(lat)
                lon = float(lon)

                row: Dict[str, Any] = {
                    "station_id": st_id,
                    "prediction_timestamp": curr_iso,
                    "latitude": round(lat, 4),
                    "longitude": round(lon, 4),
                    "station_name": str(addr) if addr else st_id,
                    "pm25_t0": round(curr_item["pm25"], 2) if curr_item["pm25"] is not None else None,
                    "pm10_t0": round(curr_item["pm10"], 2) if curr_item["pm10"] is not None else None,
                }

                # 1. Historical PM2.5 Lags & Rolling Statistics (<= t)
                hist_idx = next((i for i, h in enumerate(pm25_history) if h["parsed_timestamp"] == curr_dt), None)
                if hist_idx is not None:
                    lags_and_rolls = compute_lag_and_rolling_features(pm25_history, hist_idx, self.config)
                    row.update(lags_and_rolls)
                else:
                    for lag_h in self.config.lag_hours:
                        row[f"pm25_lag_{lag_h}h"] = None
                    for win_h in self.config.rolling_windows_hours:
                        row[f"pm25_roll_mean_{win_h}h"] = None
                        row[f"pm25_roll_median_{win_h}h"] = None

                # 2. Weather Feature Alignment (<= t)
                wx_feats = align_weather_features(curr_dt, lat, lon, weather, self.config)
                row.update(wx_feats)

                # 3. Cyclic Time Features
                cyclic_feats = compute_cyclic_time_features(curr_dt)
                row.update(cyclic_feats)

                # 4. Target Horizons (+1h, +3h, +6h)
                targets = compute_target_horizons(st_obs_list, curr_dt, self.config)
                row.update(targets)

                dataset_rows.append(row)

        return dataset_rows

    def build_and_save(
        self,
        custom_openaq_records: Optional[List[Dict[str, Any]]] = None,
        custom_weather_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes full dataset construction pipeline, runs validation and readiness assessment,
        and persists output artifacts under data/processed/forecasting/.
        """
        provenance_files: List[str] = []

        openaq = (
            custom_openaq_records
            if custom_openaq_records is not None
            else self.load_openaq_records(provenance_files)
        )
        weather = (
            custom_weather_records
            if custom_weather_records is not None
            else self.load_weather_records(provenance_files)
        )

        dataset_rows = self.build_dataset_rows(openaq, weather)

        # Execute 14 Quality Checks
        quality_report = self.validator.validate_dataset_rows(dataset_rows)

        # Execute 7 Automated Leakage Tests
        leakage_report = verify_zero_temporal_leakage(
            builder_fn=lambda o, w: self.build_dataset_rows(o, w),
            test_openaq_records=openaq if openaq else [],
            test_weather_records=weather,
        )

        # Assess Readiness
        readiness_report = self.readiness_assessor.assess_readiness(
            records=openaq,
            dataset_rows=dataset_rows,
            weather_records=weather,
            leakage_results=leakage_report,
        )

        # Save Artifacts
        csv_path, manifest_path, quality_path, readiness_path = self.save_artifacts(
            dataset_rows=dataset_rows,
            quality_report=quality_report,
            readiness_report=readiness_report,
            leakage_report=leakage_report,
            provenance_files=provenance_files,
        )

        return {
            "dataset_rows_count": len(dataset_rows),
            "dataset_rows": dataset_rows,
            "quality_report": quality_report,
            "leakage_report": leakage_report,
            "readiness_report": readiness_report,
            "artifacts": {
                "csv_path": str(csv_path),
                "manifest_path": str(manifest_path),
                "quality_path": str(quality_path),
                "readiness_path": str(readiness_path),
            },
        }

    def save_artifacts(
        self,
        dataset_rows: List[Dict[str, Any]],
        quality_report: Dict[str, Any],
        readiness_report: Dict[str, Any],
        leakage_report: Dict[str, Any],
        provenance_files: List[str],
    ) -> Tuple[Path, Path, Path, Path]:
        """Persists CSV dataset, manifest JSON, quality JSON, and readiness JSON artifacts."""
        csv_path = self.forecasting_dir / "forecast_dataset.csv"
        manifest_path = self.forecasting_dir / "forecast_dataset_manifest.json"
        quality_path = self.forecasting_dir / "forecast_data_quality.json"
        readiness_path = self.forecasting_dir / "forecast_data_readiness.json"

        # 1. Write CSV dataset
        if dataset_rows:
            fieldnames = list(dataset_rows[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(dataset_rows)
        else:
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                f.write("station_id,prediction_timestamp,latitude,longitude,pm25_t0,pm25_t_plus_1h,pm25_t_plus_3h,pm25_t_plus_6h\n")

        # 2. Write Manifest JSON
        now_utc = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        manifest = {
            "dataset_version": "1.0-provisional",
            "created_at": now_utc,
            "input_artifact_references": list(dict.fromkeys(provenance_files)),
            "row_count": len(dataset_rows),
            "station_count": readiness_report["metrics"].get("total_stations", 0),
            "time_range_hours": readiness_report["metrics"].get("time_range_hours", 0.0),
            "target_horizons": self.config.target_horizons_hours,
            "feature_groups": [
                "historical_pm25_lags",
                "rolling_statistics",
                "aligned_open_meteo_weather",
                "cyclic_temporal_features",
                "station_metadata",
            ],
            "missingness_summary": quality_report.get("missing_features", {}),
            "readiness_status": readiness_report["readiness_status"],
            "training_ready": readiness_report["training_ready"],
            "leakage_test_passed": leakage_report.get("leakage_passed", False),
            "schema_version": "1.0",
        }

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # 3. Write Data Quality JSON
        with open(quality_path, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2)

        # 4. Write Data Readiness JSON
        with open(readiness_path, "w", encoding="utf-8") as f:
            json.dump(readiness_report, f, indent=2)

        return csv_path, manifest_path, quality_path, readiness_path
