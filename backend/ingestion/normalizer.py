"""
VayuDrishti - OpenAQ Normalization Engine
Normalizes raw OpenAQ v3 payloads into canonical EnvironmentalObservation models.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.api.v1.schemas.common import Location
from backend.api.v1.schemas.observation import EnvironmentalObservation

logger = logging.getLogger(__name__)

NORMALIZATION_VERSION = "1.0"

# Canonical pollutant mapping
POLLUTANT_MAP = {
    "pm25": "PM2.5",
    "pm2.5": "PM2.5",
    "pm_25": "PM2.5",
    "pm 2.5": "PM2.5",
    "pm10": "PM10",
    "pm_10": "PM10",
    "pm 10": "PM10",
    "no2": "NO2",
    "nitrogen dioxide": "NO2",
    "so2": "SO2",
    "sulfur dioxide": "SO2",
    "co": "CO",
    "carbon monoxide": "CO",
    "o3": "O3",
    "ozone": "O3",
}

CANONICAL_UNIT = "?g/m?"

# Recognized unit variants for micrograms per cubic meter
UG_M3_VARIANTS = {
    "?g/m?",
    "?g/m3",
    "ug/m?",
    "ug/m3",
    "ug/m^3",
    "ugm-3",
    "micrograms/m3",
    "micrograms per cubic meter",
}

# Recognized unit variants for milligrams per cubic meter
MG_M3_VARIANTS = {
    "mg/m?",
    "mg/m3",
    "mg/m^3",
    "mgm-3",
    "milligrams/m3",
}


@dataclass
class NormalizationResult:
    """Outcome of single record normalization."""
    is_valid: bool
    observation: Optional[EnvironmentalObservation] = None
    rejection_reason: Optional[str] = None
    raw_record: Optional[Dict[str, Any]] = None


class OpenAQNormalizer:
    """Normalization layer for OpenAQ records."""

    def __init__(self, version: str = NORMALIZATION_VERSION):
        self.version = version

    def normalize_pollutant(self, raw_param: str) -> Optional[str]:
        """Normalize pollutant parameter name to canonical string."""
        if not raw_param:
            return None
        cleaned = raw_param.strip().lower()
        return POLLUTANT_MAP.get(cleaned)

    def normalize_unit_and_value(self, pollutant: str, value: float, unit: str) -> Tuple[float, str, Optional[str]]:
        """Deterministic unit transformation.
        
        Returns: (transformed_value, canonical_unit, note)
        """
        if not unit:
            return value, "unknown", "missing_unit"

        cleaned_unit = unit.strip().lower()

        # Standard ?g/m? match
        if cleaned_unit in [u.lower() for u in UG_M3_VARIANTS]:
            return value, CANONICAL_UNIT, None

        # CO milligrams per cubic meter conversion (1 mg/m? = 1000 ?g/m?)
        if pollutant == "CO" and cleaned_unit in [u.lower() for u in MG_M3_VARIANTS]:
            return round(value * 1000.0, 3), CANONICAL_UNIT, "converted_mg_to_ug"

        # Non-mass concentration units preserved as-is
        return value, unit.strip(), "unconverted_source_unit"

    def parse_timestamp(self, raw_datetime: Any) -> Optional[datetime]:
        """Extract and parse UTC datetime from ISO string or OpenAQ DatetimeObject."""
        if not raw_datetime:
            return None

        time_str = None
        if isinstance(raw_datetime, dict):
            # OpenAQ v3 DatetimeObject provides {'utc': '...', 'local': '...'}
            time_str = raw_datetime.get("utc") or raw_datetime.get("local")
        elif isinstance(raw_datetime, str):
            time_str = raw_datetime

        if not time_str:
            return None

        try:
            # Handle ISO-8601 strings (Z or +HH:MM)
            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse timestamp '{time_str}': {e}")
            return None

    def normalize_record(
        self,
        raw_reading: Dict[str, Any],
        location_meta: Optional[Dict[str, Any]] = None,
        retrieved_at: Optional[datetime] = None,
    ) -> NormalizationResult:
        """Normalize a single OpenAQ reading with its location context into an EnvironmentalObservation."""
        retrieved_at = retrieved_at or datetime.now(timezone.utc)
        loc_meta = location_meta or {}

        # 1. Extract and normalize pollutant
        param_obj = raw_reading.get("parameter")
        raw_pollutant = None
        source_unit = None

        if isinstance(param_obj, dict):
            raw_pollutant = param_obj.get("name") or param_obj.get("displayName")
            source_unit = param_obj.get("units")
        elif isinstance(param_obj, str):
            raw_pollutant = param_obj

        # Fallback to sensor name or reading parameter field
        if not raw_pollutant:
            raw_pollutant = raw_reading.get("name") or raw_reading.get("parameter_name")

        canonical_pollutant = self.normalize_pollutant(raw_pollutant or "")
        if not canonical_pollutant:
            return NormalizationResult(
                is_valid=False,
                rejection_reason=f"unsupported_pollutant: '{raw_pollutant}'",
                raw_record=raw_reading,
            )

        # 2. Extract and validate measured value
        raw_value = raw_reading.get("value")
        if raw_value is None:
            return NormalizationResult(
                is_valid=False,
                rejection_reason="missing_value",
                raw_record=raw_reading,
            )

        try:
            val_float = float(raw_value)
        except (ValueError, TypeError):
            return NormalizationResult(
                is_valid=False,
                rejection_reason=f"non_numeric_value: '{raw_value}'",
                raw_record=raw_reading,
            )

        if val_float < 0.0:
            return NormalizationResult(
                is_valid=False,
                rejection_reason=f"negative_concentration_physical_violation: {val_float}",
                raw_record=raw_reading,
            )

        # 3. Normalize unit and value
        norm_val, norm_unit, unit_note = self.normalize_unit_and_value(
            canonical_pollutant, val_float, source_unit or "?g/m?"
        )

        # 4. Parse timestamp
        raw_dt = raw_reading.get("datetime") or raw_reading.get("datetimeLast")
        dt = self.parse_timestamp(raw_dt)
        if not dt:
            return NormalizationResult(
                is_valid=False,
                rejection_reason="invalid_or_missing_timestamp",
                raw_record=raw_reading,
            )

        # 5. Extract coordinates
        coords = raw_reading.get("coordinates") or loc_meta.get("coordinates") or {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")

        if lat is None or lon is None:
            return NormalizationResult(
                is_valid=False,
                rejection_reason="missing_coordinates",
                raw_record=raw_reading,
            )

        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (ValueError, TypeError):
            return NormalizationResult(
                is_valid=False,
                rejection_reason="non_numeric_coordinates",
                raw_record=raw_reading,
            )

        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
            return NormalizationResult(
                is_valid=False,
                rejection_reason=f"coordinates_out_of_bounds: lat={lat_f}, lon={lon_f}",
                raw_record=raw_reading,
            )

        # 6. Station & Provenance identifiers
        loc_id = loc_meta.get("id") or raw_reading.get("locationsId")
        sensor_id = raw_reading.get("sensorsId") or raw_reading.get("id")
        loc_name = loc_meta.get("name") or f"OpenAQ Location {loc_id}"
        
        # Determine source attribution
        provider = loc_meta.get("provider", {})
        provider_name = provider.get("name") if isinstance(provider, dict) else str(provider)
        owner = loc_meta.get("owner", {})
        owner_name = owner.get("name") if isinstance(owner, dict) else str(owner)
        
        source_label = "CAAQMS"
        if provider_name and "cpcb" in provider_name.lower():
            source_label = "CPCB_CAAQMS"
        elif owner_name:
            source_label = f"CAAQMS_{owner_name.split()[0]}"

        station_slug = f"DL_{loc_id}" if loc_id else "UNKNOWN_STATION"
        if loc_name:
            # Clean station name slug
            clean_name = "".join(c if c.isalnum() else "_" for c in loc_name.split(",")[0].strip().upper())
            station_slug = f"{clean_name}_{loc_id}" if loc_id else clean_name

        ts_slug = dt.strftime("%Y%m%d%H%M%S")
        source_record_id = f"openaq-loc-{loc_id}-sensor-{sensor_id}-{canonical_pollutant}-{ts_slug}"

        location_obj = Location(
            latitude=lat_f,
            longitude=lon_f,
            address=loc_name,
        )

        try:
            observation = EnvironmentalObservation(
                timestamp=dt,
                location=location_obj,
                pollutant=canonical_pollutant,
                value=norm_val,
                unit=norm_unit,
                source=source_label,
                station_id=station_slug,
                source_record_id=source_record_id,
                retrieved_at=retrieved_at,
                source_url=f"https://api.openaq.org/v3/locations/{loc_id}",
                normalization_version=self.version,
                raw_payload={
                    "sensor_id": sensor_id,
                    "location_id": loc_id,
                    "raw_pollutant": raw_pollutant,
                    "raw_value": raw_value,
                    "raw_unit": source_unit,
                    "unit_note": unit_note,
                },
            )
            return NormalizationResult(is_valid=True, observation=observation, raw_record=raw_reading)
        except Exception as e:
            return NormalizationResult(
                is_valid=False,
                rejection_reason=f"schema_instantiation_error: {e}",
                raw_record=raw_reading,
            )
