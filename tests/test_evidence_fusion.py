"""
VayuDrishti — Phase 1E-H Multi-Source Evidence Fusion Test Suite

Tests Haversine distance, time difference, spatial/temporal matching windows,
source family grouping, support scoring, confidence tiering, missing/conflicting signal handling,
deterministic explanation generation, REST API endpoints, and Scenarios A–G.
"""

import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.api.v1.schemas.evidence import EvidenceLocation, EvidenceManifest, MediaItem, EvidenceAIAnalysis
from backend.api.v1.schemas.fusion import EvidenceFusionResult
from backend.ingestion.citizen_evidence_storage import CitizenEvidenceStorage, generate_evidence_id
from backend.ingestion.evidence_fusion_engine import (
    EvidenceFusionEngine,
    FusionConfiguration,
    haversine_distance_km,
    time_difference_minutes,
)
from backend.ingestion.exceptions import (
    AnchorMetadataNotFoundError,
    EvidenceFusionError,
    FusionPersistenceError,
)
from tests.fixtures.fusion_fixtures import (
    get_scenario_a_records,
    get_scenario_b_records,
    get_scenario_c_records,
    get_scenario_d_records,
    get_scenario_e_records,
    get_scenario_f_records,
    get_scenario_g_records,
)

client = TestClient(app)


@pytest.fixture
def temp_data_dir():
    """Provides a temporary data directory and cleans it up after test completion."""
    tmp_path = Path(tempfile.mkdtemp(prefix="vayudrishti_fusion_test_"))
    yield tmp_path
    shutil.rmtree(tmp_path, ignore_errors=True)


def create_sample_manifest(
    storage: CitizenEvidenceStorage,
    evidence_id: str,
    latitude: float = 28.6139,
    longitude: float = 77.2090,
    submitted_at: Optional[datetime] = None,
) -> EvidenceManifest:
    """Helper to create and persist a test citizen evidence manifest."""
    now_utc = submitted_at or datetime.now(timezone.utc)
    manifest = EvidenceManifest(
        evidence_id=evidence_id,
        submitted_at=now_utc,
        location=EvidenceLocation(
            latitude=latitude,
            longitude=longitude,
            accuracy_m=10.0,
            source="gps",
            timestamp=now_utc,
        ),
        media=[
            MediaItem(
                media_id=f"med_{evidence_id}_1",
                media_type="photo",
                filename="photo_1.jpg",
                stored_filename="photo_1.jpg",
                file_path=f"data/raw/citizen_evidence/photos/{evidence_id}_1.jpg",
                mime_type="image/jpeg",
                file_size_bytes=1024,
                checksum_sha256="0" * 64,
            )
        ],
        description="Visible dense black smoke from nearby factory stack.",
        category="industrial_smoke",
        consent_given=True,
        status="RECEIVED",
        source="citizen_web",
        schema_version="1.0",
    )
    storage.save_manifest(manifest)
    return manifest


# ==============================================================================
# 1. GEODESIC & TEMPORAL MATHEMATICS TESTS
# ==============================================================================
def test_haversine_distance_km():
    """Verifies Haversine geodesic distance calculation."""
    # Distance between New Delhi (28.6139, 77.2090) and Connaught Place (28.6315, 77.2167) ~2.1 km
    dist = haversine_distance_km(28.6139, 77.2090, 28.6315, 77.2167)
    assert 1.9 <= dist <= 2.3

    # Same location distance is 0.0
    zero_dist = haversine_distance_km(28.6139, 77.2090, 28.6139, 77.2090)
    assert zero_dist == 0.0


def test_time_difference_minutes():
    """Verifies signed time difference calculation in minutes."""
    t1 = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    diff = time_difference_minutes(t1, t2)
    assert diff == 30.0

    diff_negative = time_difference_minutes(t2, t1)
    assert diff_negative == -30.0


# ==============================================================================
# 2. SCENARIOS A - G ENGINE TESTS
# ==============================================================================
def test_scenario_a_strong_support(temp_data_dir):
    """Scenario A: All 6 source families present within window -> HIGH_SUPPORT."""
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    manifest = create_sample_manifest(storage, ev_id)

    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    sc_a = get_scenario_a_records(
        anchor_time_iso=manifest.submitted_at.isoformat(),
        lat=manifest.location.latitude,
        lon=manifest.location.longitude,
    )

    result = engine.fuse_evidence(
        evidence_id=ev_id,
        custom_openaq_data=sc_a["openaq"],
        custom_weather_data=sc_a["weather"],
        custom_firms_data=sc_a["firms"],
        custom_satellite_data=sc_a["satellite"],
        custom_geospatial_data=sc_a["geospatial"],
    )

    assert result.confidence_tier == "HIGH_SUPPORT"
    assert result.support_score >= 70.0
    assert len(result.supporting_signals) >= 5
    assert len(result.unavailable_signals) == 0
    assert "HIGH_SUPPORT" in result.explanation


