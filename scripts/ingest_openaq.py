"""
VayuDrishti - OpenAQ Ingestion CLI Entry Point
Usage:
    python scripts/ingest_openaq.py [--fixture tests/fixtures/openaq_delhi_sample.json] [--live] [--limit 3]
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path so backend imports work seamlessly
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

from backend.ingestion.pipeline import OpenAQIngestionPipeline
from backend.ingestion.exceptions import MissingCredentialError, OpenAQError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingest_openaq")


def main() -> int:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="VayuDrishti - OpenAQ v3 Air Quality Ingestion Pipeline"
    )
    parser.add_argument(
        "--fixture",
        type=str,
        default=None,
        help="Path to local sanitized OpenAQ JSON fixture file.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Force live fetch against OpenAQ v3 API (requires OPENAQ_API_KEY).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=3,
        help="Maximum locations to query for live Delhi pilot sample (default: 3).",
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default=str(ROOT_DIR / "data" / "raw"),
        help="Directory to store raw API response snapshots.",
    )
    parser.add_argument(
        "--processed-dir",
        type=str,
        default=str(ROOT_DIR / "data" / "processed"),
        help="Directory to store canonical processed observations and quality reports.",
    )

    args = parser.parse_args()

    api_key = os.getenv("OPENAQ_API_KEY")
    default_fixture = ROOT_DIR / "tests" / "fixtures" / "openaq_delhi_sample.json"

    # Determine execution mode
    fixture_to_use = None
    if args.fixture:
        fixture_to_use = args.fixture
    elif args.live:
        if not api_key or not api_key.strip():
            logger.error(
                "Live OpenAQ ingestion failed: OPENAQ_API_KEY is not configured in .env or environment. "
                "Set your API key or execute with --fixture <path>."
            )
            return 2
    else:
        # Auto-detect: if no key is present, fallback gracefully to the sanitized fixture
        if not api_key or not api_key.strip():
            if default_fixture.exists():
                logger.info(
                    "OPENAQ_API_KEY is not configured. Falling back to sanitized offline fixture "
                    f"at: {default_fixture}"
                )
                fixture_to_use = str(default_fixture)
            else:
                logger.warning("OPENAQ_API_KEY is absent and default fixture not found.")

    pipeline = OpenAQIngestionPipeline(
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
    )

    logger.info("=" * 60)
    logger.info("Starting VayuDrishti OpenAQ Ingestion Run")
    logger.info(f"Target: Delhi NCR Pilot Corridors")
    logger.info(f"Mode: {'Fixture (' + str(fixture_to_use) + ')' if fixture_to_use else 'Live OpenAQ v3'}")
    logger.info("=" * 60)

    try:
        summary = pipeline.run(
            fixture_path=fixture_to_use,
            location_limit=args.limit,
            run_label="delhi",
        )
    except Exception as e:
        logger.error(f"Fatal error during ingestion run: {e}", exc_info=True)
        return 1

    if summary.get("status") == "skipped":
        logger.info(f"Ingestion skipped: {summary.get('message')}")
        return 0

    metrics = summary.get("metrics", {})
    logger.info("-" * 60)
    logger.info("INGESTION COMPLETED SUCCESSFULLY")
    logger.info(f"Run ID:            {summary.get('run_id')}")
    logger.info(f"Records Fetched:   {metrics.get('records_fetched')}")
    logger.info(f"Records Valid:     {metrics.get('records_valid')}")
    logger.info(f"Records Invalid:   {metrics.get('records_invalid')}")
    logger.info(f"Duplicates Skipped:{metrics.get('records_duplicate')}")
    logger.info(f"Pass Rate:         {metrics.get('pass_rate_percent')}%")
    logger.info(f"Raw Snapshot:      {summary.get('raw_snapshot_path')}")
    logger.info(f"Processed JSONL:   {summary.get('processed_output_path')}")
    logger.info(f"Report (JSON):     {summary.get('validation_report_json')}")
    logger.info(f"Report (Markdown): {summary.get('validation_report_md')}")
    logger.info("-" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
