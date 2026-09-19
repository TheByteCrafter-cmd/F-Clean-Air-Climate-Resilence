"""
VayuDrishti — Live Air Quality Data Provider (Phase 1E-J2E.3.2)

Controlled live air quality telemetry retrieval for Anand Vihar 8118 using OpenAQ v3 API
hourly sensor endpoint (/sensors/{id}/hours). Supports LIVE and OFFLINE_TEST modes with
credential-safe logging and freshness auditing.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from backend.ingestion.exceptions import (
    AuthenticationError,
    MissingCredentialError,
    OpenAQAPIError,
)
from backend.ingestion.openaq_client import OpenAQClient
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

ANAND_VIHAR_LOCATION_ID = 8118
CANONICAL_STATION_ID = "ANAND_VIHAR_8118"


class LiveAirQualityProvider:
    """
    Retrieves recent PM2.5 hourly time-series from OpenAQ v3 for Anand Vihar 8118.
    Prefers GET /v3/sensors/{sensor_id}/hours for building the 24h+ lag context.
    """

    def __init__(
        self,
        openaq_client: Optional[OpenAQClient] = None,
        lookback_hours: float = 30.0,
        max_aq_age_minutes: float = 120.0,
        mode: str = "LIVE",
    ):
        self.client = openaq_client or OpenAQClient()
        self.lookback_hours = max(30.0, float(lookback_hours))
        self.max_aq_age_minutes = float(max_aq_age_minutes)
        self.mode = mode.upper()

    def discover_pm25_sensor(self, location_id: int = ANAND_VIHAR_LOCATION_ID) -> Optional[int]:
        """Discovers the active PM2.5 sensor associated with location_id."""
        try:
            sensors_meta = self.client.discover_sensors(location_id)
            for s in sensors_meta:
                param = str(s.get("parameter", "")).lower()
                if param in ["pm25", "pm2.5"]:
                    sensor_id = s.get("sensor_id")
                    if sensor_id:
                        logger.info(f"Resolved PM2.5 sensor {sensor_id} for location {location_id}")
                        return int(sensor_id)
            # Fallback to first sensor if parameter string missing
            if sensors_meta and sensors_meta[0].get("sensor_id"):
                return int(sensors_meta[0]["sensor_id"])
        except Exception as e:
            logger.warning(f"Could not discover sensors for location {location_id}: {e}")
        return None

    def fetch_recent_pm25_history(
        self,
        prediction_timestamp: Optional[str] = None,
        fixture_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves recent PM2.5 hourly records for Anand Vihar 8118.

        If mode == "OFFLINE_TEST", uses provided fixture_records or cached telemetry without network calls.
        If mode == "LIVE", queries OpenAQ v3 API /sensors/{sensor_id}/hours.
        """
        reasons: List[str] = []

        # Determine reference timestamp
        now_utc = datetime.now(timezone.utc)
        ref_dt = now_utc
        if prediction_timestamp:
            try:
                parsed_req_dt = parse_utc_timestamp(prediction_timestamp)
                if parsed_req_dt > now_utc + timedelta(minutes=5):
                    return {
                        "status": "INVALID_INPUT",
                        "records": [],
                        "sensor_id": None,
                        "location_id": ANAND_VIHAR_LOCATION_ID,
                        "source_age_minutes": None,
                        "latest_timestamp": None,
                        "reasons": [f"Requested prediction_timestamp '{prediction_timestamp}' is in the future."],
                    }
                ref_dt = parsed_req_dt
            except Exception as e:
                return {
                    "status": "INVALID_INPUT",
                    "records": [],
                    "sensor_id": None,
                    "location_id": ANAND_VIHAR_LOCATION_ID,
                    "source_age_minutes": None,
                    "latest_timestamp": None,
                    "reasons": [f"Invalid prediction_timestamp '{prediction_timestamp}': {e}"],
                }

        # Offline / Fixture mode execution
        if self.mode == "OFFLINE_TEST":
            records = fixture_records or []
            if not records:
                return {
                    "status": "LIVE_AQ_UNAVAILABLE",
                    "records": [],
                    "sensor_id": None,
                    "location_id": ANAND_VIHAR_LOCATION_ID,
                    "source_age_minutes": None,
                    "latest_timestamp": None,
                    "reasons": ["OFFLINE_TEST mode specified but no fixture_records provided."],
                }

            # Filter <= ref_dt
            valid_recs = []
            for r in records:
                raw_t = r.get("timestamp") or r.get("datetime")
                if not raw_t:
                    continue
                try:
                    rec_dt = parse_utc_timestamp(raw_t)
                    if rec_dt <= ref_dt:
                        valid_recs.append((rec_dt, r))
                except ValueError:
                    continue

            if not valid_recs:
                return {
                    "status": "LIVE_AQ_UNAVAILABLE",
                    "records": [],
                    "sensor_id": None,
                    "location_id": ANAND_VIHAR_LOCATION_ID,
                    "source_age_minutes": None,
                    "latest_timestamp": None,
                    "reasons": ["No offline records available at or before target timestamp."],
                }

            valid_recs.sort(key=lambda x: x[0])
            latest_dt = valid_recs[-1][0]
            age_min = (ref_dt - latest_dt).total_seconds() / 60.0

            if age_min > self.max_aq_age_minutes:
                status = "LIVE_AQ_STALE"
                reasons.append(f"AQ source age = {round(age_min, 1)} minutes > {self.max_aq_age_minutes} minute freshness threshold")
            else:
                status = "READY"

            formatted_records = [r[1] for r in valid_recs]
            return {
                "status": status,
                "records": formatted_records,
                "sensor_id": 8118,
                "location_id": ANAND_VIHAR_LOCATION_ID,
                "source_age_minutes": round(age_min, 1),
                "latest_timestamp": latest_dt.isoformat().replace("+00:00", "Z"),
                "reasons": reasons,
            }

        # Live Mode Execution — Credential Check
        if not self.client.has_credentials():
            logger.warning("OPENAQ_API_KEY missing. Live AQ retrieval unavailable.")
            return {
                "status": "LIVE_AQ_UNAVAILABLE",
                "records": [],
                "sensor_id": None,
                "location_id": ANAND_VIHAR_LOCATION_ID,
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": ["OPENAQ_API_KEY is not configured in environment."],
            }

        sensor_id = self.discover_pm25_sensor(ANAND_VIHAR_LOCATION_ID)
        if not sensor_id:
            logger.warning(f"No active PM2.5 sensor found for location {ANAND_VIHAR_LOCATION_ID}")
            return {
                "status": "LIVE_AQ_UNAVAILABLE",
                "records": [],
                "sensor_id": None,
                "location_id": ANAND_VIHAR_LOCATION_ID,
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": [f"No valid PM2.5 sensor discovered for location {ANAND_VIHAR_LOCATION_ID}."],
            }

        # Calculate time window for GET /sensors/{sensor_id}/hours
        date_from_dt = ref_dt - timedelta(hours=self.lookback_hours)
        date_from_str = date_from_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        date_to_str = ref_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            raw_res = self.client.get_sensor_measurements(
                sensors_id=sensor_id,
                date_from=date_from_str,
                date_to=date_to_str,
                limit=1000,
            )
            items = raw_res.get("results", [])
        except (AuthenticationError, MissingCredentialError) as e:
            logger.error(f"OpenAQ authentication failed: {e}")
            return {
                "status": "LIVE_AQ_UNAVAILABLE",
                "records": [],
                "sensor_id": sensor_id,
                "location_id": ANAND_VIHAR_LOCATION_ID,
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": ["OpenAQ authentication failed."],
            }
        except OpenAQAPIError as e:
            logger.error(f"OpenAQ API error: {e}")
            return {
                "status": "LIVE_AQ_UNAVAILABLE",
                "records": [],
                "sensor_id": sensor_id,
                "location_id": ANAND_VIHAR_LOCATION_ID,
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": [f"OpenAQ API query failed: {e}"],
            }
        except Exception as e:
            logger.error(f"Unexpected error retrieving OpenAQ telemetry: {e}")
            return {
                "status": "LIVE_AQ_UNAVAILABLE",
                "records": [],
                "sensor_id": sensor_id,
                "location_id": ANAND_VIHAR_LOCATION_ID,
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": [f"Unexpected OpenAQ retrieval error: {e}"],
            }

        if not items:
            return {
                "status": "LIVE_AQ_UNAVAILABLE",
                "records": [],
                "sensor_id": sensor_id,
                "location_id": ANAND_VIHAR_LOCATION_ID,
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": [f"No hourly PM2.5 measurements returned for sensor {sensor_id} in requested window."],
            }

        # Normalize and filter measurements
        normalized_records = []
        seen_timestamps = set()

        for item in items:
            period = item.get("period", {})
            dt_raw = (
                period.get("datetimeEnd", {}).get("utc")
                if isinstance(period.get("datetimeEnd"), dict)
                else item.get("datetime", {}).get("utc")
            )
            if not dt_raw:
                dt_raw = item.get("datetime")

            if not dt_raw:
                continue

            try:
                dt_parsed = parse_utc_timestamp(dt_raw)
            except ValueError:
                continue

            # Strict leakage check (<= ref_dt)
            if dt_parsed > ref_dt:
                continue

            val = item.get("value")
            if val is None:
                continue

            try:
                val_float = float(val)
                if val_float < 0.0:  # Ignore physical invalid values if any
                    continue
            except (ValueError, TypeError):
                continue

            iso_ts = dt_parsed.isoformat().replace("+00:00", "Z")
            if iso_ts in seen_timestamps:
                continue
            seen_timestamps.add(iso_ts)

            normalized_records.append(
                {
                    "station_id": CANONICAL_STATION_ID,
                    "location_id": ANAND_VIHAR_LOCATION_ID,
                    "sensor_id": sensor_id,
                    "timestamp": iso_ts,
                    "parsed_dt": dt_parsed,
                    "pollutant": "PM2.5",
                    "value": round(val_float, 2),
                    "unit": "µg/m³",
                    "source": "OpenAQ_v3_Live",
                }
            )

        if not normalized_records:
            return {
                "status": "LIVE_AQ_UNAVAILABLE",
                "records": [],
                "sensor_id": sensor_id,
                "location_id": ANAND_VIHAR_LOCATION_ID,
                "source_age_minutes": None,
                "latest_timestamp": None,
                "reasons": ["No valid non-negative PM2.5 observations remained after filtering."],
            }

        # Sort chronologically
        normalized_records.sort(key=lambda x: x["parsed_dt"])
        latest_dt = normalized_records[-1]["parsed_dt"]
        age_min = (ref_dt - latest_dt).total_seconds() / 60.0

        # Clean parsed_dt internal field before returning
        clean_records = []
        for rec in normalized_records:
            r_copy = dict(rec)
            r_copy.pop("parsed_dt", None)
            clean_records.append(r_copy)

        if age_min > self.max_aq_age_minutes:
            status = "LIVE_AQ_STALE"
            reasons.append(
                f"AQ source age = {round(age_min, 1)} minutes > {self.max_aq_age_minutes} minute freshness threshold"
            )
        else:
            status = "READY"

        return {
            "status": status,
            "records": clean_records,
            "sensor_id": sensor_id,
            "location_id": ANAND_VIHAR_LOCATION_ID,
            "source_age_minutes": round(age_min, 1),
            "latest_timestamp": latest_dt.isoformat().replace("+00:00", "Z"),
            "reasons": reasons,
        }
