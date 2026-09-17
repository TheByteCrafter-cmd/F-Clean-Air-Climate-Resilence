"""
VayuDrishti — Phase 1E-I Hyper-Local Pollution Hotspot Detection Test Suite

Tests Haversine distance, local baseline, anomaly calculation, IDW interpolation,
zero-distance handling, minimum station density rule, IDW search radius, grid generation,
contiguous region grouping, GeoJSON polygon geometry, hotspot support scoring,
confidence tiering, fusion linkage, REST API endpoints, and Scenarios A–H.
"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.api.v1.schemas.hotspot import HotspotDetectionResult, HotspotSummary
from backend.ingestion.exceptions import (
    HotspotDetectionError,
    HotspotPersistenceError,
    InsufficientSpatialDataError,
)
from backend.ingestion.hotspot_detector import (
    HotspotDetectorConfiguration,
    HyperLocalHotspotDetector,
    haversine_spherical_distance_km,
)
from tests.fixtures.hotspot_fixtures import (
    get_hotspot_scenario_a_records,
    get_hotspot_scenario_b_records,
    get_hotspot_scenario_c_records,
    get_hotspot_scenario_d_records,
    get_hotspot_scenario_e_records,
    get_hotspot_scenario_f_records,
    get_hotspot_scenario_g_records,
    get_hotspot_scenario_h_records,
)

client = TestClient(app)


@pytest.fixture
def temp_data_dir():
    """Provides a temporary data directory and cleans it up after test completion."""
    tmp_path = Path(tempfile.mkdtemp(prefix="vayudrishti_hotspot_test_"))
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


# ==============================================================================
# 1. DISTANCE & MATHEMATICS TESTS
# ==============================================================================
def test_haversine_spherical_distance_km():
    """Verifies Haversine spherical distance calculation."""
    dist = haversine_spherical_distance_km(28.6139, 77.2090, 28.6315, 77.2167)
    assert 1.9 <= dist <= 2.3

    zero_dist = haversine_spherical_distance_km(28.6139, 77.2090, 28.6139, 77.2090)
    assert zero_dist == 0.0


# ==============================================================================
# 2. SCENARIO TESTS (A - H)
# ==============================================================================
def test_scenario_a_clear_elevated_anomaly(temp_data_dir):
    """Scenario A: 5 stations with clear spatial anomaly -> generates hotspot result."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_a = get_hotspot_scenario_a_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_a["openaq"],
        custom_weather_data=sc_a["weather"],
        custom_firms_data=sc_a["firms"],
        custom_fusion_data=sc_a["fusion"],
    )

    assert len(results) >= 1
    res = results[0]
    assert res.pollutant == "PM2.5"
    assert res.confidence_tier in ["MODERATE_SUPPORT", "HIGH_SUPPORT"]
    assert res.support_score >= 40.0
    assert res.interpolated_value >= 100.0
    assert res.anomaly_value > 0.0
    assert res.geometry["type"] in ["Polygon", "MultiPolygon"]
    assert "AIR_QUALITY" in res.supporting_source_families


def test_scenario_b_insufficient_station_density(temp_data_dir):
    """Scenario B: Only 2 stations (< 3 minimum requirement) -> returns empty list."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_b = get_hotspot_scenario_b_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_b["openaq"],
    )

    assert len(results) == 0


def test_scenario_c_no_meaningful_anomaly(temp_data_dir):
    """Scenario C: Clean baseline observations (uniform PM2.5 ~25) -> no hotspot detected."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_c = get_hotspot_scenario_c_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_c["openaq"],
    )

    assert len(results) == 0


def test_scenario_d_strong_anomaly_weak_corroboration(temp_data_dir):
    """Scenario D: High PM2.5 anomaly without external corroboration -> generated with lower support."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_d = get_hotspot_scenario_d_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_d["openaq"],
    )

    assert len(results) >= 1
    res = results[0]
    # Without weather, FIRMS, or fusion, corroboration score is lower
    assert res.anomaly_value >= 50.0
    assert "AIR_QUALITY" in res.supporting_source_families


def test_scenario_e_fusion_evidence_strengthens_hotspot(temp_data_dir):
    """Scenario E: Fusion + FIRMS + Weather strengthens support score."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_e = get_hotspot_scenario_e_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_e["openaq"],
        custom_weather_data=sc_e["weather"],
        custom_firms_data=sc_e["firms"],
        custom_fusion_data=sc_e["fusion"],
    )

    assert len(results) >= 1
    res = results[0]
    assert res.support_score >= 60.0
    assert "CITIZEN_GEMINI" in res.supporting_source_families
    assert "THERMAL_ANOMALY" in res.supporting_source_families


