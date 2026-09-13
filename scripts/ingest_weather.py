"""
VayuDrishti - Open-Meteo Weather Ingestion CLI Entry Point
Usage:
    python scripts/ingest_weather.py [--live] [--fixture tests/fixtures/open_meteo_delhi_sample.json] [--days 1]
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.ingestion.weather_client import DELHI_LATITUDE, DELHI_LONGITUDE
from backend.ingestion.weather_pipeline import OpenMeteoIngestionPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingest_weather")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VayuDrishti - Open-Meteo Weather Ingestion Pipeline"
    )
    parser.add_argument(
        "--fixture",
        type=str,
        default=None,
        help="Path to local sanitized Open-Meteo JSON fixture file.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Perform live fetch against Open-Meteo forecast API (default behavior).",
    )
    parser.add_argument(
        "--latitude",
        type=float,
        default=DELHI_LATITUDE,
        help=f"Target latitude (default: {DELHI_LATITUDE}).",
    )
    parser.add_argument(
        "--longitude",
        type=float,
        default=DELHI_LONGITUDE,
        help=f"Target longitude (default: {DELHI_LONGITUDE}).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of forecast days (default: 1).",
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
        help="Directory to store canonical processed weather observations and reports.",
    )

    args = parser.parse_args()

    pipeline = OpenMeteoIngestionPipeline(
        raw_dir=args.raw_dir,
        processed_dir=args.processed_dir,
    )

    mode_str = f"Fixture ({args.fixture})" if args.fixture else "Live Open-Meteo API"
    logger.info("=" * 60)
    logger.info("Starting VayuDrishti Open-Meteo Weather Ingestion Run")
    logger.info(f"Target Location: ({args.latitude}, {args.longitude})")
    logger.info(f"Execution Mode:  {mode_str}")
    logger.info("=" * 60)

    try:
        summary = pipeline.run(
            fixture_path=args.fixture,
            latitude=args.latitude,
            longitude=args.longitude,
            forecast_days=args.days,
            run_label="delhi",
        )
    except Exception as e:
        logger.error(f"Fatal error during weather ingestion run: {e}", exc_info=True)
        return 1

    metrics = summary.get("metrics", {})
    phys = summary.get("physical_summary", {})
    logger.info("-" * 60)
    logger.info("WEATHER INGESTION COMPLETED SUCCESSFULLY")
    logger.info(f"Run ID:            {summary.get('run_id')}")
    logger.info(f"Steps Fetched:     {metrics.get('records_fetched')}")
    logger.info(f"Steps Valid:       {metrics.get('records_valid')}")
    logger.info(f"Steps Invalid:     {metrics.get('records_invalid')}")
    logger.info(f"Duplicates:        {metrics.get('records_duplicate')}")
    logger.info(f"Pass Rate:         {metrics.get('pass_rate_percent')}%")
    logger.info(f"Temperature:       {phys.get('temperature_range_c')} ?C")
    logger.info(f"Humidity:          {phys.get('relative_humidity_range_pct')} %")
    logger.info(f"Wind Speed:        {phys.get('wind_speed_range_ms')} m/s")
    logger.info(f"Boundary Layer:    {phys.get('boundary_layer_height_range_m')} m")
    logger.info(f"Raw Snapshot:      {summary.get('raw_snapshot_path')}")
    logger.info(f"Processed JSONL:   {summary.get('processed_output_path')}")
    logger.info(f"Report (JSON):     {summary.get('validation_report_json')}")
    logger.info(f"Report (Markdown): {summary.get('validation_report_md')}")
    logger.info("-" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
