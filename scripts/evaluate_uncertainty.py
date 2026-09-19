"""
VayuDrishti — Forecast Residual & Uncertainty Evaluation Entry Point (Phase 1E-J2D)

Executes residual analysis, Split Conformal prediction interval calibration,
and baseline reconciliation for LightGBM forecasting models.
"""

import json
import logging
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.src.forecasting.evaluator import ForecastResidualEvaluator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting VayuDrishti Phase 1E-J2D Residual & Uncertainty Evaluation Pipeline...")

    evaluator = ForecastResidualEvaluator(data_root=PROJECT_ROOT / "data")
    result = evaluator.evaluate_residuals_and_uncertainty()

    print("\n" + "=" * 65)
    print("VAYUDRISHTI PHASE 1E-J2D — RESIDUAL & UNCERTAINTY REPORT")
    print("=" * 65)
    print(f"Status: {result['status']}")
    print(f"Disclaimer: {result['conformal_guarantee_disclaimer']}\n")

    print("SPLIT CONFORMAL CALIBRATION & COVERAGE RESULTS:")
    print("-" * 65)
    print(f"{'Horizon':<8} | {'80% Radius (q)':<14} | {'Width (2q)':<10} | {'Emp Cov 80%':<12} | {'90% Radius (q)':<14} | {'Emp Cov 90%':<12}")
    print("-" * 65)

    for h_name, metrics in result["uncertainty_metrics"].items():
        q80 = metrics["conformal_radius_80"]
        w80 = metrics["average_interval_width_80"]
        cov80 = metrics["test_empirical_coverage_80_pct"]
        q90 = metrics["conformal_radius_90"]
        w90 = metrics["average_interval_width_90"]
        cov90 = metrics["test_empirical_coverage_90_pct"]
        print(f"{h_name:<8} | {q80:<14.2f} | {w80:<10.2f} | {cov80:>10.2f}% | {q90:<14.2f} | {cov90:>10.2f}%")

    print("-" * 65)
    print("\nARTIFACTS GENERATED:")
    for key, path in result["artifacts"].items():
        print(f"  - {key}: {path}")

    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()
