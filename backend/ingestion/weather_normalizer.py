"""
VayuDrishti - Open-Meteo Weather Normalization Engine
Normalizes Open-Meteo tabular/array payloads into canonical WeatherObservation instances.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.api.v1.schemas.common import Location
from backend.api.v1.schemas.weather import WeatherObservation

logger = logging.getLogger(__name__)

NORMALIZATION_VERSION = "1.0"


@dataclass
class WeatherNormalizationResult:
    """Outcome of normalizing a single hourly weather step."""
    is_valid: bool
    observation: Optional[WeatherObservation] = None
    rejection_reason: Optional[str] = None
    raw_reading: Optional[Dict[str, Any]] = None


class OpenMeteoNormalizer:
    """Transforms Open-Meteo forecast JSON arrays into individual canonical WeatherObservations."""

    def __init__(self, version: str = NORMALIZATION_VERSION):
        self.version = version

    def compute_wind_components(self, speed_ms: float, direction_deg: float) -> Tuple[float, float]:
        """Compute Cartesian meteorological wind components (u eastward, v northward).
        
        Meteorological Convention:
        Wind direction theta is the direction FROM which the wind is blowing,
        measured clockwise from true north (0 = North, 90 = East, 180 = South, 270 = West).
        The velocity vector points towards the direction TO which the wind blows:
            u = - speed * sin(theta_rad)   [Eastward positive, Westward negative]
            v = - speed * cos(theta_rad)   [Northward positive, Southward negative]
        """
        rad = math.radians(direction_deg % 360.0)
        u = -speed_ms * math.sin(rad)
        v = -speed_ms * math.cos(rad)
        return round(u, 3), round(v, 3)

    def normalize_wind_speed(self, raw_speed: float, raw_unit: Optional[str] = "m/s") -> float:
        """Ensure wind speed is strictly in meters per second (m/s)."""
        if raw_unit and "km" in raw_unit.lower():
            # 1 km/h = 1000m / 3600s = 1/3.6 m/s
            return round(raw_speed / 3.6, 3)
        return round(raw_speed, 3)

    def parse_timestamp(self, raw_time: str, source_tz: str = "UTC") -> Optional[datetime]:
        """Parse ISO timestamp and normalize to timezone-aware UTC datetime."""
        if not raw_time:
            return None
        try:
            # If string ends with Z or has offset
            if "Z" in raw_time or "+" in raw_time or "-" in raw_time[10:]:
                dt = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                return dt.astimezone(timezone.utc)
            # Naive ISO string (e.g. "2026-09-13T00:00")
            dt = datetime.fromisoformat(raw_time)
            # Default to UTC if unspecified or treat as source_tz
            dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError) as e:
            logger.debug(f"Could not parse weather timestamp '{raw_time}': {e}")
            return None

    def normalize_hourly_step(
        self,
        time_str: str,
        step_data: Dict[str, Any],
        location_meta: Dict[str, Any],
        units_meta: Optional[Dict[str, str]] = None,
        retrieved_at: Optional[datetime] = None,
    ) -> WeatherNormalizationResult:
        """Normalize a single hourly time-step."""
        retrieved_at = retrieved_at or datetime.now(timezone.utc)
        units = units_meta or {}

        # 1. Parse and validate timestamp
        dt = self.parse_timestamp(time_str, source_tz=location_meta.get("timezone", "UTC"))
        if not dt:
            return WeatherNormalizationResult(
                is_valid=False,
                rejection_reason=f"invalid_timestamp: '{time_str}'",
                raw_reading=step_data,
            )

        # 2. Coordinates
        lat = location_meta.get("latitude")
        lon = location_meta.get("longitude")
        if lat is None or lon is None:
            return WeatherNormalizationResult(
                is_valid=False,
                rejection_reason="missing_coordinates",
                raw_reading=step_data,
            )

        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except (ValueError, TypeError):
            return WeatherNormalizationResult(
                is_valid=False,
                rejection_reason=f"non_numeric_coordinates: lat={lat}, lon={lon}",
                raw_reading=step_data,
            )

        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
            return WeatherNormalizationResult(
                is_valid=False,
                rejection_reason=f"coordinates_out_of_bounds: lat={lat_f}, lon={lon_f}",
                raw_reading=step_data,
            )

        # 3. Required physical fields: check for missing/null values
        req_fields = [
            "temperature_2m",
            "relative_humidity_2m",
            "surface_pressure",
            "wind_speed_10m",
            "wind_direction_10m",
        ]
        for f in req_fields:
            if step_data.get(f) is None:
                return WeatherNormalizationResult(
                    is_valid=False,
                    rejection_reason=f"missing_required_variable: '{f}'",
                    raw_reading=step_data,
                )

        try:
            temp_c = float(step_data["temperature_2m"])
            rh_pct = float(step_data["relative_humidity_2m"])
            press_hpa = float(step_data["surface_pressure"])
            raw_ws = float(step_data["wind_speed_10m"])
            wd_deg = float(step_data["wind_direction_10m"])
        except (ValueError, TypeError) as e:
            return WeatherNormalizationResult(
                is_valid=False,
                rejection_reason=f"non_numeric_variable_value: {e}",
                raw_reading=step_data,
            )

        # 4. Normalize wind speed to m/s
        ws_unit = units.get("wind_speed_10m", "m/s")
        ws_ms = self.normalize_wind_speed(raw_ws, ws_unit)

        # 5. Compute Cartesian components u and v
        wind_u, wind_v = self.compute_wind_components(ws_ms, wd_deg)

        # 6. Optional variables (preserve nulls, do NOT substitute 0 for missing BLH)
        blh_val = step_data.get("boundary_layer_height")
        blh_m = float(blh_val) if blh_val is not None else None

        precip_val = step_data.get("precipitation")
        precip_mm = float(precip_val) if precip_val is not None else 0.0

        # 7. Build Canonical WeatherObservation
        ts_slug = dt.strftime("%Y%m%d%H%M")
        weather_id = f"weather-om-{lat_f:.4f}-{lon_f:.4f}-{ts_slug}"
        loc_address = location_meta.get("city") or f"Open-Meteo Grid ({lat_f:.2f}, {lon_f:.2f})"

        location_obj = Location(
            latitude=lat_f,
            longitude=lon_f,
            address=loc_address,
        )

        try:
            obs = WeatherObservation(
                weather_id=weather_id,
                timestamp=dt,
                location=location_obj,
                temperature_c=temp_c,
                relative_humidity_pct=rh_pct,
                surface_pressure_hpa=press_hpa,
                wind_speed_ms=ws_ms,
                wind_direction_deg=wd_deg,
                precipitation_mm=precip_mm,
                boundary_layer_height_m=blh_m,
                wind_u_ms=wind_u,
                wind_v_ms=wind_v,
                source="Open-Meteo",
                retrieved_at=retrieved_at,
                source_url="https://api.open-meteo.com/v1/forecast",
                normalization_version=self.version,
                raw_payload={
                    "raw_time": time_str,
                    "raw_step": step_data,
                    "units": units,
                },
            )
            return WeatherNormalizationResult(is_valid=True, observation=obs, raw_reading=step_data)
        except Exception as e:
            return WeatherNormalizationResult(
                is_valid=False,
                rejection_reason=f"schema_validation_error: {e}",
                raw_reading=step_data,
            )

    def normalize_response(
        self,
        raw_payload: Dict[str, Any],
        retrieved_at: Optional[datetime] = None,
    ) -> List[WeatherNormalizationResult]:
        """Normalize all hourly timesteps contained in an Open-Meteo response."""
        retrieved_at = retrieved_at or datetime.now(timezone.utc)

        # Support both wrapped metadata envelope and raw API response
        api_data = raw_payload.get("raw_response") if "raw_response" in raw_payload else raw_payload

        hourly_block = api_data.get("hourly", {})
        times = hourly_block.get("time", [])
        units_meta = api_data.get("hourly_units", {})

        location_meta = {
            "latitude": api_data.get("latitude"),
            "longitude": api_data.get("longitude"),
            "elevation": api_data.get("elevation"),
            "timezone": api_data.get("timezone", "UTC"),
            "city": raw_payload.get("metadata", {}).get("target_location", {}).get("city"),
        }

        results: List[WeatherNormalizationResult] = []
        for i, time_str in enumerate(times):
            step_data: Dict[str, Any] = {}
            for var_name, values_array in hourly_block.items():
                if var_name == "time":
                    continue
                if i < len(values_array):
                    step_data[var_name] = values_array[i]
                else:
                    step_data[var_name] = None

            norm_res = self.normalize_hourly_step(
                time_str=time_str,
                step_data=step_data,
                location_meta=location_meta,
                units_meta=units_meta,
                retrieved_at=retrieved_at,
            )
            results.append(norm_res)

        return results