def test_scenario_b_citizen_evidence_only(temp_data_dir):
    """Scenario B: Citizen Evidence only present -> LOW_SUPPORT (25 pts), 5 unavailable signals."""
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    create_sample_manifest(storage, ev_id)

    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    sc_b = get_scenario_b_records()

    result = engine.fuse_evidence(
        evidence_id=ev_id,
        custom_openaq_data=sc_b["openaq"],
        custom_weather_data=sc_b["weather"],
        custom_firms_data=sc_b["firms"],
        custom_satellite_data=sc_b["satellite"],
        custom_geospatial_data=sc_b["geospatial"],
    )

    assert result.confidence_tier == "LOW_SUPPORT"
    assert result.support_score == 10.0  # Base citizen report score without Gemini analysis
    assert len(result.unavailable_signals) == 5
    assert "AIR_QUALITY" in result.unavailable_signals
    assert "THERMAL_ANOMALY" in result.unavailable_signals
    assert "WEATHER" in result.unavailable_signals
    assert "SATELLITE_NO2" in result.unavailable_signals
    assert "GEOSPATIAL_CONTEXT" in result.unavailable_signals


def test_scenario_c_conflicting_air_quality(temp_data_dir):
    """Scenario C: Clean baseline OpenAQ station within window -> categorized under conflicting_signals."""
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    manifest = create_sample_manifest(storage, ev_id)

    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    sc_c = get_scenario_c_records(
        anchor_time_iso=manifest.submitted_at.isoformat(),
        lat=manifest.location.latitude,
        lon=manifest.location.longitude,
    )

    result = engine.fuse_evidence(
        evidence_id=ev_id,
        custom_openaq_data=sc_c["openaq"],
        custom_weather_data=sc_c["weather"],
        custom_firms_data=sc_c["firms"],
        custom_satellite_data=sc_c["satellite"],
        custom_geospatial_data=sc_c["geospatial"],
    )

    assert len(result.conflicting_signals) == 1
    assert result.conflicting_signals[0].source_family == "AIR_QUALITY"
    assert result.conflicting_signals[0].key_values["value"] == 12.0
    assert "Conflicting observations detected" in result.explanation


def test_scenario_d_partial_sources(temp_data_dir):
    """Scenario D: Weather and OpenAQ present, other sources missing."""
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    manifest = create_sample_manifest(storage, ev_id)

    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    sc_d = get_scenario_d_records(
        anchor_time_iso=manifest.submitted_at.isoformat(),
        lat=manifest.location.latitude,
        lon=manifest.location.longitude,
    )

    result = engine.fuse_evidence(
        evidence_id=ev_id,
        custom_openaq_data=sc_d["openaq"],
        custom_weather_data=sc_d["weather"],
        custom_firms_data=sc_d["firms"],
        custom_satellite_data=sc_d["satellite"],
        custom_geospatial_data=sc_d["geospatial"],
    )

    assert result.confidence_tier in ["MODERATE_SUPPORT", "HIGH_SUPPORT"]
    assert "THERMAL_ANOMALY" in result.unavailable_signals
    assert "SATELLITE_NO2" in result.unavailable_signals
    assert "GEOSPATIAL_CONTEXT" in result.unavailable_signals


def test_scenario_e_poor_spatial_alignment(temp_data_dir):
    """Scenario E: OpenAQ & FIRMS 50 km away -> outside window, categorized as unavailable."""
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    manifest = create_sample_manifest(storage, ev_id)

    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    sc_e = get_scenario_e_records(
        anchor_time_iso=manifest.submitted_at.isoformat(),
        lat=manifest.location.latitude,
        lon=manifest.location.longitude,
    )

    result = engine.fuse_evidence(
        evidence_id=ev_id,
        custom_openaq_data=sc_e["openaq"],
        custom_weather_data=sc_e["weather"],
        custom_firms_data=sc_e["firms"],
        custom_satellite_data=sc_e["satellite"],
        custom_geospatial_data=sc_e["geospatial"],
    )

    assert "AIR_QUALITY" in result.unavailable_signals
    assert "THERMAL_ANOMALY" in result.unavailable_signals


def test_scenario_f_poor_temporal_alignment(temp_data_dir):
    """Scenario F: OpenAQ observation 12 hours later -> outside max 60 min window, categorized as unavailable."""
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    manifest = create_sample_manifest(storage, ev_id)

    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    sc_f = get_scenario_f_records(
        anchor_time_iso=manifest.submitted_at.isoformat(),
        lat=manifest.location.latitude,
        lon=manifest.location.longitude,
    )

    result = engine.fuse_evidence(
        evidence_id=ev_id,
        custom_openaq_data=sc_f["openaq"],
        custom_weather_data=sc_f["weather"],
        custom_firms_data=sc_f["firms"],
        custom_satellite_data=sc_f["satellite"],
        custom_geospatial_data=sc_f["geospatial"],
    )

    assert "AIR_QUALITY" in result.unavailable_signals


