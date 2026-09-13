"""
VayuDrishti - NASA FIRMS Active Fire Ingestion CLI
Command-line utility for controlled ingestion of NASA FIRMS thermal anomaly data.

Usage:
  # Ingest from offline test fixture:
  python scripts/ingest_firms.py --fixture tests/fixtures/firms_delhi_sample.csv

  # Controlled live retrieval from NASA FIRMS regional feed (Delhi NCR bounding box):
  python scripts/ingest_firms.py --live

  # Unfiltered regional ingestion (all South Asia):
  python scripts/ingest_firms.py --live --all-regions
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.ingestion import (
    DELHI_NCR_BBOX,
    FIRMSClient,
    FIRMSIngestionPipeline,
    FIRMSNormalizer,
    FIRMSValidator,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_firms")


def parse_bbox(bbox_str: str) -> dict[str, float]:
    """Parse lat_min,lat_max,lon_min,lon_max string into bbox dictionary."""
    parts = [float(p.strip()) for p in bbox_str.split(",")]
    if len(parts) != 4:
        raise ValueError("Bounding box must contain exactly 4 comma-separated values: lat_min,lat_max,lon_min,lon_max")
    return {
        "lat_min": parts[0],
        "lat_max": parts[1],
        "lon_min": parts[2],
        "lon_max": parts[3],
    }


def main():
    parser = argparse.ArgumentParser(
        description="VayuDrishti - NASA FIRMS Active Fire Ingestion Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--live",
        action="store_true",
        help="Execute live retrieval from NASA FIRMS regional 24h CSV stream",
    )
    group.add_argument(
        "--fixture",
        type=str,
        help="Path to local CSV fixture file for offline processing",
    )

    parser.add_argument(
        "--bbox",
        type=str,
        default=None,
        help="Spatial bounding box filter: lat_min,lat_max,lon_min,lon_max (default: Delhi NCR 28.0,29.5,76.5,78.0)",
    )
    parser.add_argument(
        "--all-regions",
        action="store_true",
        help="Disable bounding box filter and retain all South Asia detections",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed",
        help="Directory to store processed JSONL and quality reports",
    )
    parser.add_argument(
        "--no-save-raw",
        action="store_true",
        help="Do not save raw CSV snapshot in data/raw",
    )

    args = parser.parse_args()

    # Determine bounding box
    if args.all_regions:
        bbox = None
        prefix = "firms_south_asia"
    elif args.bbox:
        bbox = parse_bbox(args.bbox)
        prefix = "firms_custom"
    else:
        bbox = DELHI_NCR_BBOX
        prefix = "firms_delhi"

    pipeline = FIRMSIngestionPipeline(
        raw_dir=PROJECT_ROOT / "data" / "raw",
        processed_dir=PROJECT_ROOT / args.output_dir,
    )

    print("=" * 70)
    print(" VAYUDRISHTI - NASA FIRMS THERMAL ANOMALY INGESTION ENGINE")
    print("=" * 70)

    try:
        if args.fixture:
            fixture_path = Path(args.fixture)
            print(f"Source Mode: Local Offline Fixture ({fixture_path})")
            signals, report, files = pipeline.run_pipeline(
                fixture_path=fixture_path,
                bbox=bbox,
                save_raw=not args.no_save_raw,
                output_prefix=prefix,
            )
        else:
            print("Source Mode: NASA FIRMS South Asia 24h Regional CSV Stream (LIVE)")
            signals, report, files = pipeline.run_pipeline(
                live=True,
                bbox=bbox,
                save_raw=not args.no_save_raw,
                output_prefix=prefix,
            )

        print("\n--- INGESTION AUDIT SUMMARY ---")
        print(f"Product:               {report.product}")
        print(f"Total Rows Received:   {report.total_rows_received}")
        print(f"Rows Retained:         {report.rows_retained} (Valid and In-Scope)")
        print(f"Rows Rejected:         {report.rows_rejected}")
        print(f"Duplicates Dropped:    {report.duplicate_count}")
        print(f"Out of BBox:           {report.out_of_bounds_count}")
        print(f"Validity Rate:         {report.validity_rate_pct}%")

        if report.geographic_extent:
            print(f"Geographic Extent:     Lat [{report.geographic_extent['min_lat']:.4f}, {report.geographic_extent['max_lat']:.4f}], Lon [{report.geographic_extent['min_lon']:.4f}, {report.geographic_extent['max_lon']:.4f}]")

        if report.acquisition_time_range:
            print(f"Time Window (UTC):     {report.acquisition_time_range['min_utc']} -> {report.acquisition_time_range['max_utc']}")

        if report.frp_summary:
            print(f"FRP Range:             {report.frp_summary['min_mw']} MW to {report.frp_summary['max_mw']} MW (Mean: {report.frp_summary['mean_mw']} MW)")

        if report.satellites_represented:
            print(f"Satellites:            {dict(report.satellites_represented)}")

        if report.confidence_distribution:
            print(f"Confidence:            {dict(report.confidence_distribution)}")

        print("\n--- GENERATED ARTIFACTS ---")
        for key, path in files.items():
            print(f"[{key}]: {path}")

        print("\n[SUCCESS] NASA FIRMS ingestion completed successfully.")
        return 0

    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}", exc_info=True)
        print(f"\n[ERROR] FIRMS Ingestion failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
