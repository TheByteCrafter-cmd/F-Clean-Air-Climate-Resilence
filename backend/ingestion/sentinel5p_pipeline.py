"""
VayuDrishti - Sentinel-5P Ingestion Pipeline
Coordinates Earth Engine extraction, normalization, validation, cached artifact generation, and quality reporting.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.api.v1.schemas.satellite import Sentinel5PNO2Signal
from backend.ingestion.exceptions import GEEAuthenticationError
from backend.ingestion.sentinel5p_client import (
    DEFAULT_DELHI_ROI,
    GEE_COLLECTION_ID,
    PRIMARY_BAND,
    Sentinel5PClient,
)
from backend.ingestion.sentinel5p_normalizer import Sentinel5PNormalizer
from backend.ingestion.sentinel5p_validator import (
    Sentinel5PQualityReport,
    Sentinel5PValidator,
)

logger = logging.getLogger(__name__)


class Sentinel5PPipeline:
    """Orchestrates Sentinel-5P TROPOMI NO2 satellite data ingestion."""

    def __init__(
        self,
        client: Optional[Sentinel5PClient] = None,
        normalizer: Optional[Sentinel5PNormalizer] = None,
        validator: Optional[Sentinel5PValidator] = None,
        raw_dir: Path = Path("data/raw"),
        processed_dir: Path = Path("data/processed/satellite"),
    ):
        self.client = client or Sentinel5PClient()
        self.normalizer = normalizer or Sentinel5PNormalizer()
        self.validator = validator or Sentinel5PValidator()
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def run_pipeline(
        self,
        records: Optional[List[Dict[str, Any]]] = None,
        fixture_path: Optional[Path] = None,
        live: bool = False,
        roi: Optional[Dict[str, float]] = DEFAULT_DELHI_ROI,
        save_raw: bool = True,
        output_prefix: str = "sentinel5p_delhi_no2",
        retrieval_mode_override: Optional[str] = None,
    ) -> Tuple[List[Sentinel5PNO2Signal], Sentinel5PQualityReport, Dict[str, Path]]:
        """Execute end-to-end Sentinel-5P ingestion pipeline.
        
        Args:
            records: Optional raw record dictionaries.
            fixture_path: Optional offline fixture path.
            live: If True, attempts controlled live extraction from Google Earth Engine.
            roi: Region of Interest bounding box.
            save_raw: Whether to persist raw extraction JSON snapshot.
            output_prefix: Filename prefix for outputs.
            retrieval_mode_override: Optional label for retrieval mode.
            
        Returns:
            (retained_signals, quality_report, generated_files_dict)
        """
        retrieval_time = datetime.now(timezone.utc)
        timestamp_str = retrieval_time.strftime("%Y%m%d_%H%M%S")
        is_auth, auth_msg = self.client.check_authentication()

        raw_records: List[Dict[str, Any]] = []
        retrieval_mode = retrieval_mode_override or "CACHED_FALLBACK"

        # 1. Acquire raw data
        if records is not None:
            raw_records = records
            retrieval_mode = retrieval_mode_override or "DIRECT_INPUT"
        elif fixture_path is not None:
            raw_records = self.client.load_fixture(fixture_path)
            retrieval_mode = retrieval_mode_override or "OFFLINE_FIXTURE"
        elif live:
            if not is_auth:
                raise GEEAuthenticationError(auth_msg)
            raw_records = self.client.extract_live(roi=roi)
            retrieval_mode = "LIVE_GEE"
        else:
            raise ValueError(
                "Sentinel5PPipeline requires either records, fixture_path, or live=True"
            )

        generated_files: Dict[str, Path] = {}

        # 2. Persist raw snapshot
        if save_raw and raw_records:
            raw_filename = f"{output_prefix}_sample_{timestamp_str}.json"
            raw_path = self.raw_dir / raw_filename
            with raw_path.open("w", encoding="utf-8") as f:
                json.dump(
                    {
                        "dataset_id": GEE_COLLECTION_ID,
                        "primary_band": PRIMARY_BAND,
                        "retrieval_time_utc": retrieval_time.isoformat(),
                        "retrieval_mode": retrieval_mode,
                        "roi": roi,
                        "sample_count": len(raw_records),
                        "observations": raw_records,
                    },
                    f,
                    indent=2,
                )
            generated_files["raw_json"] = raw_path
            logger.info(f"Saved raw Sentinel-5P snapshot: {raw_path} ({len(raw_records)} records)")

        # 3. Normalize records into canonical Sentinel5PNO2Signal objects
        norm_results = self.normalizer.normalize_dataset(
            raw_records,
            retrieved_at=retrieval_time,
            source_collection=GEE_COLLECTION_ID,
            provenance_extra={"roi": roi, "retrieval_mode": retrieval_mode},
        )

        valid_signals = [r.signal for r in norm_results if r.is_valid and r.signal is not None]
        norm_rejected_count = len(norm_results) - len(valid_signals)

        # 4. Validate, spatial-filter, cloud-screen, and deduplicate
        retained_signals, report = self.validator.validate_dataset(
            valid_signals,
            roi=roi,
            retrieval_time=retrieval_time,
            retrieval_mode=retrieval_mode,
            auth_status="ACTIVE" if is_auth else "GEE RUNTIME ACCESS NOT CONFIGURED",
        )

        # Reconcile total received count and syntax-level rejections
        report.total_samples_received = len(raw_records)
        report.samples_rejected += norm_rejected_count
        for r in norm_results:
            if not r.is_valid and r.rejection_reason:
                report.rejection_reasons[r.rejection_reason] = (
                    report.rejection_reasons.get(r.rejection_reason, 0) + 1
                )
        if report.total_samples_received > 0:
            report.validity_rate_pct = round(
                (report.samples_retained / report.total_samples_received) * 100.0, 2
            )

        # 5. Save processed JSONL
        processed_filename = f"{output_prefix}_{timestamp_str}.jsonl"
        processed_path = self.processed_dir / processed_filename
        with processed_path.open("w", encoding="utf-8") as f:
            for sig in retained_signals:
                f.write(sig.model_dump_json() + "\n")
        generated_files["processed_jsonl"] = processed_path

        # 6. Save quality reports
        report_json_path = self.processed_dir / f"{output_prefix}_report_{timestamp_str}.json"
        with report_json_path.open("w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        generated_files["report_json"] = report_json_path

        report_md_path = self.processed_dir / f"{output_prefix}_report_{timestamp_str}.md"
        report_md_path.write_text(report.to_markdown(), encoding="utf-8")
        generated_files["report_md"] = report_md_path

        logger.info(
            f"Sentinel-5P pipeline completed. Retained {len(retained_signals)} signals. "
            f"Output artifacts saved in {self.processed_dir}"
        )

        return retained_signals, report, generated_files
