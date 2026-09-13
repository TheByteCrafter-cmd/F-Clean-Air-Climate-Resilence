"""
VayuDrishti - Sentinel-5P Validator & Quality Auditor
Audits physical boundaries, cloud screening, negative value preservation, and quality reporting.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from backend.api.v1.schemas.satellite import Sentinel5PNO2Signal
from backend.ingestion.sentinel5p_client import DEFAULT_DELHI_ROI, GEE_COLLECTION_ID, PRIMARY_BAND

logger = logging.getLogger(__name__)

MAX_ALLOWED_CLOUD_FRACTION = 0.50  # ESA/Copernicus recommended tropospheric threshold


class Sentinel5PValidationOutcome(BaseModel):
    """Validation outcome for an individual Sentinel5PNO2Signal."""
    is_valid: bool
    rejection_reason: Optional[str] = None
    is_duplicate: bool = False
    is_out_of_bounds: bool = False
    is_cloud_rejected: bool = False
    is_negative_preserved: bool = False


class Sentinel5PQualityReport(BaseModel):
    """Comprehensive data quality and provenance audit report for Sentinel-5P NO2."""
    dataset_id: str = GEE_COLLECTION_ID
    band: str = PRIMARY_BAND
    unit: str = "mol/m?"
    retrieval_timestamp: Optional[datetime] = None
    retrieval_mode: str = "CACHED_FALLBACK"  # or LIVE_GEE
    authentication_status: str = "GEE RUNTIME ACCESS NOT CONFIGURED"
    roi_filter: Optional[Dict[str, float]] = None
    geographic_extent: Optional[Dict[str, float]] = None
    acquisition_time_range: Optional[Dict[str, str]] = None
    total_samples_received: int = 0
    samples_retained: int = 0
    samples_rejected: int = 0
    duplicate_count: int = 0
    out_of_bounds_count: int = 0
    cloud_rejected_count: int = 0
    negative_values_preserved_count: int = 0
    no2_summary_mol_m2: Optional[Dict[str, float]] = None
    no2_summary_umol_m2: Optional[Dict[str, float]] = None
    cloud_fraction_summary: Optional[Dict[str, float]] = None
    quality_distribution: Dict[str, int] = Field(default_factory=dict)
    rejection_reasons: Dict[str, int] = Field(default_factory=dict)
    validity_rate_pct: float = 0.0

    def to_markdown(self) -> str:
        """Render quality report as human-readable GitHub-flavored Markdown."""
        retrieval_str = (
            self.retrieval_timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            if self.retrieval_timestamp
            else "N/A"
        )
        geo_str = (
            f"Lat [{self.geographic_extent['min_lat']:.4f}, {self.geographic_extent['max_lat']:.4f}], "
            f"Lon [{self.geographic_extent['min_lon']:.4f}, {self.geographic_extent['max_lon']:.4f}]"
            if self.geographic_extent
            else "None"
        )
        time_str = (
            f"{self.acquisition_time_range['min_utc']} to {self.acquisition_time_range['max_utc']}"
            if self.acquisition_time_range
            else "None"
        )
        no2_str = (
            f"Min: {self.no2_summary_mol_m2['min_mol_m2']:.6f} mol/m? ({self.no2_summary_umol_m2['min_umol_m2']:.2f} ?mol/m?), "
            f"Max: {self.no2_summary_mol_m2['max_mol_m2']:.6f} mol/m? ({self.no2_summary_umol_m2['max_umol_m2']:.2f} ?mol/m?), "
            f"Mean: {self.no2_summary_mol_m2['mean_mol_m2']:.6f} mol/m? ({self.no2_summary_umol_m2['mean_umol_m2']:.2f} ?mol/m?)"
            if self.no2_summary_mol_m2
            else "None"
        )
        cloud_str = (
            f"Min: {self.cloud_fraction_summary['min']:.2f}, Max: {self.cloud_fraction_summary['max']:.2f}, "
            f"Mean: {self.cloud_fraction_summary['mean']:.2f}"
            if self.cloud_fraction_summary
            else "N/A"
        )
        roi_str = (
            f"Lat [{self.roi_filter['lat_min']}, {self.roi_filter['lat_max']}], "
            f"Lon [{self.roi_filter['lon_min']}, {self.roi_filter['lon_max']}]"
            if self.roi_filter
            else "Unfiltered"
        )

        md = f"""# Sentinel-5P TROPOMI Tropospheric NO2 Ingestion Quality Report

