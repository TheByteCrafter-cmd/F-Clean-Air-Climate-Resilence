"""
VayuDrishti - Sentinel-5P TROPOMI NO2 Ingestion CLI
Command-line utility for Sentinel-5P Earth Engine satellite environmental signal ingestion.

Usage:
  # Check Earth Engine catalog contract and local authentication status:
  python scripts/ingest_sentinel5p.py --catalog-check

  # Ingest from offline test fixture:
  python scripts/ingest_sentinel5p.py --offline-fixture tests/fixtures/sentinel5p_delhi_sample.json

  # Attempt controlled live extraction from Google Earth Engine (if authenticated):
  python scripts/ingest_sentinel5p.py --live
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
    DEFAULT_DELHI_ROI,
    GEE_COLLECTION_ID,
    S5P_PRIMARY_BAND,
    Sentinel5PClient,
    Sentinel5PPipeline,
)
from backend.ingestion.exceptions import GEEAuthenticationError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ingest_sentinel5p")


def parse_roi(roi_str: str) -> dict[str, float]:
    """Parse lat_min,lat_max,lon_min,lon_max string into ROI dict."""
    parts = [float(p.strip()) for p in roi_str.split(",")]
    if len(parts) != 4:
        raise ValueError("ROI must contain exactly 4 comma-separated values: lat_min,lat_max,lon_min,lon_max")
    return {
        "lat_min": parts[0],
        "lat_max": parts[1],
        "lon_min": parts[2],
        "lon_max": parts[3],
    }


def main():
    parser = argparse.ArgumentParser(
        description="VayuDrishti - Sentinel-5P TROPOMI NO2 Satellite Ingestion Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--catalog-check",
        action="store_true",
        help="Display official GEE catalog contract, bands, and verify local authentication",
    )
    group.add_argument(
        "--offline-fixture",
        type=str,
        help="Path to local JSON/JSONL fixture file for offline processing",
    )
    group.add_argument(
        "--live",
        action="store_true",
        help="Attempt controlled live extraction from Google Earth Engine",
    )

    parser.add_argument(
        "--roi",
        type=str,
        default=None,
        help="Region of Interest bounding box: lat_min,lat_max,lon_min,lon_max (default: Delhi Pilot ROI)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/processed/satellite",
        help="Directory to store processed JSONL and quality reports",
    )
    parser.add_argument(
        "--no-save-raw",
        action="store_true",
        help="Do not save raw JSON extraction snapshot in data/raw",
    )

    args = parser.parse_args()

    client = Sentinel5PClient()

    print("=" * 75)
    print(" VAYUDRISHTI - SENTINEL-5P / EARTH ENGINE NO2 SATELLITE INGESTION ENGINE")
    print("=" * 75)

    # Mode 1: Catalog Contract & Auth Check
    if args.catalog_check:
        contract = client.get_catalog_contract()
        is_auth, auth_msg = client.check_authentication()

        print("\n--- GOOGLE EARTH ENGINE CATALOG CONTRACT ---")
        print(f"Dataset ID:         {contract['dataset_id']}")
        print(f"Offline Dataset:    {contract['offline_dataset_id']}")
        print(f"Platform:           {contract['platform']} ({contract['instrument']})")
        print(f"Provider:           {contract['provider']}")
        print(f"Resolution:         ~{contract['spatial_resolution_m']}m gridded (~5.5km nadir footprint)")
        print(f"Temporal Cadence:   {contract['temporal_cadence']}")
        print(f"Primary Band:       {contract['primary_band']['name']} ({contract['primary_band']['unit']})")
        print(f"Physical Meaning:   {contract['primary_band']['physical_meaning']}")
        print(f"Valid Range:        {contract['primary_band']['valid_min']} to {contract['primary_band']['valid_max']} mol/m²")

        print("\n--- RUNTIME AUTHENTICATION AUDIT ---")
        if is_auth:
            print("[STATUS] GEE Authentication is ACTIVE.")
        else:
            print(f"[STATUS] {auth_msg}")
            print("[INFO] Offline cache fallback is fully functional and ready for pipeline operations.")

        return 0

    # Determine ROI
    roi = parse_roi(args.roi) if args.roi else DEFAULT_DELHI_ROI
    pipeline = Sentinel5PPipeline(
        client=client,
        raw_dir=PROJECT_ROOT / "data" / "raw",
        processed_dir=PROJECT_ROOT / args.output_dir,
    )

    try:
        if args.offline_fixture:
            fpath = Path(args.offline_fixture)
            print(f"Source Mode: Offline Fixture ({fpath})")
            signals, report, files = pipeline.run_pipeline(
                fixture_path=fpath,
                roi=roi,
                save_raw=not args.no_save_raw,
                output_prefix="sentinel5p_delhi_no2",
            )
        else:
            print("Source Mode: Google Earth Engine Live Extraction (LIVE)")
            signals, report, files = pipeline.run_pipeline(
                live=True,
                roi=roi,
                save_raw=not args.no_save_raw,
                output_prefix="sentinel5p_delhi_no2",
            )

        print("\n--- INGESTION AUDIT SUMMARY ---")
        print(f"Dataset ID:            {report.dataset_id}")
        print(f"Primary Band:          {report.band} ({report.unit})")
        print(f"Retrieval Mode:        {report.retrieval_mode}")
        print(f"GEE Auth Status:       {report.authentication_status}")
        print(f"Total Samples:         {report.total_samples_received}")
        print(f"Samples Retained:      {report.samples_retained} (Valid & Clear Sky)")
        print(f"Samples Rejected:      {report.samples_rejected}")
        print(f"Cloud Obscured:        {report.cloud_rejected_count}")
        print(f"Negatives Preserved:   {report.negative_values_preserved_count} (DOAS background noise)")
        print(f"Duplicates Dropped:    {report.duplicate_count}")
        print(f"Validity Rate:         {report.validity_rate_pct}%")

        if report.no2_summary_mol_m2:
            s_mol = report.no2_summary_mol_m2
            s_umol = report.no2_summary_umol_m2
            print(f"NO2 Column Min:        {s_mol['min_mol_m2']:.6f} mol/m² ({s_umol['min_umol_m2']:.2f} µmol/m²)")
            print(f"NO2 Column Max:        {s_mol['max_mol_m2']:.6f} mol/m² ({s_umol['max_umol_m2']:.2f} µmol/m²)")
            print(f"NO2 Column Mean:       {s_mol['mean_mol_m2']:.6f} mol/m² ({s_umol['mean_umol_m2']:.2f} µmol/m²)")

        if report.quality_distribution:
            print(f"Quality Tiers:         {dict(report.quality_distribution)}")

        print("\n--- GENERATED ARTIFACTS ---")
        for key, path in files.items():
            print(f"[{key}]: {path}")

        print("\n[SUCCESS] Sentinel-5P NO2 satellite ingestion completed successfully.")
        return 0

    except GEEAuthenticationError as g_err:
        print(f"\n[NOTICE] GEE Live Query Unavailable: {g_err}")
        print("[INFO] In accordance with Phase 1E-D protocol, GEE live extraction requires configured Earth Engine credentials.")
        print("[INFO] Use --offline-fixture to verify data pipeline operations using verified dataset schemas.")
        return 0
    except Exception as exc:
        logger.error(f"Ingestion failed: {exc}", exc_info=True)
        print(f"\n[ERROR] Sentinel-5P Ingestion failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
