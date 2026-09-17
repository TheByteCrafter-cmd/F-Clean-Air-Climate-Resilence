"""
VayuDrishti — Phase 1E-H Multi-Source Evidence Fusion Test Fixtures

Provides offline test fixture generators covering Scenarios A through G for fusion testing.
"""

from datetime import datetime, timezone
from typing import Dict, List, Any


def get_scenario_a_records(anchor_time_iso: str = "2026-03-15T10:00:00Z", lat: float = 28.6139, lon: float = 77.2090) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario A: Strong Support Across All Source Families.
    All 6 source families present within tight matching windows with elevated pollutant/thermal levels.
    """
    return {
        "openaq": [
            {
                "station_id": "openaq_st_1",
                "latitude": lat + 0.005,  # ~0.55 km away
                "longitude": lon + 0.005,
                "timestamp": anchor_time_iso,
                "pollutant": "PM2.5",
                "value": 185.0,  # Elevated
                "unit": "µg/m³",
                "source_file": "data/processed/openaq_delhi_observations.jsonl",
            }
        ],
        "weather": [
            {
                "weather_id": "wx_1",
                "latitude": lat,
                "longitude": lon,
                "timestamp": anchor_time_iso,
                "wind_speed_ms": 1.2,  # Stagnant air
                "relative_humidity_pct": 72.0,
                "temperature_c": 22.5,
                "source_file": "data/processed/open_meteo_delhi_weather.jsonl",
            }
        ],
        "firms": [
            {
                "fire_signal_id": "firms_1",
                "latitude": lat + 0.01,  # ~1.1 km away
                "longitude": lon + 0.01,
                "timestamp": anchor_time_iso,
                "frp": 18.5,  # High thermal radiative power
                "confidence": "high",
                "source_file": "data/processed/firms_delhi_fire.jsonl",
            }
        ],
        "satellite": [
            {
                "satellite_id": "s5p_1",
                "latitude": lat + 0.02,  # ~2.2 km away
                "longitude": lon + 0.02,
                "timestamp": anchor_time_iso,
                "no2_column_density": 0.00035,
                "unit": "mol/m²",
                "source_file": "data/processed/satellite/sentinel5p_delhi_no2.jsonl",
            }
        ],
        "geospatial": [
            {
                "feature_id": "osm_ind_1",
                "latitude": lat + 0.008,  # ~0.9 km away
                "longitude": lon + 0.008,
                "name": "Okhla Industrial Area Cluster",
                "category": "industrial",
                "source_file": "data/processed/geospatial/delhi_industrial_areas.geojson",
            }
        ],
    }


def get_scenario_b_records() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario B: Citizen Evidence Only.
    All environmental and geospatial datasets are completely empty / missing.
    """
    return {
        "openaq": [],
        "weather": [],
        "firms": [],
        "satellite": [],
        "geospatial": [],
    }


def get_scenario_c_records(anchor_time_iso: str = "2026-03-15T10:00:00Z", lat: float = 28.6139, lon: float = 77.2090) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario C: Conflicting Air Quality Signal.
    OpenAQ station matched within 1 km and 10 mins, but PM2.5 value is baseline clean (12.0 µg/m³).
    """
    return {
        "openaq": [
            {
                "station_id": "openaq_clean_1",
                "latitude": lat + 0.002,
                "longitude": lon + 0.002,
                "timestamp": anchor_time_iso,
                "pollutant": "PM2.5",
                "value": 12.0,  # Clean baseline level
                "unit": "µg/m³",
                "source_file": "data/processed/openaq_delhi_observations.jsonl",
            }
        ],
        "weather": [],
        "firms": [],
        "satellite": [],
        "geospatial": [],
    }


def get_scenario_d_records(anchor_time_iso: str = "2026-03-15T10:00:00Z", lat: float = 28.6139, lon: float = 77.2090) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario D: Partial Environmental Sources Present.
    Weather and OpenAQ present, but FIRMS, Sentinel-5P, and OSM absent.
    """
    return {
        "openaq": [
            {
                "station_id": "openaq_st_2",
                "latitude": lat + 0.008,
                "longitude": lon + 0.008,
                "timestamp": anchor_time_iso,
                "pollutant": "PM2.5",
                "value": 140.0,
                "unit": "µg/m³",
                "source_file": "data/processed/openaq_delhi_observations.jsonl",
            }
        ],
        "weather": [
            {
                "weather_id": "wx_2",
                "latitude": lat,
                "longitude": lon,
                "timestamp": anchor_time_iso,
                "wind_speed_ms": 1.5,
                "source_file": "data/processed/open_meteo_delhi_weather.jsonl",
            }
        ],
        "firms": [],
        "satellite": [],
        "geospatial": [],
    }


def get_scenario_e_records(anchor_time_iso: str = "2026-03-15T10:00:00Z", lat: float = 28.6139, lon: float = 77.2090) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario E: Poor Spatial Alignment.
    OpenAQ and FIRMS records are 50 km away (outside max distance thresholds).
    """
    return {
        "openaq": [
            {
                "station_id": "openaq_far",
                "latitude": lat + 0.45,  # ~50 km away
                "longitude": lon + 0.45,
                "timestamp": anchor_time_iso,
                "pollutant": "PM2.5",
                "value": 220.0,
                "unit": "µg/m³",
                "source_file": "data/processed/openaq_delhi_observations.jsonl",
            }
        ],
        "weather": [],
        "firms": [
            {
                "fire_signal_id": "firms_far",
                "latitude": lat + 0.50,
                "longitude": lon + 0.50,
                "timestamp": anchor_time_iso,
                "frp": 25.0,
                "source_file": "data/processed/firms_delhi_fire.jsonl",
            }
        ],
        "satellite": [],
        "geospatial": [],
    }


def get_scenario_f_records(anchor_time_iso: str = "2026-03-15T10:00:00Z", lat: float = 28.6139, lon: float = 77.2090) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario F: Poor Temporal Alignment.
    OpenAQ measurement timestamp is 12 hours after the citizen report timestamp (outside 60 min window).
    """
    return {
        "openaq": [
            {
                "station_id": "openaq_late",
                "latitude": lat + 0.002,
                "longitude": lon + 0.002,
                "timestamp": "2026-03-15T22:00:00Z",  # 12 hours later
                "pollutant": "PM2.5",
                "value": 190.0,
                "unit": "µg/m³",
                "source_file": "data/processed/openaq_delhi_observations.jsonl",
            }
        ],
        "weather": [],
        "firms": [],
        "satellite": [],
        "geospatial": [],
    }


def get_scenario_g_records(anchor_time_iso: str = "2026-03-15T10:00:00Z", lat: float = 28.6139, lon: float = 77.2090) -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario G: Thermal Anomaly Signal Only Matched.
    FIRMS thermal signal 1 km away with high FRP, other environmental signals absent.
    """
    return {
        "openaq": [],
        "weather": [],
        "firms": [
            {
                "fire_signal_id": "firms_only",
                "latitude": lat + 0.009,
                "longitude": lon + 0.009,
                "timestamp": anchor_time_iso,
                "frp": 32.0,
                "confidence": "high",
                "source_file": "data/processed/firms_delhi_fire.jsonl",
            }
        ],
        "satellite": [],
        "geospatial": [],
    }