**Dataset ID:** `{self.dataset_id}`  
**Primary Band:** `{self.band}`  
**Unit:** `{self.unit}`  
**Retrieval Mode:** `{self.retrieval_mode}`  
**GEE Authentication:** `{self.authentication_status}`  
**Retrieval Time:** {retrieval_str}  
**Region of Interest (ROI):** {roi_str}  

## Summary Statistics

| Metric | Value |
| :--- | :--- |
| **Total Samples Received** | {self.total_samples_received} |
| **Samples Retained (Valid & Clear)** | {self.samples_retained} |
| **Samples Rejected** | {self.samples_rejected} |
| **Duplicates Filtered** | {self.duplicate_count} |
| **Out-of-ROI Filtered** | {self.out_of_bounds_count} |
| **Cloud Obscured (Rejected)** | {self.cloud_rejected_count} |
| **Negative Values Preserved (Noise)** | {self.negative_values_preserved_count} |
| **Validity Rate** | {self.validity_rate_pct:.1f}% |

## Spatio-Temporal Window

* **Geographic Extent:** {geo_str}
* **Acquisition Time Window:** {time_str}

## Atmospheric Column Density (mol/m?)

* **Tropospheric NO2:** {no2_str}
* **Cloud Fraction:** {cloud_str}

## Quality Level Distribution
"""
        for q, cnt in self.quality_distribution.items():
            md += f"- **{q}:** {cnt} samples\n"

        if self.rejection_reasons:
            md += "\n## Rejection Breakdown\n\n"
            for reason, cnt in self.rejection_reasons.items():
                md += f"- `{reason}`: {cnt}\n"

        md += """
## Scientific Integrity Note

1. **Vertical Column != Ground Level:** Sentinel-5P measures total integrated moles of NO2 per square meter across the tropospheric column. It does NOT measure breathing-zone concentration (?g/m?) or PM2.5.
2. **Negative Value Preservation:** DOAS spectral fitting noise yields small negative values over clean air. Clamping these to zero causes systematic positive bias; they are retained for spatial averaging.
3. **Overpass Frequency:** Single daily overpass (~13:30 local time); does not capture rush-hour or nocturnal peaks.

