"""
VayuDrishti — Historical Forecasting Data Acquisition & Alignment Engine

Provides controlled, reproducible historical air-quality (OpenAQ v3) and weather (Open-Meteo)
time-series retrieval, raw artifact preservation, canonical normalization, hourly continuity auditing,
and readiness evaluation for forecasting model training.
"""

import csv
import hashlib
import json
import logging
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.ingestion.exceptions import MissingCredentialError, OpenAQError
from backend.ingestion.openaq_client import OpenAQClient
from backend.ingestion.weather_client import OpenMeteoClient
from ml.src.forecasting.config import ForecastingConfig
from ml.src.forecasting.dataset_builder import ForecastingDatasetBuilder
from ml.src.forecasting.timestamp_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

# Representative Delhi Pilot Stations (CAAQMS locations)
DELHI_PILOT_STATIONS = [
    {"station_id": "ANAND_VIHAR_8118", "location_id": 8118, "latitude": 28.6476, "longitude": 77.3158, "name": "Anand Vihar, Delhi - DPCC"},
    {"station_id": "PUNJABI_BAGH_8122", "location_id": 8122, "latitude": 28.6740, "longitude": 77.1310, "name": "Punjabi Bagh, Delhi - DPCC"},
    {"station_id": "MANDIR_MARG_8125", "location_id": 8125, "latitude": 28.6364, "longitude": 77.2011, "name": "Mandir Marg, Delhi - DPCC"},
    {"station_id": "RK_PURAM_8124", "location_id": 8124, "latitude": 28.5632, "longitude": 77.1869, "name": "RK Puram, Delhi - DPCC"},
    {"station_id": "ITO_8120", "location_id": 8120, "latitude": 28.6286, "longitude": 77.2410, "name": "ITO, Delhi - CPCB"},
    {"station_id": "DHIER_PUR_8119", "location_id": 8119, "latitude": 28.7041, "longitude": 77.1925, "name": "Dheerpur, Delhi - IITM"},
]


