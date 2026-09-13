#!/usr/bin/env python3
"""
VayuDrishti - Geospatial Context Ingestion CLI
Ingests OpenStreetMap vectors and municipal administrative ward boundaries.
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.ingestion.geospatial_pipeline import GeospatialPipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_geospatial")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest OpenStreetMap infrastructure and municipal ward boundaries for VayuDrishti."
    )
    parser.add_argument(
        "--osm-live",
        action="store_true",
        help="Execute live query against OpenStreetMap Overpass API for Delhi pilot area.",
    )
    parser.add_argument(
        "--osm-fixture",
        type=str,
        default=None,
        help="Path to offline OSM JSON fixture for pipeline replay.",
    )
    parser.add_argument(
        "--wards-fetch",
        type=str,
        choices=["delhi", "bengaluru", "all"],
        default=None,
        help="Fetch live municipal ward boundaries from DataMeet CDN for specified city.",
    )
    parser.add_argument(
        "--wards-fixture",
        type=str,
        default=None,
        help="Path to offline wards GeoJSON fixture for pipeline replay.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed/geospatial",
        help="Directory to save processed GeoJSON feature collections.",
    )
    parser.add_argument(
        "--raw-dir",
        type=str,
        default="data/raw",
        help="Directory to store preserved raw responses.",
    )

    args = parser.parse_args()

    pipeline = GeospatialPipeline(
        raw_dir=Path(args.raw_dir),
        processed_dir=Path(args.output_dir),
    )

    actions_run = 0

    # 1. OSM Ingestion
    if args.osm_live or args.osm_fixture:
        mode = "fixture" if args.osm_fixture else "live"
        fixture_p = Path(args.osm_fixture) if args.osm_fixture else None
        logger.info(f"Starting OSM Ingestion (mode={mode})")
        try:
            res_osm = pipeline.run_osm_pipeline(mode=mode, fixture_path=fixture_p)
            logger.info("=== OSM Ingestion Results ===")
            logger.info(f"Raw Elements: {res_osm['raw_count']}")
            logger.info(f"Valid Features: {res_osm['valid_count']} (Roads: {res_osm['roads_count']}, Industrial: {res_osm['industrial_count']}, Sensitive: {res_osm['receptors_count']})")
            logger.info(f"Rejected Elements: {res_osm['rejected_count']}")
            logger.info(f"Artifacts exported to: {args.output_dir}")
            actions_run += 1
        except Exception as e:
            logger.error(f"OSM ingestion failed: {e}", exc_info=True)
            sys.exit(1)

    # 2. Municipal Wards Ingestion
    if args.wards_fetch or args.wards_fixture:
        mode = "fixture" if args.wards_fixture else "live"
        cities = ["delhi", "bengaluru"] if args.wards_fetch == "all" else ([args.wards_fetch] if args.wards_fetch else ["delhi"])
        fixture_p = Path(args.wards_fixture) if args.wards_fixture else None

        for c in cities:
            logger.info(f"Starting Municipal Wards Ingestion for {c.title()} (mode={mode})")
            try:
                res_w = pipeline.run_wards_pipeline(city=c, mode=mode, fixture_path=fixture_p)
                logger.info(f"=== Ward Ingestion Results ({c.title()}) ===")
                logger.info(f"Raw Features: {res_w['raw_count']}")
                logger.info(f"Valid Wards: {res_w['valid_count']}")
                logger.info(f"Rejected: {res_w['rejected_count']}")
                logger.info(f"Artifact saved to: {res_w['output_path']}")
                actions_run += 1
            except Exception as e:
                logger.error(f"Ward boundary ingestion failed for {c}: {e}", exc_info=True)
                sys.exit(1)

    if actions_run == 0:
        logger.warning(
            "No ingestion actions requested. Use --osm-live, --osm-fixture, --wards-fetch, or --wards-fixture."
        )
        parser.print_help()


if __name__ == "__main__":
    main()