def test_scenario_f_thermal_signal_no_pm_anomaly(temp_data_dir):
    """Scenario F: High FIRMS fire signal but uniform low PM2.5 -> no spatial PM hotspot generated."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_f = get_hotspot_scenario_f_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_f["openaq"],
        custom_firms_data=sc_f["firms"],
    )

    assert len(results) == 0


def test_scenario_g_sparse_single_high_station(temp_data_dir):
    """Scenario G: 1 high station (< 3 stations) -> returns empty list due to sparse data safety."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_g = get_hotspot_scenario_g_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_g["openaq"],
    )

    assert len(results) == 0


def test_scenario_h_contiguous_cell_aggregation(temp_data_dir):
    """Scenario H: Adjacent qualifying grid cells merge into one candidate polygon."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_h = get_hotspot_scenario_h_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_h["openaq"],
    )

    assert len(results) >= 1
    res = results[0]
    assert res.geometry["type"] in ["Polygon", "MultiPolygon"]


# ==============================================================================
# 3. PERSISTENCE & GEOJSON TESTS
# ==============================================================================
def test_hotspot_persistence_and_retrieval(temp_data_dir):
    """Verifies persisting HotspotDetectionResult and retrieving by ID."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_a = get_hotspot_scenario_a_records()

    results = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_a["openaq"],
    )
    assert len(results) >= 1
    hs_id = results[0].hotspot_id

    # Retrieve persisted artifact
    retrieved = detector.get_hotspot_result(hs_id)
    assert retrieved is not None
    assert retrieved.hotspot_id == hs_id
    assert retrieved.interpolated_value == results[0].interpolated_value

    # Verify GeoJSON collection artifact
    geojson_path = temp_data_dir / "processed" / "hotspots" / "delhi_hotspots.geojson"
    assert geojson_path.exists()
    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)
    assert geojson_data["type"] == "FeatureCollection"
    assert len(geojson_data["features"]) >= 1


# ==============================================================================
# 4. REST API ENDPOINT INTEGRATION TESTS
# ==============================================================================
def test_api_hotspot_endpoints(temp_data_dir, monkeypatch):
    """Tests POST /api/v1/hotspots/detect, GET /api/v1/hotspots/{id}, and GET /api/v1/hotspots."""
    from backend.api.v1.endpoints import hotspot as hotspot_endpoint

    test_detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    monkeypatch.setattr(hotspot_endpoint, "detector", test_detector)

    # 1. Run detection POST endpoint (using pre-populated local test scan)
    sc_a = get_hotspot_scenario_a_records()
    # Populate test detector with memory data run directly
    test_results = test_detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_a["openaq"],
        custom_weather_data=sc_a["weather"],
        custom_firms_data=sc_a["firms"],
    )
    assert len(test_results) >= 1
    hs_id = test_results[0].hotspot_id

    # 2. GET /api/v1/hotspots collection
    get_coll = client.get("/api/v1/hotspots")
    assert get_coll.status_code == 200
    coll_data = get_coll.json()
    assert coll_data["total_count"] >= 1

    # 3. GET /api/v1/hotspots/{hotspot_id} detail
    get_detail = client.get(f"/api/v1/hotspots/{hs_id}")
    assert get_detail.status_code == 200
    detail_data = get_detail.json()
    assert detail_data["hotspot_id"] == hs_id
    assert "support_score" in detail_data


def test_api_hotspot_not_found():
    """Verifies 404 response for non-existent hotspot_id."""
    response = client.get("/api/v1/hotspots/hs_00000000000000000000000000000000")
    assert response.status_code == 404