class HistoricalForecastingIngestionPipeline:
    """Acquires, normalizes, audits, and persists historical telemetry for forecasting."""

    def __init__(
        self,
        data_root: Optional[Union[str, Path]] = None,
        config: Optional[ForecastingConfig] = None,
        openaq_client: Optional[OpenAQClient] = None,
        weather_client: Optional[OpenMeteoClient] = None,
    ):
        self.config = config or ForecastingConfig()
        self.data_root = Path(data_root) if data_root else Path(os.getcwd()) / "data"

        self.raw_dir = self.data_root / "raw" / "forecasting"
        self.processed_dir = self.data_root / "processed" / "forecasting"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        self.openaq_client = openaq_client or OpenAQClient()
        self.weather_client = weather_client or OpenMeteoClient()

    def fetch_and_process_history(
        self,
        history_days: int = 30,
        stations: Optional[List[Dict[str, Any]]] = None,
        end_timestamp_iso: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes historical data acquisition workflow:
        1. Query parameters & date range computation
        2. OpenAQ historical retrieval & raw preservation
        3. Open-Meteo historical weather retrieval & raw preservation
        4. Canonical normalization & hourly continuity auditing
        5. Processed artifact persistence
        6. Dataset construction & readiness assessment
        """
        pilot_stations = stations or DELHI_PILOT_STATIONS

        # Compute date range (UTC)
        if end_timestamp_iso:
            end_dt = parse_utc_timestamp(end_timestamp_iso)
        else:
            end_dt = datetime.now(timezone.utc)

        start_dt = end_dt - timedelta(days=history_days)
        start_iso = start_dt.isoformat().replace("+00:00", "Z")
        end_iso = end_dt.isoformat().replace("+00:00", "Z")
        retrieval_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        raw_aq_records: List[Dict[str, Any]] = []
        openaq_success = False
        openaq_error_msg: Optional[str] = None

        # 1. Fetch Historical OpenAQ Data
        if self.openaq_client.has_credentials():
            try:
                for st in pilot_stations:
                    loc_id = st["location_id"]
                    try:
                        res = self.openaq_client.get_location_measurements(
                            locations_id=loc_id,
                            date_from=start_iso[:10],
                            date_to=end_iso[:10],
                            limit=1000,
                        )
                        results = res.get("results", [])
                        for item in results:
                            item["_station_meta"] = st
                            raw_aq_records.append(item)
                    except OpenAQError as err:
                        logger.warning(f"Could not fetch historical OpenAQ for location {loc_id}: {err}")
                openaq_success = len(raw_aq_records) > 0
            except Exception as e:
                openaq_error_msg = str(e)
                logger.warning(f"OpenAQ historical retrieval failed: {e}")
        else:
            openaq_error_msg = "OPENAQ_API_KEY is not configured in the environment."
            logger.info("OPENAQ_API_KEY not configured. Falling back to existing local processed data/fixtures.")

        # Preserve Raw OpenAQ Snapshot
        aq_raw_filename = f"openaq_history_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        aq_raw_path = self.raw_dir / aq_raw_filename
        raw_aq_envelope = {
            "metadata": {
                "source": "OpenAQ REST API v3",
                "retrieved_at": retrieval_iso,
                "start_utc": start_iso,
                "end_utc": end_iso,
                "history_days": history_days,
                "stations": [s["station_id"] for s in pilot_stations],
                "record_count": len(raw_aq_records),
                "has_credentials": self.openaq_client.has_credentials(),
                "error": openaq_error_msg,
            },
            "raw_records": raw_aq_records,
        }
        with open(aq_raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_aq_envelope, f, indent=2)

        # 2. Fetch Historical Open-Meteo Weather Data
        raw_wx_response: Dict[str, Any] = {}
        try:
            raw_wx_response = self.weather_client.fetch_weather(
                latitude=28.6139,
                longitude=77.2090,
                start_date=start_iso[:10],
                end_date=end_iso[:10],
            )
        except Exception as e:
            logger.warning(f"Open-Meteo historical weather fetch failed: {e}")
            raw_wx_response = {"error": str(e)}

        wx_raw_filename = f"weather_history_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        wx_raw_path = self.raw_dir / wx_raw_filename
        raw_wx_envelope = {
            "metadata": {
                "source": "Open-Meteo Historical Archive API",
                "retrieved_at": retrieval_iso,
                "start_utc": start_iso,
                "end_utc": end_iso,
                "coordinate_strategy": "Representative Regional Weather Context (Delhi NCR 28.6139 N, 77.2090 E)",
            },
            "raw_response": raw_wx_response,
        }
        with open(wx_raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_wx_envelope, f, indent=2)

        # 3. Normalize Air Quality Records
        normalized_aq = self.normalize_air_quality(raw_aq_records, pilot_stations)

        # 4. Normalize Weather Records
        normalized_wx = self.normalize_weather(raw_wx_response)

        # 5. Calculate Hourly Continuity & Station Quality Metrics
        station_quality = self.calculate_station_continuity(
            normalized_aq, pilot_stations, start_dt, end_dt
        )

        # 6. Save Processed Historical Datasets
        aq_csv_path = self.processed_dir / "historical_air_quality.csv"
        wx_csv_path = self.processed_dir / "historical_weather.csv"

        self._write_csv(aq_csv_path, normalized_aq)
        self._write_csv(wx_csv_path, normalized_wx)

        # 7. Run Dataset Builder & Readiness Assessor over Processed Data
        builder = ForecastingDatasetBuilder(data_root=self.data_root, config=self.config)
        dataset_summary = builder.build_and_save(
            custom_openaq_records=normalized_aq if normalized_aq else None,
            custom_weather_records=normalized_wx if normalized_wx else None,
        )

        # 8. Build Historical Manifest
        manifest_path = self.processed_dir / "forecasting_data_manifest.json"
        manifest = {
            "dataset_version": "1.0-historical-foundation",
            "retrieval_timestamp": retrieval_iso,
            "air_quality_source": "OpenAQ REST API v3",
            "weather_source": "Open-Meteo Historical API",
            "start_utc": start_iso,
            "end_utc": end_iso,
            "history_days": history_days,
            "air_quality_rows": len(normalized_aq),
            "weather_rows": len(normalized_wx),
            "station_count": len(pilot_stations),
            "stations": [s["station_id"] for s in pilot_stations],
            "weather_variables": [
                "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
                "wind_direction_10m", "wind_u", "wind_v", "surface_pressure", "boundary_layer_height"
            ],
            "unit_conventions": {"pollutant": "µg/m³", "temperature": "°C", "wind_speed": "m/s"},
            "raw_artifact_references": [
                str(aq_raw_path.relative_to(self.data_root.parent)).replace("\\", "/"),
                str(wx_raw_path.relative_to(self.data_root.parent)).replace("\\", "/"),
            ],
            "readiness_status": dataset_summary["readiness_report"]["readiness_status"],
            "training_ready": dataset_summary["readiness_report"]["training_ready"],
            "schema_version": "1.0",
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # 9. Build Quality Report
        quality_path = self.processed_dir / "forecasting_data_quality.json"
        quality_report = {
            "retrieval_timestamp": retrieval_iso,
            "total_raw_openaq_records": len(raw_aq_records),
            "total_normalized_aq_rows": len(normalized_aq),
            "total_normalized_weather_rows": len(normalized_wx),
            "station_continuity": station_quality,
            "overall_metrics": {
                "openaq_success": openaq_success,
                "openaq_error": openaq_error_msg,
                "overall_readiness_status": dataset_summary["readiness_report"]["readiness_status"],
            }
        }
        with open(quality_path, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2)

        return {
            "start_utc": start_iso,
            "end_utc": end_iso,
            "stations_selected": [s["station_id"] for s in pilot_stations],
            "air_quality_rows": len(normalized_aq),
            "weather_rows": len(normalized_wx),
            "station_continuity": station_quality,
            "dataset_summary": dataset_summary,
            "readiness_status": dataset_summary["readiness_report"]["readiness_status"],
            "training_ready": dataset_summary["readiness_report"]["training_ready"],
            "manifest_path": str(manifest_path),
        }

    def normalize_air_quality(
        self,
        raw_records: List[Dict[str, Any]],
        pilot_stations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Normalizes OpenAQ raw records into canonical format."""
        if not raw_records:
            return []

        st_map = {s["location_id"]: s for s in pilot_stations}
        normalized: List[Dict[str, Any]] = []
        seen_keys: set = set()

        for r in raw_records:
            loc_id = r.get("location_id") or (r.get("_station_meta", {}).get("location_id"))
            meta = st_map.get(loc_id, r.get("_station_meta", {}))

            st_id = meta.get("station_id") or f"STATION_{loc_id}"
            lat = meta.get("latitude") or (r.get("coordinates", {}).get("latitude"))
            lon = meta.get("longitude") or (r.get("coordinates", {}).get("longitude"))
            st_name = meta.get("name") or str(st_id)

            raw_t = r.get("period", {}).get("datetimeFrom", {}).get("utc") or r.get("datetime") or r.get("timestamp")
            if not raw_t:
                continue

            try:
                dt = parse_utc_timestamp(raw_t)
                iso_utc = dt.isoformat().replace("+00:00", "Z")
            except ValueError:
                continue

            pol = str(r.get("parameter", {}).get("name") or r.get("pollutant", "PM2.5")).upper().replace(".", "").replace(" ", "")
            if pol not in ["PM25", "PM2.5", "PM10"]:
                continue

            try:
                val = float(r.get("value", -1.0))
            except (ValueError, TypeError):
                continue

            if val < 0.0 or lat is None or lon is None:
                continue

            dedup_key = (st_id, pol, iso_utc)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            normalized.append({
                "station_id": st_id,
                "timestamp": iso_utc,
                "parsed_timestamp": dt,
                "latitude": round(float(lat), 4),
                "longitude": round(float(lon), 4),
                "station_name": st_name,
                "pollutant": "PM2.5" if pol in ["PM25", "PM2.5"] else "PM10",
                "value": round(val, 2),
                "unit": "µg/m³",
                "source": "OpenAQ_v3",
            })

        normalized.sort(key=lambda x: (x["station_id"], x["pollutant"], x["parsed_timestamp"]))
        return normalized

    def normalize_weather(self, raw_wx_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalizes Open-Meteo historical weather API response into hourly rows."""
        if not raw_wx_response or "hourly" not in raw_wx_response:
            return []

        hourly = raw_wx_response["hourly"]
        times = hourly.get("time", [])
        temps = hourly.get("temperature_2m", [])
        rhs = hourly.get("relative_humidity_2m", [])
        w_spds = hourly.get("wind_speed_10m", [])
        w_dirs = hourly.get("wind_direction_10m", [])
        pressures = hourly.get("surface_pressure", [])
        blhs = hourly.get("boundary_layer_height", [])

        normalized: List[Dict[str, Any]] = []

        for i, raw_t in enumerate(times):
            try:
                dt = parse_utc_timestamp(str(raw_t))
                iso_utc = dt.isoformat().replace("+00:00", "Z")
            except ValueError:
                continue

            temp = temps[i] if i < len(temps) else None
            rh = rhs[i] if i < len(rhs) else None
            w_spd = w_spds[i] if i < len(w_spds) else None
            w_dir = w_dirs[i] if i < len(w_dirs) else None
            press = pressures[i] if i < len(pressures) else None
            blh = blhs[i] if i < len(blhs) else None

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

            normalized.append({
                "timestamp": iso_utc,
                "parsed_timestamp": dt,
                "latitude": 28.6139,
                "longitude": 77.2090,
                "temperature_2m": round(float(temp), 2) if temp is not None else None,
                "relative_humidity_2m": round(float(rh), 2) if rh is not None else None,
                "wind_speed_10m": round(float(w_spd), 2) if w_spd is not None else None,
                "wind_direction_10m": round(float(w_dir), 2) if w_dir is not None else None,
                "wind_u": u_comp,
                "wind_v": v_comp,
                "surface_pressure": round(float(press), 2) if press is not None else None,
                "boundary_layer_height": round(float(blh), 2) if blh is not None else None,
            })

        normalized.sort(key=lambda x: x["parsed_timestamp"])
        return normalized

    def calculate_station_continuity(
        self,
        normalized_aq: List[Dict[str, Any]],
        pilot_stations: List[Dict[str, Any]],
        start_dt: datetime,
        end_dt: datetime,
    ) -> Dict[str, Dict[str, Any]]:
        """Calculates exact hourly continuity, missing hours, and pollutant coverage per station."""
        expected_hours = max(1, int(round((end_dt - start_dt).total_seconds() / 3600.0)))

        station_obs: Dict[str, List[Dict[str, Any]]] = {s["station_id"]: [] for s in pilot_stations}
        for r in normalized_aq:
            st_id = r["station_id"]
            if st_id in station_obs:
                station_obs[st_id].append(r)

        continuity_report: Dict[str, Dict[str, Any]] = {}

        for st in pilot_stations:
            st_id = st["station_id"]
            obs = station_obs.get(st_id, [])

            if not obs:
                continuity_report[st_id] = {
                    "station_name": st["name"],
                    "total_observations": 0,
                    "first_timestamp": None,
                    "last_timestamp": None,
                    "expected_hourly_timestamps": expected_hours,
                    "observed_hourly_timestamps": 0,
                    "continuity_percentage": 0.0,
                    "missing_hour_count": expected_hours,
                    "pm25_count": 0,
                    "pm10_count": 0,
                    "pm25_min": None,
                    "pm25_max": None,
                    "pm25_median": None,
                }
                continue

            dts = [r["parsed_timestamp"] if "parsed_timestamp" in r else parse_utc_timestamp(r["timestamp"]) for r in obs]
            min_ts = min(dts).isoformat().replace("+00:00", "Z")
            max_ts = max(dts).isoformat().replace("+00:00", "Z")

            unique_hours = len({dt.strftime("%Y-%m-%d %H:00") for dt in dts})
            pm25_vals = [r["value"] for r in obs if r["pollutant"] in ["PM2.5", "PM25"]]
            pm10_vals = [r["value"] for r in obs if r["pollutant"] == "PM10"]

            cont_pct = round((unique_hours / expected_hours) * 100.0, 2)
            missing_hours = max(0, expected_hours - unique_hours)

            continuity_report[st_id] = {
                "station_name": st["name"],
                "total_observations": len(obs),
                "first_timestamp": min_ts,
                "last_timestamp": max_ts,
                "expected_hourly_timestamps": expected_hours,
                "observed_hourly_timestamps": unique_hours,
                "continuity_percentage": cont_pct,
                "missing_hour_count": missing_hours,
                "pm25_count": len(pm25_vals),
                "pm10_count": len(pm10_vals),
                "pm25_min": min(pm25_vals) if pm25_vals else None,
                "pm25_max": max(pm25_vals) if pm25_vals else None,
                "pm25_median": round(float(median(pm25_vals)), 2) if pm25_vals else None,
            }

        return continuity_report

    def _write_csv(self, file_path: Path, records: List[Dict[str, Any]]) -> None:
        """Helper to write normalized records to CSV file."""
        if not records:
            with open(file_path, "w", newline="", encoding="utf-8") as f:
                f.write("station_id,timestamp,latitude,longitude,station_name,pollutant,value,unit,source\n")
            return

        clean_records = []
        for r in records:
            r_copy = dict(r)
            r_copy.pop("parsed_timestamp", None)
            clean_records.append(r_copy)

        fieldnames = list(clean_records[0].keys())
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(clean_records)
