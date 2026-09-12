"""
VayuDrishti - Phase 1B API Contract Tests
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.main import app
from backend.api.v1.schemas import (
    Location,
    TimeRange,
    EnvironmentalObservation,
    CitizenEvidenceMetadata,
    HotspotSummary,
    ForecastSummary,
    RiskSummary,
    AuthorityRecommendation,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check_endpoint(client):
    """Verify backward compatibility of /api/health."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "VayuDrishti API"
    assert data["phase"] == "1b"
    assert "timestamp" in data


def test_api_v1_status_endpoint(client):
    """Verify versioned /api/v1/status endpoint."""
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "v1"
    assert "operational" in data["message"].lower()


def test_standardized_error_format(client):
    """Verify error handler returns structured envelope for 404s."""
    response = client.get("/api/v1/unregistered-route")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"
    assert data["error"]["message"] == "Not Found"


def test_location_schema_validation():
    """Verify Location validation for valid and invalid coordinates."""
    valid_loc = Location(latitude=28.6139, longitude=77.2090, address="Connaught Place, New Delhi")
    assert valid_loc.latitude == 28.6139
    assert valid_loc.longitude == 77.2090

    # Latitude out of bounds (> 90)
    with pytest.raises(ValidationError):
        Location(latitude=95.0, longitude=77.2)

    # Longitude out of bounds (< -180)
    with pytest.raises(ValidationError):
        Location(latitude=28.6, longitude=-185.0)


def test_time_range_validation():
    """Verify TimeRange validator ensures start_time <= end_time."""
    now = datetime.now(timezone.utc)
    valid_range = TimeRange(start_time=now, end_time=now + timedelta(hours=1))
    assert valid_range.start_time <= valid_range.end_time

    # Invalid: start_time > end_time
    with pytest.raises(ValidationError):
        TimeRange(start_time=now + timedelta(hours=2), end_time=now)


def test_environmental_observation_schema():
    """Verify EnvironmentalObservation schema contract."""
    obs = EnvironmentalObservation(
        timestamp=datetime.now(timezone.utc),
        location=Location(latitude=28.628, longitude=77.114),
        pollutant="PM2.5",
        value=145.5,
        unit="µg/m³",
        source="CAAQMS",
        station_id="DL_ANAND_VIHAR_01",
    )
    assert obs.pollutant == "PM2.5"
    assert obs.value == 145.5

    # Negative concentration value is rejected
    with pytest.raises(ValidationError):
        EnvironmentalObservation(
            timestamp=datetime.now(timezone.utc),
            location=Location(latitude=28.628, longitude=77.114),
            pollutant="PM2.5",
            value=-10.0,
            unit="µg/m³",
            source="CAAQMS",
        )


def test_citizen_evidence_schema():
    """Verify CitizenEvidenceMetadata schema contract."""
    evidence = CitizenEvidenceMetadata(
        evidence_id="ev-delhi-001",
        timestamp=datetime.now(timezone.utc),
        location=Location(latitude=28.65, longitude=77.12),
        media_type="image/jpeg",
        description="Heavy smoke emerging from industrial compound",
        source="citizen_report",
        category="industrial_smoke",
    )
    assert evidence.evidence_id == "ev-delhi-001"
    assert evidence.media_type == "image/jpeg"


def test_hotspot_summary_schema():
    """Verify HotspotSummary schema contract and confidence bounds."""
    hotspot = HotspotSummary(
        hotspot_id="hs-del-2026-001",
        location=Location(latitude=28.628, longitude=77.114),
        severity="SEVERE",
        confidence=92.5,
        detected_at=datetime.now(timezone.utc),
        radius_meters=750.0,
    )
    assert hotspot.severity == "SEVERE"
    assert hotspot.confidence == 92.5

    # Confidence > 100 rejected
    with pytest.raises(ValidationError):
        HotspotSummary(
            hotspot_id="hs-002",
            location=Location(latitude=28.6, longitude=77.1),
            severity="HIGH",
            confidence=105.0,
            detected_at=datetime.now(timezone.utc),
        )


def test_forecast_summary_schema():
    """Verify ForecastSummary schema contract."""
    forecast = ForecastSummary(
        location=Location(latitude=28.628, longitude=77.114),
        pollutant="PM2.5",
        forecast_horizon="3h",
        predicted_value=285.0,
        confidence=85.0,
        lower_bound=240.0,
        upper_bound=330.0,
    )
    assert forecast.forecast_horizon == "3h"
    assert forecast.predicted_value == 285.0


def test_risk_and_authority_recommendation_schemas():
    """Verify RiskSummary and AuthorityRecommendation schemas."""
    risk = RiskSummary(
        risk_level="CRITICAL",
        confidence=91.0,
        contributing_signals=["industrial_plume", "stagnant_wind", "high_density_corridor"],
        affected_zone="Mayapuri Industrial Area",
    )
    assert risk.risk_level == "CRITICAL"
    assert len(risk.contributing_signals) == 3

    rec = AuthorityRecommendation(
        recommendation_id="rec-001",
        priority="P1_URGENT",
        action="Dispatch Flying Squad Team 3 and deploy mobile water sprinkler unit",
        reason="Corridor PM2.5 spike forecasted to exceed 300 µg/m³ with low boundary layer",
        grap_stage="GRAP-III",
    )
    assert rec.priority == "P1_URGENT"
    assert rec.grap_stage == "GRAP-III"