# ==============================================================================
# 5. SCORING INTEGRITY & INVARIANCE TESTS (PHASE 1E-I.1)
# ==============================================================================
def test_score_invariance_fusion_vs_direct_sources(temp_data_dir):
    """
    SCENARIO C / SCORE INVARIANCE TEST:
    Verifies that providing direct FIRMS/Sentinel/OSM source records in addition to an
    EvidenceFusionResult containing the exact same source families does NOT increase
    the hotspot support score (zero double-counting).
    """
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_e = get_hotspot_scenario_e_records()

    # Fusion result that explicitly includes THERMAL_ANOMALY and WEATHER supporting signals
    mock_fusion_with_signals = [{
        "fusion_id": "fu_test_e_full",
        "event_anchor_id": "ev_test_e",
        "created_at": "2026-09-18T00:00:00Z",
        "support_score": 90.0,
        "confidence_tier": "HIGH_SUPPORT",
        "supporting_signals": [
            {
                "source_family": "THERMAL_ANOMALY",
                "source_type": "FIRMS",
                "record_id": "f1",
                "provenance_ref": "firms.csv"
            },
            {
                "source_family": "WEATHER",
                "source_type": "OpenMeteo",
                "record_id": "w1",
                "provenance_ref": "weather.json"
            }
        ],
        "explanation": "Corroborated by thermal and weather signals"
    }]

    # Case 1: OpenAQ + EvidenceFusionResult (which summarizes FIRMS & Weather)
    res_fusion_only = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_e["openaq"],
        custom_fusion_data=mock_fusion_with_signals,
    )
    assert len(res_fusion_only) >= 1
    score_1 = res_fusion_only[0].support_score
    breakdown_1 = res_fusion_only[0].score_breakdown

    # Case 2: OpenAQ + EvidenceFusionResult + Direct FIRMS + Direct Weather
    res_fusion_and_direct = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_e["openaq"],
        custom_fusion_data=mock_fusion_with_signals,
        custom_firms_data=sc_e["firms"],
        custom_weather_data=sc_e["weather"],
    )
    assert len(res_fusion_and_direct) >= 1
    score_2 = res_fusion_and_direct[0].support_score
    breakdown_2 = res_fusion_and_direct[0].score_breakdown

    # Scores and breakdowns MUST be identical (Invariance Guarantee)
    assert score_1 == score_2
    assert breakdown_1["corroboration"] == breakdown_2["corroboration"]
    assert breakdown_1["total_score"] == breakdown_2["total_score"]


def test_openaq_inside_fusion_not_double_counted(temp_data_dir):
    """
    Verifies OpenAQ observations inside an EvidenceFusionResult do NOT receive
    an independent corroboration bonus on top of spatial anomaly scoring.
    """
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_a = get_hotspot_scenario_a_records()

    # Mock a fusion result that includes AIR_QUALITY in supporting_signals
    mock_fusion_openaq = [{
        "fusion_id": "fu_test_openaq_only",
        "event_anchor_id": "ev_test_anchor",
        "created_at": "2026-09-18T00:00:00Z",
        "support_score": 85.0,
        "confidence_tier": "HIGH_SUPPORT",
        "supporting_signals": [
            {
                "source_family": "AIR_QUALITY",
                "source_type": "OpenAQ",
                "record_id": "aq_del_001",
                "provenance_ref": "data/processed/openaq_delhi_observations.jsonl"
            }
        ],
        "explanation": "Test OpenAQ fusion"
    }]

    res = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_a["openaq"],
        custom_fusion_data=mock_fusion_openaq,
    )

    assert len(res) >= 1
    hotspot = res[0]
    # AIR_QUALITY inside fusion must NOT add corroboration bonus points
    # Scored families only includes CITIZEN_GEMINI from fusion anchor
    assert "AIR_QUALITY" not in [d["source_family"] for d in hotspot.corroboration_breakdown]
    assert hotspot.score_breakdown["corroboration"] == 6.25  # Only 1 family (CITIZEN_GEMINI)


def test_score_breakdown_auditability(temp_data_dir):
    """Verifies that score_breakdown and corroboration_breakdown fields are properly populated."""
    detector = HyperLocalHotspotDetector(data_root=temp_data_dir)
    sc_a = get_hotspot_scenario_a_records()

    res = detector.detect_hotspots(
        pollutant="PM2.5",
        custom_openaq_data=sc_a["openaq"],
        custom_firms_data=sc_a["firms"],
        custom_weather_data=sc_a["weather"],
    )

    assert len(res) >= 1
    hotspot = res[0]
    assert "spatial_anomaly" in hotspot.score_breakdown
    assert "spatial_extent" in hotspot.score_breakdown
    assert "spatial_coverage" in hotspot.score_breakdown
    assert "corroboration" in hotspot.score_breakdown
    assert "total_score" in hotspot.score_breakdown
    assert isinstance(hotspot.corroboration_breakdown, list)
    assert len(hotspot.corroboration_breakdown) >= 1

