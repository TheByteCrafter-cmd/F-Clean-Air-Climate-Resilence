"""
VayuDrishti - Open-Meteo Weather Pipeline Orchestrator
Coordinates weather fetch, raw preservation, normalization, physical validation,
chronological sorting, and storage.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.api.v1.schemas.weather import WeatherObservation
from backend.ingestion.weather_client import (
    DELHI_LATITUDE,
    DELHI_LONGITUDE,
    OpenMeteoClient,
)
from backend.ingestion.weather_normalizer import OpenMeteoNormalizer
from backend.ingestion.weather_validator import (
    WeatherQualityReport,
    WeatherValidator,
)

logger = logging.getLogger(__name__)


class OpenMeteoIngestionPipeline:
    """End-to-end Meteorological Ingestion Pipeline for Open-Meteo."""

    def __init__(
        self,
        raw_dir: str = "data/raw",
        processed_dir: str = "data/processed",
        client: Optional[OpenMeteoClient] = None,
        normalizer: Optional[OpenMeteoNormalizer] = None,
        validator: Optional[WeatherValidator] = None,
    ):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.client = client or OpenMeteoClient()
        self.normalizer = normalizer or OpenMeteoNormalizer()
        self.validator = validator or WeatherValidator()

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        fixture_path: Optional[str] = None,
        latitude: float = DELHI_LATITUDE,
        longitude: float = DELHI_LONGITUDE,
        forecast_days: int = 1,
        past_days: int = 0,
        run_label: str = "delhi",
    ) -> Dict[str, Any]:
        """Execute the complete weather ingestion workflow."""
        run_id = f"run-w-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        date_slug = now.strftime("%Y%m%d_%H%M%S")
        generated_at = now.isoformat()

        report = WeatherQualityReport(
            run_id=run_id,
            source_name="Open-Meteo Forecast & Reanalysis API",
            generated_at=generated_at,
            location_summary={
                "city": f"{run_label.title()} Pilot Reference",
                "latitude": latitude,
                "longitude": longitude,
            },
        )

        raw_data: Dict[str, Any] = {}
        source_mode = "live"

        # 1. Acquire Data (Fixture or Live)
        if fixture_path:
            source_mode = "fixture"
            fixture_file = Path(fixture_path)
            if not fixture_file.exists():
                raise FileNotFoundError(f"Weather fixture file not found at: {fixture_path}")
            with open(fixture_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            logger.info(f"Loaded weather fixture from: {fixture_path}")
        else:
            logger.info(f"Initiating controlled live Open-Meteo fetch for ({latitude}, {longitude})...")
            raw_data = self.client.fetch_delhi_sample(
                forecast_days=forecast_days,
                past_days=past_days,
            )

        # 2. Persist Raw Snapshot
        raw_filename = f"open_meteo_{run_label}_sample_{date_slug}.json"
        raw_filepath = self.raw_dir / raw_filename
        with open(raw_filepath, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Persisted raw weather snapshot: {raw_filepath}")

        # 3. Normalize Response
        norm_results = self.normalizer.normalize_response(raw_data, retrieved_at=now)
        report.records_fetched = len(norm_results)
        report.records_parsed = len(norm_results)

        # Extract units for reporting
        api_data = raw_data.get("raw_response", raw_data)
        report.unit_summary = api_data.get("hourly_units", {})

        valid_observations: List[WeatherObservation] = []
        rejections: List[Dict[str, Any]] = []

        # 4. Validate & Deduplicate
        for res in norm_results:
            if not res.is_valid:
                report.record_invalid(res.rejection_reason or "unknown_normalization_error")
                rejections.append({
                    "reason": res.rejection_reason,
                    "raw": res.raw_reading,
                })
                continue

            val_outcome = self.validator.validate(res.observation, report=report)
            if val_outcome.is_valid and val_outcome.observation:
                valid_observations.append(val_outcome.observation)
            elif not val_outcome.is_valid:
                rejections.append({
                    "reason": val_outcome.rejection_reason,
                    "observation": val_outcome.observation.model_dump(mode="json") if val_outcome.observation else None,
                })

        # 5. Enforce Chronological Sorting
        valid_observations.sort(key=lambda o: o.timestamp)

        # 6. Persist Processed JSONL
        processed_filename = f"open_meteo_{run_label}_weather_{date_slug}.jsonl"
        processed_filepath = self.processed_dir / processed_filename
        with open(processed_filepath, "w", encoding="utf-8") as f:
            for obs in valid_observations:
                line = json.dumps(obs.model_dump(mode="json"), ensure_ascii=False)
                f.write(line + "\n")
        logger.info(f"Persisted {len(valid_observations)} canonical WeatherObservations: {processed_filepath}")

        # 7. Persist Quality Reports (JSON & Markdown)
        report_dict = report.to_dict()
        report_filename_json = f"open_meteo_{run_label}_weather_report_{date_slug}.json"
        report_filepath_json = self.processed_dir / report_filename_json
        with open(report_filepath_json, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)

        report_filename_md = f"open_meteo_{run_label}_weather_report_{date_slug}.md"
        report_filepath_md = self.processed_dir / report_filename_md
        with open(report_filepath_md, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())

        logger.info(f"Weather quality reports saved: {report_filepath_json} and {report_filepath_md}")

        return {
            "status": "success",
            "mode": source_mode,
            "run_id": run_id,
            "raw_snapshot_path": str(raw_filepath),
            "processed_output_path": str(processed_filepath),
            "validation_report_json": str(report_filepath_json),
            "validation_report_md": str(report_filepath_md),
            "metrics": report_dict["metrics"],
            "invalid_reasons": report.invalid_reasons,
            "missing_values": report.missing_values,
            "physical_summary": report_dict["physical_summary"],
        }
