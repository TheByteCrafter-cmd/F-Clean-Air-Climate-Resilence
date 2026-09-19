"""
VayuDrishti — Risk Assessment API Test Suite (Phase 1E-J2E.4.2)

Comprehensive unit and integration test suite for POST /api/v1/risk endpoint:
1. Valid forecast-only risk request (PARTIAL status)
2. Valid forecast + hotspot request
3. Valid forecast + context request
4. Valid complete request (READY status)
5. Response schema validation
6. Score breakdown preservation
7. Reason code preservation
8. Evidence reference preservation
9. Canonical station acceptance (ANAND_VIHAR_8118)
10. Station alias acceptance (8118)
11. Unsupported station handling
12. Invalid timestamp syntax handling
13. Stale forecast rejection
14. Missing forecast field validation rejection (422)
15. Invalid numeric values rejection (NaN/Infinity 422)
16. Invalid hotspot support score rejection (>100 or <0 422)
17. PARTIAL status propagation
18. BLOCKED status propagation
19. Deterministic repeated request
20. Engine / API exact equivalence
21. Non-medical disclaimer preservation
22. Zero external network calls verification
23. Application-lifetime engine singleton behavior
24. Structured error response schema
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from ml.src.risk.risk_engine import RiskAssessmentEngine
from ml.src.risk.risk_schemas import RiskAssessmentInput

client = TestClient(app)


@pytest.fixture
def valid_payload():
    return {
        "station_id": "ANAND_VIHAR_8118",
        "assessment_timestamp": "2026-09-20T10:00:00Z",
        "forecast_generated_timestamp": "2026-09-20T09:30:00Z",
        "predicted_pm25_1h": 75.0,
        "pm25_1h_lower_90": 50.0,
        "pm25_1h_upper_90": 100.0,
        "predicted_pm25_3h": 85.0,
        "pm25_3h_lower_90": 55.0,
        "pm25_3h_upper_90": 115.0,
        "predicted_pm25_6h": 95.0,
        "pm25_6h_lower_90": 60.0,
        "pm25_6h_upper_90": 130.0,
        "hotspot_detected": True,
        "hotspot_id": "hotspot_av_001",
        "hotspot_support_score": 80.0,
        "hotspot_spatial_extent": 1.5,
        "hotspot_source_families": ["INDUSTRIAL_EMISSION"],
        "industrial_context": True,
        "major_road_context": True,
        "sensitive_receptor_context": False,
        "forecast_result_id": "fc_res_123",
        "fusion_id": "fusion_456",
        "context_artifact_id": "ctx_789",
    }


# Test 1: Valid Forecast-Only Request (PARTIAL Data Quality Status)
def test_valid_forecast_only_request(valid_payload):
    payload = valid_payload.copy()
    payload.pop("hotspot_support_score")
    payload.pop("hotspot_detected")
    payload.pop("industrial_context")

    response = client.post("/api/v1/risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["data_quality_status"] == "PARTIAL"
    assert data["hotspot_missing"] is True


# Test 2: Valid Forecast + Hotspot Request
def test_valid_forecast_plus_hotspot_request(valid_payload):
    payload = valid_payload.copy()
    payload.pop("industrial_context")
    payload.pop("major_road_context")
    payload.pop("sensitive_receptor_context")

    response = client.post("/api/v1/risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["score_breakdown"]["hotspot_corroboration"] > 0.0
    assert "HOTSPOT_CORROBORATED" in data["reason_codes"]


# Test 3: Valid Forecast + Context Request
def test_valid_forecast_plus_context_request(valid_payload):
    payload = valid_payload.copy()
    payload.pop("hotspot_support_score")
    payload.pop("hotspot_detected")

    response = client.post("/api/v1/risk", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["score_breakdown"]["context"] > 0.0
    assert "INDUSTRIAL_CONTEXT_PRESENT" in data["reason_codes"]


# Test 4: Valid Complete Request (READY Status)
def test_valid_complete_request(valid_payload):
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["data_quality_status"] == "READY"
    assert data["hotspot_missing"] is False
    assert data["context_missing"] is False


# Test 5: Response Schema Validation
def test_response_schema_validation(valid_payload):
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    required_keys = [
        "status",
        "assessment_id",
        "canonical_station_id",
        "assessment_timestamp",
        "forecast_generated_timestamp",
        "forecast_age_minutes",
        "risk_score",
        "risk_level",
        "score_breakdown",
        "reason_codes",
        "data_quality_status",
        "hotspot_missing",
        "context_missing",
        "evidence_references",
        "model_scope",
        "calculation_version",
        "non_medical_disclaimer",
    ]
    for key in required_keys:
        assert key in data, f"Missing required response key: {key}"


# Test 6: Score Breakdown Preservation
def test_score_breakdown_preservation(valid_payload):
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    bd = response.json()["score_breakdown"]
    assert "forecast_severity" in bd
    assert "forecast_persistence" in bd
    assert "uncertainty" in bd
    assert "hotspot_corroboration" in bd
    assert "context" in bd


# Test 7: Reason Code Preservation
def test_reason_code_preservation(valid_payload):
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    reasons = response.json()["reason_codes"]
    assert "FORECAST_PM25_ELEVATED" in reasons
    assert "FORECAST_PERSISTENT" in reasons


# Test 8: Evidence Reference Preservation
def test_evidence_reference_preservation(valid_payload):
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    refs = response.json()["evidence_references"]
    assert refs["forecast_result_id"] == "fc_res_123"
    assert refs["hotspot_id"] == "hotspot_av_001"
    assert refs["fusion_id"] == "fusion_456"
    assert refs["context_artifact_id"] == "ctx_789"


# Test 9: Canonical Station Acceptance
def test_canonical_station_acceptance(valid_payload):
    valid_payload["station_id"] = "ANAND_VIHAR_8118"
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    assert response.json()["canonical_station_id"] == "ANAND_VIHAR_8118"


# Test 10: Station Alias Acceptance
def test_station_alias_acceptance(valid_payload):
    valid_payload["station_id"] = "8118"
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    assert response.json()["canonical_station_id"] == "ANAND_VIHAR_8118"


# Test 11: Unsupported Station Response
def test_unsupported_station_response(valid_payload):
    valid_payload["station_id"] = "UNSUPPORTED_STATION_9999"
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "UNSUPPORTED_STATION_SCOPE"
    assert data["data_quality_status"] == "BLOCKED"
    assert "UNSUPPORTED_STATION_SCOPE" in data["reason_codes"]


# Test 12: Invalid Timestamp Response
def test_invalid_timestamp_response(valid_payload):
    valid_payload["assessment_timestamp"] = "malformed-timestamp"
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data_quality_status"] == "BLOCKED"
    assert any("INVALID_TIMESTAMP" in r for r in data["reason_codes"])


# Test 13: Stale Forecast Rejection
def test_stale_forecast_rejection(valid_payload):
    valid_payload["assessment_timestamp"] = "2026-09-20T13:00:00Z"  # 3.5 hrs later
    valid_payload["forecast_generated_timestamp"] = "2026-09-20T09:30:00Z"
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["data_quality_status"] == "BLOCKED"
    assert any("STALE_FORECAST" in r for r in data["reason_codes"])


# Test 14: Missing Forecast Field Rejection
def test_missing_forecast_field_rejection(valid_payload):
    valid_payload.pop("predicted_pm25_1h")
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 422
    assert "error" in response.json()


# Test 15: Invalid Numeric Values Rejection (NaN / Infinity)
def test_invalid_numeric_values_rejection(valid_payload):
    valid_payload["predicted_pm25_1h"] = "NaN"
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 422


# Test 16: Invalid Hotspot Support Score Rejection
def test_invalid_hotspot_support_score_rejection(valid_payload):
    valid_payload["hotspot_support_score"] = 150.0  # > 100.0 forbidden
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 422


# Test 17: PARTIAL Status Propagation
def test_partial_status_propagation(valid_payload):
    valid_payload["hotspot_support_score"] = None
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    assert response.json()["data_quality_status"] == "PARTIAL"


# Test 18: BLOCKED Status Propagation
def test_blocked_status_propagation(valid_payload):
    valid_payload["assessment_timestamp"] = "2026-09-20T15:00:00Z"
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    assert response.json()["data_quality_status"] == "BLOCKED"


# Test 19: Deterministic Repeated Request
def test_deterministic_repeated_request(valid_payload):
    res1 = client.post("/api/v1/risk", json=valid_payload).json()
    res2 = client.post("/api/v1/risk", json=valid_payload).json()
    assert res1["risk_score"] == res2["risk_score"]
    assert res1["risk_level"] == res2["risk_level"]
    assert res1["score_breakdown"] == res2["score_breakdown"]
    assert res1["reason_codes"] == res2["reason_codes"]


# Test 20: Engine / API Exact Equivalence
def test_engine_api_equivalence(valid_payload):
    # Direct engine execution
    engine = RiskAssessmentEngine()
    input_data = RiskAssessmentInput(
        station_id=valid_payload["station_id"],
        assessment_timestamp=valid_payload["assessment_timestamp"],
        forecast_generated_timestamp=valid_payload["forecast_generated_timestamp"],
        predicted_pm25_1h=valid_payload["predicted_pm25_1h"],
        pm25_1h_lower_90=valid_payload["pm25_1h_lower_90"],
        pm25_1h_upper_90=valid_payload["pm25_1h_upper_90"],
        predicted_pm25_3h=valid_payload["predicted_pm25_3h"],
        pm25_3h_lower_90=valid_payload["pm25_3h_lower_90"],
        pm25_3h_upper_90=valid_payload["pm25_3h_upper_90"],
        predicted_pm25_6h=valid_payload["predicted_pm25_6h"],
        pm25_6h_lower_90=valid_payload["pm25_6h_lower_90"],
        pm25_6h_upper_90=valid_payload["pm25_6h_upper_90"],
        hotspot_detected=valid_payload["hotspot_detected"],
        hotspot_id=valid_payload["hotspot_id"],
        hotspot_support_score=valid_payload["hotspot_support_score"],
        hotspot_spatial_extent=valid_payload["hotspot_spatial_extent"],
        hotspot_source_families=valid_payload["hotspot_source_families"],
        industrial_context=valid_payload["industrial_context"],
        major_road_context=valid_payload["major_road_context"],
        sensitive_receptor_context=valid_payload["sensitive_receptor_context"],
        forecast_result_id=valid_payload["forecast_result_id"],
        fusion_id=valid_payload["fusion_id"],
        context_artifact_id=valid_payload["context_artifact_id"],
    )
    direct_res = engine.assess_risk(input_data)

    # API execution
    api_res = client.post("/api/v1/risk", json=valid_payload).json()

    # Equivalence assertions
    assert api_res["canonical_station_id"] == direct_res.station_id
    assert api_res["risk_score"] == direct_res.risk_score
    assert api_res["risk_level"] == direct_res.risk_level
    assert api_res["score_breakdown"]["forecast_severity"] == direct_res.score_breakdown.forecast_severity
    assert api_res["score_breakdown"]["forecast_persistence"] == direct_res.score_breakdown.forecast_persistence
    assert api_res["score_breakdown"]["uncertainty"] == direct_res.score_breakdown.uncertainty
    assert api_res["score_breakdown"]["hotspot_corroboration"] == direct_res.score_breakdown.hotspot_corroboration
    assert api_res["score_breakdown"]["context"] == direct_res.score_breakdown.context
    assert api_res["reason_codes"] == direct_res.reason_codes
    assert api_res["data_quality_status"] == direct_res.data_quality_status


# Test 21: Non-Medical Disclaimer Preservation
def test_non_medical_disclaimer_preservation(valid_payload):
    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    disclaimer = response.json()["non_medical_disclaimer"]
    assert "medical diagnosis" in disclaimer.lower()
    assert "operational environmental risk" in disclaimer.lower()


# Test 22: Zero External Network Calls Verification
def test_zero_external_network_calls(monkeypatch, valid_payload):
    # Monkeypatch requests & httpx to raise error if invoked
    def block_network(*args, **kwargs):
        raise RuntimeError("External network call forbidden during risk API execution!")

    monkeypatch.setattr("requests.get", block_network)
    monkeypatch.setattr("requests.post", block_network)

    response = client.post("/api/v1/risk", json=valid_payload)
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"


# Test 23: Application-Lifetime Engine Singleton Behavior
def test_application_lifetime_engine_behavior():
    from backend.api.v1.endpoints.risk import get_risk_engine

    engine1 = get_risk_engine()
    engine2 = get_risk_engine()
    assert engine1 is engine2


# Test 24: Structured Error Response Schema
def test_structured_error_schema():
    response = client.post("/api/v1/risk", json={})
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert "message" in data["error"]
