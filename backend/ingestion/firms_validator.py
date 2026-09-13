"""
VayuDrishti - NASA FIRMS Validator & Quality Auditor
Validates physical boundaries, spatial limits, deduplication, and generates data quality reports.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from backend.api.v1.schemas.satellite import FireSignal

logger = logging.getLogger(__name__)

# Standard pilot bounding boxes for regional spatial filtering
DELHI_NCR_BBOX: Dict[str, float] = {
    "lat_min": 28.0,
    "lat_max": 29.5,
    "lon_min": 76.5,
    "lon_max": 78.0,
}

NORTH_INDIA_BBOX: Dict[str, float] = {
    "lat_min": 26.0,
    "lat_max": 32.0,
    "lon_min": 74.0,
    "lon_max": 80.0,
}


class FIRMSValidationOutcome(BaseModel):
    """Validation outcome for an individual FireSignal."""
    is_valid: bool
    rejection_reason: Optional[str] = None
    is_duplicate: bool = False
    is_out_of_bounds: bool = False


class FIRMSQualityReport(BaseModel):
    """Auditable quality and integrity report for a FIRMS ingestion run."""
    source: str = "NASA_FIRMS"
    product: str = "SUOMI_VIIRS_C2_South_Asia_24h"
    retrieval_timestamp: Optional[datetime] = None
    total_rows_received: int = 0
    rows_retained: int = 0
    rows_rejected: int = 0
    duplicate_count: int = 0
    out_of_bounds_count: int = 0
    bounding_box_filter: Optional[Dict[str, float]] = None
    geographic_extent: Optional[Dict[str, float]] = None
    acquisition_time_range: Optional[Dict[str, str]] = None
    satellites_represented: Dict[str, int] = Field(default_factory=dict)
    confidence_distribution: Dict[str, int] = Field(default_factory=dict)
    daynight_distribution: Dict[str, int] = Field(default_factory=dict)
    frp_summary: Optional[Dict[str, float]] = None
    rejection_reasons: Dict[str, int] = Field(default_factory=dict)
    validity_rate_pct: float = 0.0

    def to_markdown(self) -> str:
        """Render report as human-readable GitHub-flavored Markdown."""
        retrieval_str = (
            self.retrieval_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            if self.retrieval_timestamp
            else "N/A"
        )
        geo_str = (
            f"Lat [{self.geographic_extent['min_lat']:.4f}, {self.geographic_extent['max_lat']:.4f}], "
            f"Lon [{self.geographic_extent['min_lon']:.4f}, {self.geographic_extent['max_lon']:.4f}]"
            if self.geographic_extent
            else "None (no valid observations)"
        )
        time_str = (
            f"{self.acquisition_time_range['min_utc']} to {self.acquisition_time_range['max_utc']}"
            if self.acquisition_time_range
            else "None"
        )
        frp_str = (
            f"Min: {self.frp_summary['min_mw']:.2f} MW, Max: {self.frp_summary['max_mw']:.2f} MW, "
            f"Mean: {self.frp_summary['mean_mw']:.2f} MW, Total: {self.frp_summary['total_mw']:.2f} MW"
            if self.frp_summary
            else "None"
        )
        bbox_str = (
            f"Lat [{self.bounding_box_filter['lat_min']}, {self.bounding_box_filter['lat_max']}], "
            f"Lon [{self.bounding_box_filter['lon_min']}, {self.bounding_box_filter['lon_max']}]"
            if self.bounding_box_filter
            else "Unfiltered (Entire Stream)"
        )

        md = f"""# NASA FIRMS Thermal Anomaly Ingestion Quality Report

**Product:** {self.product}  
**Source:** {self.source}  
**Retrieval Time:** {retrieval_str}  
**Bounding Box Filter:** {bbox_str}  

## Summary Statistics

