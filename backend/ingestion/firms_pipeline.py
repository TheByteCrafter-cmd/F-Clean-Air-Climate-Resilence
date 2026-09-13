"""
VayuDrishti - NASA FIRMS Ingestion Pipeline
Coordinates controlled fetch, raw snapshot, normalization, validation, and quality auditing.
"""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.api.v1.schemas.satellite import FireSignal
from backend.ingestion.firms_client import FIRMSClient, DEFAULT_REGIONAL_URL
from backend.ingestion.firms_normalizer import FIRMSNormalizer
from backend.ingestion.firms_validator import (
    DELHI_NCR_BBOX,
    FIRMSQualityReport,
    FIRMSValidator,
)

logger = logging.getLogger(__name__)


class FIRMSIngestionPipeline:
    """Orchestrates NASA FIRMS thermal anomaly data ingestion."""

    def __init__(
        self,
        client: Optional[FIRMSClient] = None,
        normalizer: Optional[FIRMSNormalizer] = None,
        validator: Optional[FIRMSValidator] = None,
        raw_dir: Path = Path("data/raw"),
        processed_dir: Path = Path("data/processed"),
    ):
        self.client = client or FIRMSClient()
        self.normalizer = normalizer or FIRMSNormalizer()
        self.validator = validator or FIRMSValidator()
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)

        # Ensure target directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def run_pipeline(
        self,
        csv_content: Optional[str] = None,
        fixture_path: Optional[Path] = None,
        live: bool = False,
        bbox: Optional[Dict[str, float]] = DELHI_NCR_BBOX,
        save_raw: bool = True,
        output_prefix: str = "firms_delhi",
    ) -> Tuple[List[FireSignal], FIRMSQualityReport, Dict[str, Path]]:
        """Execute end-to-end FIRMS ingestion pipeline.
        
        Args:
            csv_content: Optional raw CSV string to process.
            fixture_path: Optional local CSV file path.
            live: If True, executes controlled live retrieval from NASA FIRMS.
            bbox: Optional bounding box dictionary to filter records (default: Delhi NCR).
            save_raw: Whether to persist raw CSV snapshot.
            output_prefix: Filename prefix for outputs.
            
        Returns:
            (retained_signals, quality_report, generated_files_dict)
        """
        retrieval_time = datetime.now(timezone.utc)
        timestamp_str = retrieval_time.strftime("%Y%m%d_%H%M%S")
        source_url = DEFAULT_REGIONAL_URL

        # 1. Acquire raw CSV text
        if csv_content is not None:
            raw_csv = csv_content
            source_url = "memory://csv_content"
        elif fixture_path is not None:
            fpath = Path(fixture_path)
            if not fpath.exists():
                raise FileNotFoundError(f"Fixture not found at: {fpath}")
            raw_csv = fpath.read_text(encoding="utf-8")
            source_url = f"file://{fpath.name}"
        elif live:
            raw_csv = self.client.fetch_regional_feed()
            source_url = self.client.regional_url
        else:
            raise ValueError(
                "FIRMSIngestionPipeline requires either csv_content, fixture_path, or live=True"
            )

        generated_files: Dict[str, Path] = {}

        # 2. Persist raw snapshot if requested
        if save_raw and raw_csv:
            raw_filename = f"{output_prefix}_sample_{timestamp_str}.csv"
            raw_path = self.raw_dir / raw_filename
            raw_path.write_text(raw_csv, encoding="utf-8")
            generated_files["raw_csv"] = raw_path
            logger.info(f"Saved raw FIRMS snapshot: {raw_path} ({len(raw_csv)} bytes)")

        # 3. Parse CSV rows
        raw_rows = self.client.parse_csv(raw_csv)
        logger.info(f"Parsed {len(raw_rows)} rows from CSV")

        # 4. Normalize rows into FireSignal models
        norm_results = self.normalizer.normalize_dataset(
            raw_rows,
            retrieved_at=retrieval_time,
            source_url=source_url,
            product_name="SUOMI_VIIRS_C2_South_Asia_24h",
        )

        valid_signals: List[FireSignal] = [
            r.signal for r in norm_results if r.is_valid and r.signal is not None
        ]
        normalization_rejected_count = len(norm_results) - len(valid_signals)
        logger.info(
            f"Normalization completed: {len(valid_signals)} valid FireSignals, {normalization_rejected_count} rejected at syntax level"
        )

        # 5. Validate, spatial-filter, and deduplicate
        retained_signals, report = self.validator.validate_dataset(
            valid_signals,
            bbox=bbox,
            retrieval_time=retrieval_time,
            product_name="SUOMI_VIIRS_C2_South_Asia_24h",
        )

        # Reconcile total received count to include syntax rejections
        report.total_rows_received = len(raw_rows)
        report.rows_rejected += normalization_rejected_count
        for r in norm_results:
            if not r.is_valid and r.rejection_reason:
                report.rejection_reasons[r.rejection_reason] = (
                    report.rejection_reasons.get(r.rejection_reason, 0) + 1
                )
        if report.total_rows_received > 0:
            report.validity_rate_pct = round(
                (report.rows_retained / report.total_rows_received) * 100.0, 2
            )

        # 6. Save processed JSONL output
        processed_filename = f"{output_prefix}_fire_{timestamp_str}.jsonl"
        processed_path = self.processed_dir / processed_filename
        with processed_path.open("w", encoding="utf-8") as f:
            for sig in retained_signals:
                f.write(sig.model_dump_json() + "\n")
        generated_files["processed_jsonl"] = processed_path

        # 7. Save quality reports (JSON and Markdown)
        report_json_path = self.processed_dir / f"{output_prefix}_fire_report_{timestamp_str}.json"
        with report_json_path.open("w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        generated_files["report_json"] = report_json_path

        report_md_path = self.processed_dir / f"{output_prefix}_fire_report_{timestamp_str}.md"
        report_md_path.write_text(report.to_markdown(), encoding="utf-8")
        generated_files["report_md"] = report_md_path

        logger.info(
            f"FIRMS pipeline completed. Retained {len(retained_signals)} signals. "
            f"Reports saved to {report_json_path} and {report_md_path}"
        )

        return retained_signals, report, generated_files