def test_scenario_g_thermal_only(temp_data_dir):
    """Scenario G: FIRMS fire signal matched, others absent."""
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    manifest = create_sample_manifest(storage, ev_id)

    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    sc_g = get_scenario_g_records(
        anchor_time_iso=manifest.submitted_at.isoformat(),
        lat=manifest.location.latitude,
        lon=manifest.location.longitude,
    )

    result = engine.fuse_evidence(
        evidence_id=ev_id,
        custom_openaq_data=sc_g["openaq"],
        custom_weather_data=sc_g["weather"],
        custom_firms_data=sc_g["firms"],
        custom_satellite_data=sc_g["satellite"],
        custom_geospatial_data=sc_g["geospatial"],
    )

    firms_signals = [s for s in result.supporting_signals if s.source_family == "THERMAL_ANOMALY"]
    assert len(firms_signals) == 1
    assert firms_signals[0].key_values["frp_mw"] == 32.0


# ==============================================================================
# 3. SINGLE EVIDENCE FAMILY & GEMINI INTEGRATION TESTS
# ==============================================================================
def test_citizen_plus_gemini_family_no_double_counting(temp_data_dir):
    """Verifies Citizen Report + Gemini AI analysis is scored as 1 single family (CITIZEN_GEMINI, max 25 pts)."""
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    manifest = create_sample_manifest(storage, ev_id)

    # Persist Gemini analysis
    analysis_dir = temp_data_dir / "processed" / "citizen_evidence" / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    ai_analysis = EvidenceAIAnalysis(
        analysis_id=f"an_{ev_id}",
        evidence_id=ev_id,
        analyzed_at=datetime.now(timezone.utc),
        relevance="relevant",
        explanation="Photo shows high volume black particulate smoke.",
        probable_categories=[{"category": "industrial_smoke", "confidence_level": "high"}],
        model_name="gemini-1.5-flash",
        schema_version="1.0",
    )
    with open(analysis_dir / f"{ev_id}.json", "w", encoding="utf-8") as f:
        f.write(ai_analysis.model_dump_json(indent=2))

    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    sc_b = get_scenario_b_records()

    result = engine.fuse_evidence(
        evidence_id=ev_id,
        custom_openaq_data=sc_b["openaq"],
        custom_weather_data=sc_b["weather"],
        custom_firms_data=sc_b["firms"],
        custom_satellite_data=sc_b["satellite"],
        custom_geospatial_data=sc_b["geospatial"],
    )

    # Max score for CITIZEN_GEMINI is 25.0
    assert result.support_score == 25.0
    cg_refs = [s for s in result.supporting_signals if s.source_family == "CITIZEN_GEMINI"]
    assert len(cg_refs) == 1
    assert cg_refs[0].key_values["gemini_relevance"] == "relevant"


# ==============================================================================
# 4. EXCEPTION & ANCHOR VALIDATION TESTS
# ==============================================================================
def test_missing_manifest_raises_anchor_not_found(temp_data_dir):
    """Verifies AnchorMetadataNotFoundError when evidence_id does not exist."""
    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    with pytest.raises(AnchorMetadataNotFoundError):
        engine.fuse_evidence("ev_00000000000000000000000000000000")


def test_invalid_evidence_id_raises_error(temp_data_dir):
    """Verifies EvidenceFusionError for unsafe/malformatted evidence_id."""
    engine = EvidenceFusionEngine(data_root=temp_data_dir)
    with pytest.raises(EvidenceFusionError):
        engine.fuse_evidence("../invalid_id")


# ==============================================================================
# 5. REST API ENDPOINT INTEGRATION TESTS
# ==============================================================================
def test_api_fuse_citizen_evidence_endpoint(temp_data_dir, monkeypatch):
    """Tests POST /api/v1/fusion/evidence/{evidence_id} API endpoint."""
    # Monkeypatch storage and fusion engine data root
    storage = CitizenEvidenceStorage(data_root=temp_data_dir)
    ev_id = generate_evidence_id()
    create_sample_manifest(storage, ev_id)

    # Patch global engine in endpoints module
    from backend.api.v1.endpoints import fusion as fusion_endpoint
    test_engine = EvidenceFusionEngine(data_root=temp_data_dir)
    monkeypatch.setattr(fusion_endpoint, "engine", test_engine)

    response = client.post(f"/api/v1/fusion/evidence/{ev_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["event_anchor_id"] == ev_id
    assert "support_score" in data
    assert "confidence_tier" in data

    # Verify GET /api/v1/fusion/{fusion_id}
    fusion_id = data["fusion_id"]
    get_res = client.get(f"/api/v1/fusion/{fusion_id}")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["fusion_id"] == fusion_id

    # Verify GET /api/v1/fusion/evidence/{evidence_id} (using ev_ lookup)
    get_ev_res = client.get(f"/api/v1/fusion/{ev_id}")
    assert get_ev_res.status_code == 200
    assert get_ev_res.json()["fusion_id"] == fusion_id


def test_api_fusion_not_found():
    """Verifies 404 response for non-existent fusion_id."""
    response = client.get("/api/v1/fusion/fu_nonexistent_12345")
    assert response.status_code == 404
