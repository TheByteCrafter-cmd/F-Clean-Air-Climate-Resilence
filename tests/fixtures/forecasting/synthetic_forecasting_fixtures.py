"""
SYNTHETIC FORECASTING TEST FIXTURES — TEST ONLY

Contains deterministic synthetic multi-timestamp observation records for 2 fake stations
(syn_st_01 and syn_st_02) over a 24-hour window, with weather records and an intentional missing value.

CAUTION:
These synthetic fixtures are for unit and integration testing ONLY.
DO NOT use these synthetic fixtures for real model training or accuracy claims.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def get_synthetic_forecasting_records(
    base_time_iso: str = "2026-03-15T00:00:00Z",
    num_hours: int = 24,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Generates deterministic synthetic multi-hour time-series observation data for 2 fake stations.

    Includes:
    - 2 stations: syn_st_01 (lat 28.61, lon 77.20) and syn_st_02 (lat 28.65, lon 77.25)
    - 24 hourly timestamps
    - Weather records aligned to hourly timestamps
    - At least 1 missing PM2.5 observation (to test missing lag/rolling statistics)
    """
    start_dt = datetime.fromisoformat(base_time_iso.replace("Z", "+00:00"))
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=timezone.utc)

    openaq_records: List[Dict[str, Any]] = []
    weather_records: List[Dict[str, Any]] = []

    # Station 1: syn_st_01
    for h in range(num_hours):
        curr_dt = start_dt + timedelta(hours=h)
        iso_str = curr_dt.isoformat().replace("+00:00", "Z")

        # Synthetic PM2.5 curve: 100 + 30 * sin(2*pi*h/24) + small variation
        pm25_val = 100.0 + 30.0 * (h % 24) / 24.0 + (h % 5)

        # Intentional missing observation at h=10 for syn_st_01
        if h != 10:
            openaq_records.append({
                "station_id": "syn_st_01",
                "timestamp": iso_str,
                "pollutant": "PM2.5",
                "value": round(pm25_val, 1),
                "unit": "µg/m³",
                "source": "SYNTHETIC_TEST_FIXTURE",
                "location": {"latitude": 28.610, "longitude": 77.200, "address": "Synthetic Station 01"},
            })

            # Secondary PM10 observation
            openaq_records.append({
                "station_id": "syn_st_01",
                "timestamp": iso_str,
                "pollutant": "PM10",
                "value": round(pm25_val * 1.8, 1),
                "unit": "µg/m³",
                "source": "SYNTHETIC_TEST_FIXTURE",
                "location": {"latitude": 28.610, "longitude": 77.200, "address": "Synthetic Station 01"},
            })

        # Weather for Station 1 location
        weather_records.append({
            "timestamp": iso_str,
            "latitude": 28.610,
            "longitude": 77.200,
            "temperature_2m": round(20.0 + (h % 10) * 0.5, 1),
            "relative_humidity_2m": round(50.0 + (h % 8) * 2.0, 1),
            "wind_speed_10m": round(2.0 + (h % 3) * 0.5, 1),
            "wind_direction_10m": float((h * 15) % 360),
            "surface_pressure": 1012.5,
            "boundary_layer_height": round(500.0 + (h % 12) * 50.0, 1),
        })

    # Station 2: syn_st_02
    for h in range(num_hours):
        curr_dt = start_dt + timedelta(hours=h)
        iso_str = curr_dt.isoformat().replace("+00:00", "Z")

        pm25_val = 80.0 + 20.0 * (h % 24) / 24.0 + (h % 4)

        openaq_records.append({
            "station_id": "syn_st_02",
            "timestamp": iso_str,
            "pollutant": "PM2.5",
            "value": round(pm25_val, 1),
            "unit": "µg/m³",
            "source": "SYNTHETIC_TEST_FIXTURE",
            "location": {"latitude": 28.650, "longitude": 77.250, "address": "Synthetic Station 02"},
        })

        openaq_records.append({
            "station_id": "syn_st_02",
            "timestamp": iso_str,
            "pollutant": "PM10",
            "value": round(pm25_val * 1.6, 1),
            "unit": "µg/m³",
            "source": "SYNTHETIC_TEST_FIXTURE",
            "location": {"latitude": 28.650, "longitude": 77.250, "address": "Synthetic Station 02"},
        })

    return {
        "openaq": openaq_records,
        "weather": weather_records,
    }