| Metric | Value |
| :--- | :--- |
| **Total Rows Received** | {self.total_rows_received} |
| **Rows Retained (Valid & In-Scope)** | {self.rows_retained} |
| **Rows Rejected** | {self.rows_rejected} |
| **Duplicates Filtered** | {self.duplicate_count} |
| **Out-of-Scope (BBox Filtered)** | {self.out_of_bounds_count} |
| **Validity Rate** | {self.validity_rate_pct:.1f}% |

## Spatio-Temporal Envelope

* **Geographic Extent:** {geo_str}
* **Acquisition Time Window:** {time_str}

## Thermal Energy (Fire Radiative Power)

* **FRP Statistics:** {frp_str}

## Signal Distributions

### By Satellite Platform
"""
        for sat, cnt in self.satellites_represented.items():
            md += f"- **{sat}:** {cnt} detections\n"

        md += "\n### By Confidence Level\n"
        for conf, cnt in self.confidence_distribution.items():
            md += f"- **{conf}:** {cnt} detections\n"

        md += "\n### By Orbit Pass (Day/Night)\n"
        for dn, cnt in self.daynight_distribution.items():
            label = "Day" if dn == "D" else ("Night" if dn == "N" else dn)
            md += f"- **{label} ({dn}):** {cnt} detections\n"

        if self.rejection_reasons:
            md += "\n## Rejection Reasons Breakdown\n\n"
            for reason, cnt in self.rejection_reasons.items():
                md += f"- `{reason}`: {cnt}\n"

        md += "\n---\n*Report generated deterministically by VayuDrishti NASA FIRMS Ingestion Engine.*"
        return md


class FIRMSValidator:
    """Audits, spatial-filters, deduplicates, and validates FireSignal objects."""

    def __init__(self):
        pass

    def validate_signal(
        self,
        signal: FireSignal,
        bbox: Optional[Dict[str, float]] = None,
    ) -> FIRMSValidationOutcome:
        """Validate a single FireSignal against physical limits and spatial bounding box."""
        # 1. Geographic Coordinate Validation
        if not (-90.0 <= signal.latitude <= 90.0) or not (-180.0 <= signal.longitude <= 180.0):
            return FIRMSValidationOutcome(
                is_valid=False,
                rejection_reason=f"Coordinates out of physical bounds: lat={signal.latitude}, lon={signal.longitude}",
            )

        # 2. Spatial Bounding Box Filter (if specified)
        if bbox:
            lat_min = bbox.get("lat_min", -90.0)
            lat_max = bbox.get("lat_max", 90.0)
            lon_min = bbox.get("lon_min", -180.0)
            lon_max = bbox.get("lon_max", 180.0)
            if not (lat_min <= signal.latitude <= lat_max and lon_min <= signal.longitude <= lon_max):
                return FIRMSValidationOutcome(
                    is_valid=False,
                    rejection_reason="Outside target pilot geographic bounding box",
                    is_out_of_bounds=True,
                )

        # 3. Fire Radiative Power (FRP) non-negative check
        if signal.frp_mw is not None and signal.frp_mw < 0.0:
            return FIRMSValidationOutcome(
                is_valid=False,
                rejection_reason=f"Negative Fire Radiative Power: {signal.frp_mw} MW",
            )

        # 4. Thermal Brightness Temperature Physical Ranges
        if signal.bright_ti4_k is not None:
            if not (150.0 <= signal.bright_ti4_k <= 600.0):
                return FIRMSValidationOutcome(
                    is_valid=False,
                    rejection_reason=f"Brightness temperature I-4 out of physical range (150-600K): {signal.bright_ti4_k} K",
                )

        if signal.bright_ti5_k is not None:
            if not (150.0 <= signal.bright_ti5_k <= 500.0):
                return FIRMSValidationOutcome(
                    is_valid=False,
                    rejection_reason=f"Brightness temperature I-5 out of physical range (150-500K): {signal.bright_ti5_k} K",
                )

        return FIRMSValidationOutcome(is_valid=True)

    def validate_dataset(
        self,
        signals: List[FireSignal],
        bbox: Optional[Dict[str, float]] = None,
        retrieval_time: Optional[datetime] = None,
        product_name: str = "SUOMI_VIIRS_C2_South_Asia_24h",
    ) -> Tuple[List[FireSignal], FIRMSQualityReport]:
        """Validate, deduplicate, and chronologically sort a dataset of FireSignal objects.
        
        Returns:
            (retained_signals_sorted, quality_report)
        """
        seen_ids: Set[str] = set()
        retained: List[FireSignal] = []
        rejection_reasons: Dict[str, int] = {}
        sat_counts: Dict[str, int] = {}
        conf_counts: Dict[str, int] = {}
        dn_counts: Dict[str, int] = {}

        total_received = len(signals)
        duplicate_count = 0
        out_of_bounds_count = 0

        for signal in signals:
            # Check duplicate by deterministic signal_id
            if signal.signal_id in seen_ids:
                duplicate_count += 1
                rejection_reasons["Duplicate signal identity"] = (
                    rejection_reasons.get("Duplicate signal identity", 0) + 1
                )
                continue

            outcome = self.validate_signal(signal, bbox=bbox)
            if not outcome.is_valid:
                reason = outcome.rejection_reason or "Unknown validation failure"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                if outcome.is_out_of_bounds:
                    out_of_bounds_count += 1
                continue

            # Accepted record
            seen_ids.add(signal.signal_id)
            retained.append(signal)

            # Accumulate distributions
            sat_counts[signal.satellite] = sat_counts.get(signal.satellite, 0) + 1
            conf_counts[signal.confidence] = conf_counts.get(signal.confidence, 0) + 1
            if signal.daynight:
                dn_counts[signal.daynight] = dn_counts.get(signal.daynight, 0) + 1

        # Sort chronologically by acquisition_time
        retained.sort(key=lambda s: s.acquisition_time)

        # Compute spatio-temporal and FRP summaries
        geo_extent = None
        time_range = None
        frp_summary = None

        if retained:
            min_lat = min(s.latitude for s in retained)
            max_lat = max(s.latitude for s in retained)
            min_lon = min(s.longitude for s in retained)
            max_lon = max(s.longitude for s in retained)
            geo_extent = {
                "min_lat": min_lat,
                "max_lat": max_lat,
                "min_lon": min_lon,
                "max_lon": max_lon,
            }

            min_time = min(s.acquisition_time for s in retained)
            max_time = max(s.acquisition_time for s in retained)
            time_range = {
                "min_utc": min_time.isoformat(),
                "max_utc": max_time.isoformat(),
            }

            frp_values = [s.frp_mw for s in retained if s.frp_mw is not None]
            if frp_values:
                frp_summary = {
                    "min_mw": round(min(frp_values), 2),
                    "max_mw": round(max(frp_values), 2),
                    "mean_mw": round(sum(frp_values) / len(frp_values), 2),
                    "total_mw": round(sum(frp_values), 2),
                }

        retained_count = len(retained)
        rejected_count = total_received - retained_count
        validity_rate = (retained_count / total_received * 100.0) if total_received > 0 else 0.0

        report = FIRMSQualityReport(
            source="NASA_FIRMS",
            product=product_name,
            retrieval_timestamp=retrieval_time or datetime.now(timezone.utc),
            total_rows_received=total_received,
            rows_retained=retained_count,
            rows_rejected=rejected_count,
            duplicate_count=duplicate_count,
            out_of_bounds_count=out_of_bounds_count,
            bounding_box_filter=bbox,
            geographic_extent=geo_extent,
            acquisition_time_range=time_range,
            satellites_represented=sat_counts,
            confidence_distribution=conf_counts,
            daynight_distribution=dn_counts,
            frp_summary=frp_summary,
            rejection_reasons=rejection_reasons,
            validity_rate_pct=round(validity_rate, 2),
        )

        return retained, report