---
*Report generated deterministically by VayuDrishti Sentinel-5P Ingestion Engine.*
"""
        return md


class Sentinel5PValidator:
    """Audits, spatial-filters, cloud-screens, and deduplicates Sentinel-5P signals."""

    def __init__(self, filter_clouds: bool = True, max_cloud_fraction: float = MAX_ALLOWED_CLOUD_FRACTION):
        self.filter_clouds = filter_clouds
        self.max_cloud_fraction = max_cloud_fraction

    def validate_signal(
        self,
        signal: Sentinel5PNO2Signal,
        roi: Optional[Dict[str, float]] = None,
    ) -> Sentinel5PValidationOutcome:
        """Validate a single Sentinel5PNO2Signal against physical, spatial, and cloud limits."""
        # 1. Coordinate check
        if not (-90.0 <= signal.latitude <= 90.0) or not (-180.0 <= signal.longitude <= 180.0):
            return Sentinel5PValidationOutcome(
                is_valid=False,
                rejection_reason=f"Coordinates out of bounds: lat={signal.latitude}, lon={signal.longitude}",
            )

        # 2. ROI spatial filter
        if roi:
            lat_min = roi.get("lat_min", -90.0)
            lat_max = roi.get("lat_max", 90.0)
            lon_min = roi.get("lon_min", -180.0)
            lon_max = roi.get("lon_max", 180.0)
            if not (lat_min <= signal.latitude <= lat_max and lon_min <= signal.longitude <= lon_max):
                return Sentinel5PValidationOutcome(
                    is_valid=False,
                    rejection_reason="Outside target Region of Interest (ROI)",
                    is_out_of_bounds=True,
                )

        # 3. Cloud screening
        if self.filter_clouds and signal.cloud_fraction is not None:
            if signal.cloud_fraction > self.max_cloud_fraction:
                return Sentinel5PValidationOutcome(
                    is_valid=False,
                    rejection_reason=f"Cloud fraction {signal.cloud_fraction:.2f} exceeds threshold {self.max_cloud_fraction}",
                    is_cloud_rejected=True,
                )

        # 4. Check negative values
        is_neg_preserved = signal.tropospheric_no2_mol_m2 < 0.0

        return Sentinel5PValidationOutcome(
            is_valid=True,
            is_negative_preserved=is_neg_preserved,
        )

    def validate_dataset(
        self,
        signals: List[Sentinel5PNO2Signal],
        roi: Optional[Dict[str, float]] = None,
        retrieval_time: Optional[datetime] = None,
        retrieval_mode: str = "CACHED_FALLBACK",
        auth_status: str = "GEE RUNTIME ACCESS NOT CONFIGURED",
    ) -> Tuple[List[Sentinel5PNO2Signal], Sentinel5PQualityReport]:
        """Validate, deduplicate, and chronologically sort a dataset of Sentinel5PNO2Signal objects."""
        seen_ids: Set[str] = set()
        retained: List[Sentinel5PNO2Signal] = []
        rejection_reasons: Dict[str, int] = {}
        quality_counts: Dict[str, int] = {}

        total_received = len(signals)
        duplicate_count = 0
        out_of_bounds_count = 0
        cloud_rejected_count = 0
        negative_preserved_count = 0

        for signal in signals:
            if signal.signal_id in seen_ids:
                duplicate_count += 1
                rejection_reasons["Duplicate signal identity"] = (
                    rejection_reasons.get("Duplicate signal identity", 0) + 1
                )
                continue

            outcome = self.validate_signal(signal, roi=roi)
            if not outcome.is_valid:
                reason = outcome.rejection_reason or "Unknown validation rejection"
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                if outcome.is_out_of_bounds:
                    out_of_bounds_count += 1
                if outcome.is_cloud_rejected:
                    cloud_rejected_count += 1
                continue

            # Valid record
            seen_ids.add(signal.signal_id)
            retained.append(signal)

            if outcome.is_negative_preserved:
                negative_preserved_count += 1

            quality_counts[signal.quality_indicator] = (
                quality_counts.get(signal.quality_indicator, 0) + 1
            )

        # Sort chronologically
        retained.sort(key=lambda s: s.acquisition_time)

        # Statistical summaries
        geo_extent = None
        time_range = None
        no2_summary = None
        no2_summary_umol = None
        cloud_summary = None

        if retained:
            geo_extent = {
                "min_lat": min(s.latitude for s in retained),
                "max_lat": max(s.latitude for s in retained),
                "min_lon": min(s.longitude for s in retained),
                "max_lon": max(s.longitude for s in retained),
            }
            time_range = {
                "min_utc": min(s.acquisition_time for s in retained).isoformat(),
                "max_utc": max(s.acquisition_time for s in retained).isoformat(),
            }

            vals = [s.tropospheric_no2_mol_m2 for s in retained]
            no2_summary = {
                "min_mol_m2": min(vals),
                "max_mol_m2": max(vals),
                "mean_mol_m2": sum(vals) / len(vals),
            }
            no2_summary_umol = {
                "min_umol_m2": min(vals) * 1e6,
                "max_umol_m2": max(vals) * 1e6,
                "mean_umol_m2": (sum(vals) / len(vals)) * 1e6,
            }

            cfs = [s.cloud_fraction for s in retained if s.cloud_fraction is not None]
            if cfs:
                cloud_summary = {
                    "min": min(cfs),
                    "max": max(cfs),
                    "mean": sum(cfs) / len(cfs),
                }

        retained_count = len(retained)
        rejected_count = total_received - retained_count
        validity_rate = (retained_count / total_received * 100.0) if total_received > 0 else 0.0

        report = Sentinel5PQualityReport(
            dataset_id=GEE_COLLECTION_ID,
            band=PRIMARY_BAND,
            unit="mol/m?",
            retrieval_timestamp=retrieval_time or datetime.now(timezone.utc),
            retrieval_mode=retrieval_mode,
            authentication_status=auth_status,
            roi_filter=roi,
            geographic_extent=geo_extent,
            acquisition_time_range=time_range,
            total_samples_received=total_received,
            samples_retained=retained_count,
            samples_rejected=rejected_count,
            duplicate_count=duplicate_count,
            out_of_bounds_count=out_of_bounds_count,
            cloud_rejected_count=cloud_rejected_count,
            negative_values_preserved_count=negative_preserved_count,
            no2_summary_mol_m2=no2_summary,
            no2_summary_umol_m2=no2_summary_umol,
            cloud_fraction_summary=cloud_summary,
            quality_distribution=quality_counts,
            rejection_reasons=rejection_reasons,
            validity_rate_pct=round(validity_rate, 2),
        )

        return retained, report
