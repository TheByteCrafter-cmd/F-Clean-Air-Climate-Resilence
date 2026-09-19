"""
VayuDrishti — Live Weather Data Provider (Phase 1E-J2E.3.2)

Controlled live weather telemetry retrieval for Anand Vihar 8118 using Open-Meteo API.
Derives wind Cartesian vector components (u, v) using J1 meteorological convention and enforces
the 60-minute max weather age threshold.
"""

import math
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.ingestion.weather_client import OpenMeteoClient
from ml.src.forecasting.historical_ingestion import DELHI_PILOT_STATIONS
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

ANAND_VIHAR_META = next(st for st in DELHI_PILOT_STATIONS if st["station_id"] == "ANAND_VIHAR_8118")
CANONICAL_LATITUDE = float(ANAND_VIHAR_META["latitude"])
CANONICAL_LONGITUDE = float(ANAND_VIHAR_META["longitude"])


class LiveWeatherProvider:
    """
    Retrieves recent hourly weather telemetry from Open-Meteo API for Anand Vihar coordinates.
    Calculates meteorological wind u/v components and enforces the 60-minute weather staleness limit.
    """

    def __init__(
        self,
        weather_client: Optional[OpenMeteoClient] = None,
        max_weather_age_minutes: float = 60.0,
        mode: str = "LIVE",
    ):
        self.client = weather_client or OpenMeteoClient()
        self.max_weather_age_minutes = float(max_weather_age_minutes)
        self.mode = mode.upper()

    def fetch_recent_weather(
        self,
        prediction_timestamp: Optional[str] = None,
        fixture_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves recent hourly weather context for Anand Vihar.

        If mode == "OFFLINE_TEST", uses provided fixture_records without network calls.
        If mode == "LIVE", queries Open-Meteo HTTP API.
        """
        reasons: List[str] = []
        now_utc = datetime.now(timezone.utc)
        ref_dt = parse_utc_timestamp(prediction_timestamp) if prediction_timestamp else now_utc

        # Offline / Fixture mode execution
        if self.mode == "OFFLINE_TEST":
            records = fixture_records or []
            if not records:
                return {
                    "status": "WEATHER_STALE",
                    "records": [],
                    "source_age_minutes": None,
                    "latest_timestamp": None,
                    "reasons": ["OFFLINE_TEST mode specified but no fixture_records provided."],
                }

            valid_recs = []
            for r in records:
                raw_t = r.get("timestamp") or r.get("datetime")
                if not raw_t:
                    continue
                try:
                    w_dt = parse_utc_timestamp(raw_t)
                    if w_dt <= ref_dt:
                        valid_recs.append((w_dt, r))
                except ValueError:
                    continue

            if not valid_recs:
                return {
                    "status": "WEATHER_STALE",
                    "records": [],
                    "source_age_minutes": None,
                    "latest_timestamp": None,
                    "reasons": ["No offline weather records available at or before target timestamp."],
                }

            valid_recs.sort(key=lambda x: x[0])
            latest_dt = valid_recs[-1][0]
            age_min = (ref_dt - latest_dt).total_seconds() / 60.0

            if age_min > self.max_weather_age_minutes:
                status = "WEATHER_STALE"
                reasons.append(f"weather observation age = {round(age_min, 1)} minutes > {self.max_weather_age_minutes} minute threshold")
            else:
                status = "READY"

            formatted_records = [r[1] for r in valid_recs]
            return {
                "status": status,
                "records": formatted_records,
                "source_age_minutes": round(age_min, 1),
                "latest_timestamp": latest_dt.isoformat().replace("+00:00", "Z"),
                "reasons": reasons,
            }

        # Live Mode Execution — Query Open-Meteo
        try:
            raw_res = self.client.fetch_weather(
                latitude=CANONICAL_LATITUDE,
                longitude=CANONICAL_LONGITUDE,
                past_days=1,
                forecast_days=1,
            )
            parsed_steps = self.client.parse_hourly_response(raw_res)
        except Exception as e:
            logger.error(f"Open-Meteo weather fetch error: {e}")
            return {
                "status": "WEATHER_STALE",
                "records": [],
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": [f"Open-Meteo weather query failed: {e}"],
            }

        if not parsed_steps:
            return {
                "status": "WEATHER_STALE",
                "records": [],
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": ["No hourly weather records returned by Open-Meteo."],
            }

        # Filter & calculate u, v wind vector components (<= ref_dt)
        normalized_records = []
        for step in parsed_steps:
            raw_t = step.get("timestamp") or step.get("datetime")
            if not raw_t:
                continue
            try:
                w_dt = parse_utc_timestamp(raw_t)
            except ValueError:
                continue

            # Exclude future weather (> ref_dt)
            if w_dt > ref_dt:
                continue

            w_spd = step.get("wind_speed_10m")
            w_dir = step.get("wind_direction_10m")

            u_comp = None
            v_comp = None
            if w_spd is not None and w_dir is not None:
                try:
                    spd = float(w_spd)
                    deg = float(w_dir)
                    rad = math.radians(deg)
                    u_comp = round(-spd * math.sin(rad), 2)
                    v_comp = round(-spd * math.cos(rad), 2)
                except (ValueError, TypeError):
                    pass

            rec = {
                "timestamp": w_dt.isoformat().replace("+00:00", "Z"),
                "parsed_dt": w_dt,
                "temperature_2m": step.get("temperature_2m"),
                "relative_humidity_2m": step.get("relative_humidity_2m"),
                "wind_speed_10m": w_spd,
                "wind_direction_10m": w_dir,
                "wind_u": u_comp,
                "wind_v": v_comp,
                "surface_pressure": step.get("surface_pressure"),
                "boundary_layer_height": step.get("boundary_layer_height"),
                "source": "Open-Meteo_Live",
            }
            normalized_records.append(rec)

        if not normalized_records:
            return {
                "status": "WEATHER_STALE",
                "records": [],
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": ["No past weather observations available at or before target timestamp."],
            }

        normalized_records.sort(key=lambda x: x["parsed_dt"])
        latest_dt = normalized_records[-1]["parsed_dt"]
        age_min = (ref_dt - latest_dt).total_seconds() / 60.0

        clean_records = []
        for r in normalized_records:
            r_copy = dict(r)
            r_copy.pop("parsed_dt", None)
            clean_records.append(r_copy)

        if age_min > self.max_weather_age_minutes:
            status = "WEATHER_STALE"
            reasons.append(
                f"weather observation age = {round(age_min, 1)} minutes > {self.max_weather_age_minutes} minute threshold"
            )
        else:
            status = "READY"

        return {
            "status": status,
            "records": clean_records,
            "source_age_minutes": round(age_min, 1),
            "latest_timestamp": latest_dt.isoformat().replace("+00:00", "Z"),
            "reasons": reasons,
        }
