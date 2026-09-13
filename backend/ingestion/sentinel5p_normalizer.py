"""
VayuDrishti - Sentinel-5P TROPOMI Normalizer
Normalizes raw Google Earth Engine / Sentinel-5P records into canonical Sentinel5PNO2Signal models.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.api.v1.schemas.satellite import Sentinel5PNO2Signal
from backend.ingestion.sentinel5p_client import GEE_COLLECTION_ID, PRIMARY_BAND

logger = logging.getLogger(__name__)

NORMALIZATION_VERSION = "1.0"
NO2_UNIT = "mol/m?"

# Noise floor for DOAS spectral retrieval; values below this represent unphysical artifacts
EXTREME_NEGATIVE_THRESHOLD = -0.0001  # -100 ?mol/m?
UNPHYSICAL_UPPER_BOUND = 0.01          # 10,000 ?mol/m?


class Sentinel5PNormalizationResult(BaseModel):
    """Encapsulates normalization outcome for a single Sentinel-5P observation."""
    signal: Optional[Sentinel5PNO2Signal] = None
    is_valid: bool = False
    rejection_reason: Optional[str] = None
    raw_record: Dict[str, Any] = Field(default_factory=dict)


class Sentinel5PNormalizer:
    """Normalizes raw GEE extraction records into canonical Sentinel5PNO2Signal objects.
    
    Principles:
    1. Value preserved strictly in mol/m? (no conversion to PM2.5 or ?g/m?).
    2. Small negative values (>-0.0001 mol/m?) are scientifically valid noise and NOT clamped to zero.
    3. Representative centroid point (Option A) used as geometry with footprint metadata.
    4. Deterministic signal identity: s5p:no2:trop:{lat:.5f}:{lon:.5f}:{timestamp_utc}.
    """

    def __init__(self, normalization_version: str = NORMALIZATION_VERSION):
        self.version = normalization_version

    def normalize_record(
        self,
        record: Dict[str, Any],
        retrieved_at: Optional[datetime] = None,
        source_collection: str = GEE_COLLECTION_ID,
        provenance_extra: Optional[Dict[str, Any]] = None,
    ) -> Sentinel5PNormalizationResult:
        """Normalize a single satellite observation dictionary."""
        if not record:
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason="Empty or null satellite record",
                raw_record=record or {},
            )

        # 1. Coordinate extraction and validation
        raw_lat = record.get("latitude")
        raw_lon = record.get("longitude")
        if raw_lat is None or raw_lon is None or raw_lat == "" or raw_lon == "":
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason="Missing latitude or longitude coordinate",
                raw_record=record,
            )

        try:
            lat = float(raw_lat)
            lon = float(raw_lon)
        except (ValueError, TypeError) as exc:
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason=f"Invalid coordinate format ({raw_lat}, {raw_lon}): {exc}",
                raw_record=record,
            )

        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason=f"Coordinates out of bounds: lat={lat}, lon={lon}",
                raw_record=record,
            )

        # 2. Timestamp extraction and UTC normalization
        acq_time: Optional[datetime] = None
        if "system_time_start" in record and record["system_time_start"] is not None:
            raw_ts = record["system_time_start"]
            try:
                # GEE system:time_start is epoch milliseconds
                if isinstance(raw_ts, (int, float)):
                    acq_time = datetime.fromtimestamp(raw_ts / 1000.0, tz=timezone.utc)
                elif isinstance(raw_ts, str) and raw_ts.isdigit():
                    acq_time = datetime.fromtimestamp(int(raw_ts) / 1000.0, tz=timezone.utc)
                else:
                    acq_time = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
            except Exception as exc:
                return Sentinel5PNormalizationResult(
                    is_valid=False,
                    rejection_reason=f"Failed to parse system_time_start '{raw_ts}': {exc}",
                    raw_record=record,
                )
        elif "timestamp" in record or "acquisition_time" in record:
            raw_iso = record.get("timestamp") or record.get("acquisition_time")
            try:
                acq_time = datetime.fromisoformat(str(raw_iso).replace("Z", "+00:00"))
            except Exception as exc:
                return Sentinel5PNormalizationResult(
                    is_valid=False,
                    rejection_reason=f"Failed to parse timestamp '{raw_iso}': {exc}",
                    raw_record=record,
                )
        else:
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason="Missing observation timestamp / system_time_start",
                raw_record=record,
            )

        # Ensure timezone is UTC
        if acq_time.tzinfo is None:
            acq_time = acq_time.replace(tzinfo=timezone.utc)
        else:
            acq_time = acq_time.astimezone(timezone.utc)

        # 3. Tropospheric NO2 column value extraction
        raw_val = (
            record.get("tropospheric_NO2_column_number_density")
            if "tropospheric_NO2_column_number_density" in record
            else record.get("value")
        )
        if raw_val is None or raw_val == "":
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason="Missing tropospheric NO2 column value",
                raw_record=record,
            )

        try:
            val = float(raw_val)
        except (ValueError, TypeError) as exc:
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason=f"Malformed tropospheric NO2 value '{raw_val}': {exc}",
                raw_record=record,
            )

        # Scientific Negative Value & Upper Bound Handling:
        # Values between -0.0001 and 0.0 mol/m? are valid DOAS noise and MUST NOT be clamped to zero.
        if val < EXTREME_NEGATIVE_THRESHOLD:
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason=f"Unphysical negative tropospheric NO2 anomaly ({val:.6f} mol/m? < {EXTREME_NEGATIVE_THRESHOLD})",
                raw_record=record,
            )

        if val > UNPHYSICAL_UPPER_BOUND:
            return Sentinel5PNormalizationResult(
                is_valid=False,
                rejection_reason=f"Unphysical upper bound tropospheric NO2 ({val:.6f} mol/m? > {UNPHYSICAL_UPPER_BOUND})",
                raw_record=record,
            )

        # 4. Cloud fraction and QA value extraction
        cloud_frac: Optional[float] = None
        if "cloud_fraction" in record and record["cloud_fraction"] is not None and record["cloud_fraction"] != "":
            try:
                cf = float(record["cloud_fraction"])
                if 0.0 <= cf <= 1.0:
                    cloud_frac = cf
            except ValueError:
                pass

        qa_val: Optional[float] = None
        if "qa_value" in record and record["qa_value"] is not None and record["qa_value"] != "":
            try:
                qv = float(record["qa_value"])
                if 0.0 <= qv <= 1.0:
                    qa_val = qv
            except ValueError:
                pass

        # 5. Determine standardized quality indicator
        # High quality: clear sky (cloud_fraction <= 0.3) and high QA (>= 0.75)
        # Nominal quality: moderate cloud (cloud_fraction <= 0.5) and acceptable QA (>= 0.50)
        # Low quality: cloud_fraction > 0.5 or QA < 0.50
        if cloud_frac is not None and cloud_frac > 0.5:
            quality_indicator = "LOW"
        elif qa_val is not None and qa_val < 0.50:
            quality_indicator = "LOW"
        elif (cloud_frac is not None and cloud_frac <= 0.3) or (qa_val is not None and qa_val >= 0.75):
            quality_indicator = "HIGH"
        else:
            quality_indicator = "NOMINAL"

        # 6. Supporting bands (optional)
        strat_no2: Optional[float] = None
        if "stratospheric_NO2_column_number_density" in record and record["stratospheric_NO2_column_number_density"] is not None:
            try:
                strat_no2 = float(record["stratospheric_NO2_column_number_density"])
            except (ValueError, TypeError):
                pass

        tot_no2: Optional[float] = None
        if "NO2_column_number_density" in record and record["NO2_column_number_density"] is not None:
            try:
                tot_no2 = float(record["NO2_column_number_density"])
            except (ValueError, TypeError):
                pass

        # 7. Deterministic Signal Identifier
        iso_str = acq_time.strftime("%Y%m%dT%H%M%SZ")
        signal_id = f"s5p:no2:trop:{lat:.5f}:{lon:.5f}:{iso_str}"

        # 8. Provenance
        provenance = {
            "dataset_id": source_collection,
            "band": PRIMARY_BAND,
            "acquisition_time_utc": acq_time.isoformat(),
            "retrieved_at": (retrieved_at or datetime.now(timezone.utc)).isoformat(),
            "normalization_version": self.version,
            "negative_value_policy": "Preserved without zero-clamping (statistical unbiased)",
        }
        if provenance_extra:
            provenance.update(provenance_extra)

        # 9. Construct canonical Sentinel5PNO2Signal model
        signal = Sentinel5PNO2Signal(
            signal_id=signal_id,
            acquisition_time=acq_time,
            satellite="Sentinel-5P",
            instrument="TROPOMI",
            signal_type="SATELLITE_NO2_COLUMN",
            geometry={"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
            value=val,
            unit=NO2_UNIT,
            quality_indicator=quality_indicator,
            processing_level="L3_NRT",
            latitude=round(lat, 5),
            longitude=round(lon, 5),
            tropospheric_no2_mol_m2=val,
            cloud_fraction=cloud_frac,
            qa_value=qa_val,
            stratospheric_no2_mol_m2=strat_no2,
            total_no2_mol_m2=tot_no2,
            approx_resolution_km=5.5,
            source=source_collection,
            provenance=provenance,
            raw_payload={k: v for k, v in record.items() if v is not None},
        )

        return Sentinel5PNormalizationResult(is_valid=True, signal=signal, raw_record=record)

    def normalize_dataset(
        self,
        records: List[Dict[str, Any]],
        retrieved_at: Optional[datetime] = None,
        source_collection: str = GEE_COLLECTION_ID,
        provenance_extra: Optional[Dict[str, Any]] = None,
    ) -> List[Sentinel5PNormalizationResult]:
        """Normalize an entire list of raw satellite records."""
        results = []
        for rec in records:
            results.append(
                self.normalize_record(
                    rec,
                    retrieved_at=retrieved_at,
                    source_collection=source_collection,
                    provenance_extra=provenance_extra,
                )
            )
        return results
