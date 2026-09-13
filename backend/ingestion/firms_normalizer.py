"""
VayuDrishti - NASA FIRMS Normalizer
Converts raw FIRMS CSV records into canonical FireSignal models.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.api.v1.schemas.satellite import FireSignal

logger = logging.getLogger(__name__)

NORMALIZATION_VERSION = "1.0"

# Satellite platform mapping for NASA FIRMS feeds
SATELLITE_CODE_MAP = {
    "N": "Suomi-NPP",
    "n": "Suomi-NPP",
    "1": "NOAA-20",
    "2": "NOAA-21",
    "T": "Terra",
    "t": "Terra",
    "A": "Aqua",
    "a": "Aqua",
}

INSTRUMENT_MAP = {
    "Suomi-NPP": "VIIRS",
    "NOAA-20": "VIIRS",
    "NOAA-21": "VIIRS",
    "Terra": "MODIS",
    "Aqua": "MODIS",
}


class FIRMSNormalizationResult(BaseModel):
    """Encapsulates the normalization outcome of a single FIRMS CSV row."""
    signal: Optional[FireSignal] = None
    is_valid: bool = False
    rejection_reason: Optional[str] = None
    raw_record: Dict[str, Any] = Field(default_factory=dict)


class FIRMSNormalizer:
    """Normalizes raw NASA FIRMS CSV row dictionaries into canonical FireSignal objects.
    
    Principles:
    1. Strict UTC timestamp reconstruction from acq_date (YYYY-MM-DD) and acq_time (HHMM).
    2. Preservation of raw categorical confidence without artificial probability conversions.
    3. Fire Radiative Power (FRP) preserved in MW as reported, strictly as a thermal intensity metric.
    4. Dual-band brightness temperatures (I-4, I-5) preserved in Kelvin.
    5. Clean deterministic identifier: firms:{satellite}:{lat:.5f}:{lon:.5f}:{date}:{time}.
    """

    def __init__(self, normalization_version: str = NORMALIZATION_VERSION):
        self.version = normalization_version

    def normalize_row(
        self,
        row: Dict[str, str],
        retrieved_at: Optional[datetime] = None,
        source_url: Optional[str] = None,
        product_name: str = "SUOMI_VIIRS_C2_South_Asia_24h",
    ) -> FIRMSNormalizationResult:
        """Normalize a single raw CSV row dictionary into a FireSignal."""
        if not row:
            return FIRMSNormalizationResult(
                is_valid=False,
                rejection_reason="Empty or null CSV row",
                raw_record=row or {},
            )

        # 1. Coordinate extraction and basic numeric check
        raw_lat = row.get("latitude")
        raw_lon = row.get("longitude")
        if raw_lat is None or raw_lon is None or raw_lat == "" or raw_lon == "":
            return FIRMSNormalizationResult(
                is_valid=False,
                rejection_reason="Missing latitude or longitude coordinate",
                raw_record=row,
            )

        try:
            lat = float(raw_lat)
            lon = float(raw_lon)
        except (ValueError, TypeError) as exc:
            return FIRMSNormalizationResult(
                is_valid=False,
                rejection_reason=f"Invalid coordinate format ({raw_lat}, {raw_lon}): {exc}",
                raw_record=row,
            )

        # Coordinate range boundaries
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            return FIRMSNormalizationResult(
                is_valid=False,
                rejection_reason=f"Coordinates out of bounds: lat={lat}, lon={lon}",
                raw_record=row,
            )

        # 2. Acquisition Date & Time normalization to UTC
        acq_date = row.get("acq_date", "").strip()
        acq_time_raw = row.get("acq_time", "").strip()
        if not acq_date or not acq_time_raw:
            return FIRMSNormalizationResult(
                is_valid=False,
                rejection_reason="Missing acq_date or acq_time",
                raw_record=row,
            )

        # acq_time in FIRMS is typically 3 or 4 digits (e.g. '603' or '0603' or '2014')
        acq_time_padded = acq_time_raw.zfill(4)
        if len(acq_time_padded) != 4 or not acq_time_padded.isdigit():
            return FIRMSNormalizationResult(
                is_valid=False,
                rejection_reason=f"Malformed acq_time format: '{acq_time_raw}'",
                raw_record=row,
            )

        try:
            hour = int(acq_time_padded[:2])
            minute = int(acq_time_padded[2:])
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return FIRMSNormalizationResult(
                    is_valid=False,
                    rejection_reason=f"Out-of-range acquisition time: {hour:02d}:{minute:02d}",
                    raw_record=row,
                )
            
            # Parse YYYY-MM-DD
            dt_date = datetime.strptime(acq_date, "%Y-%m-%d")
            acq_timestamp = datetime(
                dt_date.year, dt_date.month, dt_date.day,
                hour, minute, 0,
                tzinfo=timezone.utc
            )
        except Exception as exc:
            return FIRMSNormalizationResult(
                is_valid=False,
                rejection_reason=f"Invalid date/time combination '{acq_date} {acq_time_raw}': {exc}",
                raw_record=row,
            )

        # 3. Satellite and Instrument identification
        raw_sat = row.get("satellite", "").strip()
        satellite_name = SATELLITE_CODE_MAP.get(raw_sat, raw_sat or "VIIRS")
        instrument = INSTRUMENT_MAP.get(satellite_name, "VIIRS")

        # 4. Confidence normalization (Preserve raw, do NOT create fake probabilities)
        raw_confidence = row.get("confidence", "").strip()
        quality_indicator, normalized_confidence = self._normalize_confidence(raw_confidence)

        # 5. Fire Radiative Power (FRP) in MW
        frp_mw: Optional[float] = None
        raw_frp = row.get("frp", "").strip()
        if raw_frp:
            try:
                frp_mw = float(raw_frp)
                if frp_mw < 0.0:
                    return FIRMSNormalizationResult(
                        is_valid=False,
                        rejection_reason=f"Negative FRP value: {frp_mw}",
                        raw_record=row,
                    )
            except (ValueError, TypeError) as exc:
                return FIRMSNormalizationResult(
                    is_valid=False,
                    rejection_reason=f"Malformed FRP value '{raw_frp}': {exc}",
                    raw_record=row,
                )

        # 6. Brightness Temperatures (I-4 and I-5 in Kelvin)
        bright_ti4: Optional[float] = None
        bright_ti5: Optional[float] = None
        raw_b4 = row.get("bright_ti4", "").strip()
        raw_b5 = row.get("bright_ti5", "").strip()

        if raw_b4:
            try:
                bright_ti4 = float(raw_b4)
                if not (150.0 <= bright_ti4 <= 600.0):
                    return FIRMSNormalizationResult(
                        is_valid=False,
                        rejection_reason=f"Brightness temperature I-4 out of physical range (150-600K): {bright_ti4}",
                        raw_record=row,
                    )
            except (ValueError, TypeError):
                return FIRMSNormalizationResult(
                    is_valid=False,
                    rejection_reason=f"Malformed bright_ti4 value: '{raw_b4}'",
                    raw_record=row,
                )

        if raw_b5:
            try:
                bright_ti5 = float(raw_b5)
                if not (150.0 <= bright_ti5 <= 500.0):
                    return FIRMSNormalizationResult(
                        is_valid=False,
                        rejection_reason=f"Brightness temperature I-5 out of physical range (150-500K): {bright_ti5}",
                        raw_record=row,
                    )
            except (ValueError, TypeError):
                return FIRMSNormalizationResult(
                    is_valid=False,
                    rejection_reason=f"Malformed bright_ti5 value: '{raw_b5}'",
                    raw_record=row,
                )

        # 7. Day / Night flag
        daynight = row.get("daynight", "").strip().upper() or None
        if daynight and daynight not in ("D", "N"):
            # If not standard, keep as is or log
            pass

        # 8. Scan and Track
        scan_val: Optional[float] = None
        track_val: Optional[float] = None
        if row.get("scan", "").strip():
            try:
                scan_val = float(row["scan"])
            except ValueError:
                pass
        if row.get("track", "").strip():
            try:
                track_val = float(row["track"])
            except ValueError:
                pass

        # 9. Deterministic Signal Identifier
        sat_slug = satellite_name.lower().replace(" ", "-")
        signal_id = f"firms:{sat_slug}:{lat:.5f}:{lon:.5f}:{acq_date}:{acq_time_padded}"

        # 10. Provenance metadata
        provenance = {
            "source_endpoint": source_url or "NASA_FIRMS_NRT_REGIONAL_CSV",
            "retrieved_at": (retrieved_at or datetime.now(timezone.utc)).isoformat(),
            "product": product_name,
            "raw_satellite_code": raw_sat,
            "normalization_version": self.version,
        }

        # 11. Construct canonical FireSignal model
        signal = FireSignal(
            signal_id=signal_id,
            acquisition_time=acq_timestamp,
            satellite=satellite_name,
            instrument=instrument,
            signal_type="THERMAL_FIRE_PIXEL",
            geometry={"type": "Point", "coordinates": [round(lon, 5), round(lat, 5)]},
            value=frp_mw if frp_mw is not None else 0.0,
            unit="MW",
            quality_indicator=quality_indicator,
            processing_level="NRT",
            latitude=round(lat, 5),
            longitude=round(lon, 5),
            acquisition_date=acq_date,
            acquisition_time_str=acq_time_padded,
            confidence=normalized_confidence,
            raw_confidence=raw_confidence,
            frp_mw=frp_mw,
            bright_ti4_k=bright_ti4,
            bright_ti5_k=bright_ti5,
            daynight=daynight,
            scan=scan_val,
            track=track_val,
            version=row.get("version", "").strip() or None,
            source="NASA_FIRMS",
            provenance=provenance,
            raw_payload={k: v for k, v in row.items() if v},
        )

        return FIRMSNormalizationResult(is_valid=True, signal=signal, raw_record=row)

    def normalize_dataset(
        self,
        rows: List[Dict[str, str]],
        retrieved_at: Optional[datetime] = None,
        source_url: Optional[str] = None,
        product_name: str = "SUOMI_VIIRS_C2_South_Asia_24h",
    ) -> List[FIRMSNormalizationResult]:
        """Normalize an entire list of raw CSV row dictionaries."""
        results = []
        for row in rows:
            results.append(
                self.normalize_row(
                    row,
                    retrieved_at=retrieved_at,
                    source_url=source_url,
                    product_name=product_name,
                )
            )
        return results

    @staticmethod
    def _normalize_confidence(raw_conf: str) -> tuple[str, str]:
        """Map raw FIRMS confidence to (quality_indicator, normalized_confidence).
        
        VIIRS provides: 'low', 'nominal', 'high'.
        MODIS provides: 0-100 numeric confidence.
        
        Returns:
            (quality_indicator, normalized_confidence_str)
        """
        if not raw_conf:
            return ("NOMINAL", "nominal")

        clean = raw_conf.strip().lower()

        # Categorical VIIRS check
        if clean in ("low", "l"):
            return ("LOW", "low")
        elif clean in ("nominal", "nom", "n"):
            return ("NOMINAL", "nominal")
        elif clean in ("high", "h"):
            return ("HIGH", "high")

        # Numeric MODIS check
        try:
            num = float(clean)
            if num < 30:
                return ("LOW", f"{int(num)}%")
            elif num <= 80:
                return ("NOMINAL", f"{int(num)}%")
            else:
                return ("HIGH", f"{int(num)}%")
        except ValueError:
            return ("NOMINAL", clean)
