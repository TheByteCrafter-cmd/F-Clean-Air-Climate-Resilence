"""
VayuDrishti - OpenAQ Ingestion Pipeline Orchestrator
Coordinates fetch, raw preservation, normalization, validation, and storage.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.api.v1.schemas.observation import EnvironmentalObservation
from backend.ingestion.exceptions import MissingCredentialError, OpenAQError
from backend.ingestion.normalizer import OpenAQNormalizer
from backend.ingestion.openaq_client import OpenAQClient
from backend.ingestion.validator import DataQualityReport, ObservationValidator

logger = logging.getLogger(__name__)


class OpenAQIngestionPipeline:
    """End-to-end Air Quality Ingestion Pipeline for OpenAQ v3."""

    def __init__(
        self,
        raw_dir: str = "data/raw",
        processed_dir: str = "data/processed",
        client: Optional[OpenAQClient] = None,
        normalizer: Optional[OpenAQNormalizer] = None,
        validator: Optional[ObservationValidator] = None,
    ):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.client = client or OpenAQClient()
        self.normalizer = normalizer or OpenAQNormalizer()
        self.validator = validator or ObservationValidator()

        # Ensure directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_raw_payload(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Guarantee that no API keys or sensitive authorization headers are persisted."""
        sanitized = json.loads(json.dumps(raw_data))
        # Remove any stray auth headers or key parameters if present
        if "metadata" in sanitized:
            sanitized["metadata"].pop("api_key", None)
            sanitized["metadata"].pop("authorization", None)
            if "query" in sanitized["metadata"]:
                sanitized["metadata"]["query"].pop("api_key", None)
        return sanitized

    def _extract_readings_from_raw(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract individual readings alongside their location metadata.
        
        Supports both:
        1. Multi-location sample envelope: {'raw_locations': [...], 'location_readings': [...]}
        2. Direct /v3/locations response: {'results': [{..., 'sensors': [...]}]}
        3. Direct /v3/locations/{id}/latest response: {'results': [...]}
        """
        extracted_pairs: List[Dict[str, Any]] = []

        # Format 1: Multi-location pipeline sample
        if "location_readings" in raw_data:
            for item in raw_data["location_readings"]:
                loc_meta = item.get("location_metadata", {})
                latest_list = item.get("latest", [])
                for reading in latest_list:
                    extracted_pairs.append({
                        "reading": reading,
                        "location_meta": loc_meta,
                    })

        # Format 2: Direct locations list with embedded sensors / latest
        elif "results" in raw_data:
            results = raw_data.get("results", [])
            for item in results:
                # If item is a Location with sensors array
                if "sensors" in item and isinstance(item["sensors"], list):
                    for sensor in item["sensors"]:
                        sensor_reading = {
                            "parameter": sensor.get("parameter"),
                            "name": sensor.get("name"),
                            "sensorsId": sensor.get("id"),
                            "locationsId": item.get("id"),
                            "coordinates": item.get("coordinates"),
                            "datetime": sensor.get("datetimeLast"),
                        }
                        # If sensor has latest reading value
                        if isinstance(sensor.get("latest"), dict):
                            sensor_reading["value"] = sensor["latest"].get("value")
                            if "datetime" in sensor["latest"]:
                                sensor_reading["datetime"] = sensor["latest"]["datetime"]
                        elif "value" in sensor:
                            sensor_reading["value"] = sensor.get("value")

                        extracted_pairs.append({
                            "reading": sensor_reading,
                            "location_meta": item,
                        })
                # If item is a direct Latest measurement
                elif "sensorsId" in item or "locationsId" in item:
                    extracted_pairs.append({
                        "reading": item,
                        "location_meta": {},
                    })

        return extracted_pairs

    def run(
        self,
        fixture_path: Optional[str] = None,
        location_limit: int = 3,
        run_label: str = "delhi",
    ) -> Dict[str, Any]:
        """Execute the complete ingestion workflow.
        
        If `fixture_path` is provided, reads recorded raw fixture (offline).
        If `fixture_path` is None:
            If OPENAQ_API_KEY is available: performs controlled live fetch.
            If OPENAQ_API_KEY is absent: skips live fetch gracefully.
        """
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        date_slug = now.strftime("%Y%m%d_%H%M%S")
        generated_at = now.isoformat()

        report = DataQualityReport(
            run_id=run_id,
            source_name="OpenAQ REST API v3",
            generated_at=generated_at,
        )

        raw_data: Dict[str, Any] = {}
        source_mode = "live"

        # 1. Acquire Data (Fixture or Live)
        if fixture_path:
            source_mode = "fixture"
            fixture_file = Path(fixture_path)
            if not fixture_file.exists():
                raise FileNotFoundError(f"Fixture file not found at: {fixture_path}")
            with open(fixture_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
            logger.info(f"Loaded {len(raw_data)} bytes from local fixture: {fixture_path}")
        else:
            if not self.client.has_credentials():
                message = "Live OpenAQ verification skipped because OPENAQ_API_KEY is not configured."
                logger.info(message)
                return {
                    "status": "skipped",
                    "reason": "missing_credentials",
                    "message": message,
                    "run_id": run_id,
                    "records_fetched": 0,
                    "records_valid": 0,
                }
            
            logger.info(f"Initiating controlled live OpenAQ v3 fetch (limit={location_limit})...")
            try:
                raw_data = self.client.fetch_delhi_sample(location_limit=location_limit)
            except MissingCredentialError as e:
                return {
                    "status": "skipped",
                    "reason": "missing_credentials",
                    "message": str(e),
                    "run_id": run_id,
                    "records_fetched": 0,
                    "records_valid": 0,
                }
            except OpenAQError as e:
                logger.error(f"Live OpenAQ ingestion failed: {e}")
                raise

        # 2. Persist Raw Snapshot
        sanitized_raw = self._sanitize_raw_payload(raw_data)
        raw_filename = f"openaq_{run_label}_sample_{date_slug}.json"
        raw_filepath = self.raw_dir / raw_filename
        with open(raw_filepath, "w", encoding="utf-8") as f:
            json.dump(sanitized_raw, f, indent=2, ensure_ascii=False)
        logger.info(f"Persisted sanitized raw snapshot: {raw_filepath}")

        # 3. Extract & Normalize Readings
        pairs = self._extract_readings_from_raw(sanitized_raw)
        report.records_fetched = len(pairs)
        report.records_parsed = len(pairs)

        valid_observations: List[EnvironmentalObservation] = []
        rejections: List[Dict[str, Any]] = []

        for pair in pairs:
            reading = pair["reading"]
            loc_meta = pair["location_meta"]

            norm_result = self.normalizer.normalize_record(
                raw_reading=reading,
                location_meta=loc_meta,
                retrieved_at=now,
            )

            if not norm_result.is_valid:
                report.record_invalid(norm_result.rejection_reason or "unknown_normalization_failure")
                rejections.append({
                    "reason": norm_result.rejection_reason,
                    "raw": reading,
                })
                continue

            # Validate normalized observation
            val_outcome = self.validator.validate(norm_result.observation, report=report)
            if val_outcome.is_valid and val_outcome.observation:
                valid_observations.append(val_outcome.observation)
            elif not val_outcome.is_valid:
                rejections.append({
                    "reason": val_outcome.rejection_reason,
                    "observation": val_outcome.observation.model_dump(mode="json") if val_outcome.observation else None,
                })

        # 4. Persist Processed Data (JSONL)
        processed_filename = f"openaq_{run_label}_observations_{date_slug}.jsonl"
        processed_filepath = self.processed_dir / processed_filename
        with open(processed_filepath, "w", encoding="utf-8") as f:
            for obs in valid_observations:
                line = json.dumps(obs.model_dump(mode="json"), ensure_ascii=False)
                f.write(line + "\n")
        logger.info(f"Persisted {len(valid_observations)} canonical observations: {processed_filepath}")

        # 5. Persist Validation Quality Report (JSON & Markdown)
        report_dict = report.to_dict()
        report_filename_json = f"openaq_{run_label}_validation_report_{date_slug}.json"
        report_filepath_json = self.processed_dir / report_filename_json
        with open(report_filepath_json, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2)

        report_filename_md = f"openaq_{run_label}_validation_report_{date_slug}.md"
        report_filepath_md = self.processed_dir / report_filename_md
        with open(report_filepath_md, "w", encoding="utf-8") as f:
            f.write(report.to_markdown())

        logger.info(f"Validation report saved to: {report_filepath_json} and {report_filepath_md}")

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
            "pollutant_counts": report.pollutant_counts,
            "station_counts": report.station_counts,
        }
