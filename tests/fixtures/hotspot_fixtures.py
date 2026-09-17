"""
VayuDrishti — Phase 1E-I Hyper-Local Hotspot Detection Test Fixtures

Provides offline test fixture generators covering Scenarios A through H for hotspot testing.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List


def get_hotspot_scenario_a_records(anchor_time_iso: str = "2026-03-15T10:00:00Z") -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario A: Clear elevated spatial anomaly with sufficient observations.
    Background stations ~40 µg/m³, hotspot cluster ~180-195 µg/m³.
    """
    return {
        "openaq": [
            {"station_id": "st_hot_1", "latitude": 28.610, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 180.0, "unit": "µg/m³"},
            {"station_id": "st_hot_2", "latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 195.0, "unit": "µg/m³"},
            {"station_id": "st_hot_3", "latitude": 28.620, "longitude": 77.210, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 175.0, "unit": "µg/m³"},
            {"station_id": "st_bg_1", "latitude": 28.700, "longitude": 77.300, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 35.0, "unit": "µg/m³"},
            {"station_id": "st_bg_2", "latitude": 28.500, "longitude": 77.100, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 40.0, "unit": "µg/m³"},
            {"station_id": "st_bg_3", "latitude": 28.680, "longitude": 77.050, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 38.0, "unit": "µg/m³"},
            {"station_id": "st_bg_4", "latitude": 28.450, "longitude": 77.250, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 42.0, "unit": "µg/m³"},
        ],
        "weather": [{"latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "wind_speed_ms": 1.1}],
        "firms": [{"latitude": 28.618, "longitude": 77.208, "timestamp": anchor_time_iso, "frp": 15.0}],
        "fusion": [{"fusion_id": "fu_test_a", "event_anchor_id": "ev_test_a", "support_score": 85.0}],
    }


def get_hotspot_scenario_b_records(anchor_time_iso: str = "2026-03-15T10:00:00Z") -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario B: Insufficient station density (< 3 stations).
    Only 2 stations available -> should return empty/insufficient data.
    """
    return {
        "openaq": [
            {"station_id": "st_sparse_1", "latitude": 28.610, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 180.0},
            {"station_id": "st_sparse_2", "latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 190.0},
        ],
        "weather": [],
        "firms": [],
        "fusion": [],
    }


def get_hotspot_scenario_c_records(anchor_time_iso: str = "2026-03-15T10:00:00Z") -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario C: No meaningful anomaly (observations uniformly clean).
    All stations report clean baseline values (~25 µg/m³).
    """
    return {
        "openaq": [
            {"station_id": "st_clean_1", "latitude": 28.610, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 25.0},
            {"station_id": "st_clean_2", "latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 26.0},
            {"station_id": "st_clean_3", "latitude": 28.620, "longitude": 77.210, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 24.0},
            {"station_id": "st_clean_4", "latitude": 28.650, "longitude": 77.250, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 25.0},
        ],
        "weather": [],
        "firms": [],
        "fusion": [],
    }


def get_hotspot_scenario_d_records(anchor_time_iso: str = "2026-03-15T10:00:00Z") -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario D: Strong anomaly but weak corroborating evidence.
    High PM2.5 anomaly at stations, but zero FIRMS, weather, or fusion evidence.
    """
    return {
        "openaq": [
            {"station_id": "st_d1", "latitude": 28.610, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 160.0},
            {"station_id": "st_d2", "latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 165.0},
            {"station_id": "st_d3", "latitude": 28.620, "longitude": 77.210, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 155.0},
            {"station_id": "st_d4", "latitude": 28.750, "longitude": 77.350, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 30.0},
            {"station_id": "st_d5", "latitude": 28.500, "longitude": 77.100, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 32.0},
            {"station_id": "st_d6", "latitude": 28.680, "longitude": 77.050, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 35.0},
        ],
        "weather": [],
        "firms": [],
        "fusion": [],
    }


def get_hotspot_scenario_e_records(anchor_time_iso: str = "2026-03-15T10:00:00Z") -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario E: Citizen/fusion evidence strengthens an existing spatial anomaly.
    """
    return {
        "openaq": [
            {"station_id": "st_e1", "latitude": 28.610, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 170.0},
            {"station_id": "st_e2", "latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 175.0},
            {"station_id": "st_e3", "latitude": 28.620, "longitude": 77.210, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 165.0},
            {"station_id": "st_e4", "latitude": 28.750, "longitude": 77.350, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 30.0},
            {"station_id": "st_e5", "latitude": 28.500, "longitude": 77.100, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 32.0},
            {"station_id": "st_e6", "latitude": 28.680, "longitude": 77.050, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 35.0},
        ],
        "weather": [{"latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "wind_speed_ms": 1.0}],
        "firms": [{"latitude": 28.616, "longitude": 77.206, "timestamp": anchor_time_iso, "frp": 22.0}],
        "fusion": [{"fusion_id": "fu_test_e", "event_anchor_id": "ev_test_e", "support_score": 90.0}],
    }


def get_hotspot_scenario_f_records(anchor_time_iso: str = "2026-03-15T10:00:00Z") -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario F: Nearby thermal signal (FIRMS) but no significant PM anomaly.
    """
    return {
        "openaq": [
            {"station_id": "st_f1", "latitude": 28.610, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 28.0},
            {"station_id": "st_f2", "latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 30.0},
            {"station_id": "st_f3", "latitude": 28.620, "longitude": 77.210, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 27.0},
            {"station_id": "st_f4", "latitude": 28.650, "longitude": 77.250, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 29.0},
        ],
        "weather": [],
        "firms": [{"latitude": 28.615, "longitude": 77.205, "timestamp": anchor_time_iso, "frp": 45.0}],
        "fusion": [],
    }


def get_hotspot_scenario_g_records(anchor_time_iso: str = "2026-03-15T10:00:00Z") -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario G: High PM observation at single station, but stations too sparse (< 3) for safe interpolation.
    """
    return {
        "openaq": [
            {"station_id": "st_g1", "latitude": 28.610, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 350.0},
        ],
        "weather": [],
        "firms": [],
        "fusion": [],
    }


def get_hotspot_scenario_h_records(anchor_time_iso: str = "2026-03-15T10:00:00Z") -> Dict[str, List[Dict[str, Any]]]:
    """
    Scenario H: Two adjacent spatial clusters merging into contiguous grid polygon.
    """
    return {
        "openaq": [
            {"station_id": "st_h1", "latitude": 28.610, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 190.0},
            {"station_id": "st_h2", "latitude": 28.620, "longitude": 77.200, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 185.0},
            {"station_id": "st_h3", "latitude": 28.615, "longitude": 77.210, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 180.0},
            {"station_id": "st_h4", "latitude": 28.750, "longitude": 77.350, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 30.0},
            {"station_id": "st_h5", "latitude": 28.500, "longitude": 77.100, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 32.0},
            {"station_id": "st_h6", "latitude": 28.680, "longitude": 77.050, "timestamp": anchor_time_iso, "pollutant": "PM2.5", "value": 35.0},
        ],
        "weather": [],
        "firms": [],
        "fusion": [],
    }
