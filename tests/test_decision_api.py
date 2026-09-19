"""
VayuDrishti — Decision Intelligence API Test Suite (Phase 1E-J2E.4.5)

Comprehensive API transport & integration test suite for POST /api/v1/decision endpoint:
1. Valid decision request (HTTP 200 & READY status)
2. Response schema validation
3. READY status propagation
4. PARTIAL status propagation
5. BLOCKED status propagation
6. Malformed request validation rejection (HTTP 422)
7. Invalid numeric values rejection (NaN/Inf HTTP 422)
8. Unsupported station scope handling (HTTP 200 BLOCKED)
9. Human review invariant ALWAYS True
10. Attempted client human review override ignored/rejected (ALWAYS True in response)
11. ActionRecommendation field & ordering preservation
12. Evidence reference preservation
13. Risk score preservation
14. Risk level preservation
15. Expiry timestamp preservation
16. No raw evidence blobs copied
17. Service initialization failure (HTTP 503)
18. Unexpected internal error (HTTP 500)
19. Deterministic repeated request evaluation
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.api.v1.endpoints.decision import get_decision_engine

client = TestClient(app)


@pytest.fixture
def valid_payload():
    return {
        "station_id": "ANAND_VIHAR_8118",
        "prediction_timestamp": "2026-03-30T12:00:00Z",
        "assessment_timestamp": "2026-03-30T12:00:00Z",
        "predicted_pm25_1h": 145.2,
        "pm25_1h_lower_90": 120.0,
        "pm25_1h_upper_90": 170.4,
        "predicted_pm25_3h": 158.0,
        "pm25_3h_lower_90": 130.0,
        "pm25_3h_upper_90": 186.0,
        "predicted_pm25_6h": 172.5,
        "pm25_6h_lower_90": 140.0,
        "pm25_6h_upper_90": 205.0,
        "hotspot_detected": True,
        "hotspot_id": "hs_av_20260330_01",
        "hotspot_support_score": 85.0,
        "hotspot_spatial_extent": 4.5,
        "hotspot_source_families": ["INDUSTRIAL_STACK", "TRAFFIC_CORRIDOR"],
        "industrial_context": True,
        "major_road_context": True,
        "sensitive_receptor_context": True,
        "forecast_result_id": "fc_av_20260330_12",
        "fusion_id": "fus_av_20260330_12",
        "context_artifact_id": "ctx_av_20260330_01",
    }


# Test 1: Valid Decision Request & HTTP 200 Success
def test_valid_decision_request(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["station_id"] == "ANAND_VIHAR_8118"
    assert data["overall_data_quality_status"] == "READY"


# Test 2: Response Schema Validation
def test_response_schema_validation(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    required_keys = [
        "status", "decision_result_id", "station_id", "prediction_timestamp",
        "created_timestamp", "expires_timestamp", "forecast_status", "risk_status",
        "action_status", "overall_data_quality_status", "forecast_reference",
        "risk_reference", "action_reference", "evidence_references", "risk_score",
        "risk_level", "recommendation_count", "recommendations", "missing_evidence",
        "decision_summary", "requires_human_review", "model_scope",
        "calculation_version", "non_medical_disclaimer", "non_causal_disclaimer"
    ]
    for key in required_keys:
        assert key in data, f"Missing required response key '{key}'"


# Test 3: READY Status Propagation
def test_ready_status_propagation(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["forecast_status"] == "READY"
    assert data["risk_status"] == "READY"
    assert data["action_status"] == "READY"
    assert data["overall_data_quality_status"] == "READY"


# Test 4: PARTIAL Status Propagation
def test_partial_status_propagation(valid_payload):
    payload = valid_payload.copy()
    payload.pop("predicted_pm25_3h")
    payload.pop("predicted_pm25_6h")

    response = client.post("/api/v1/decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["forecast_status"] == "PARTIAL"
    assert data["overall_data_quality_status"] == "PARTIAL"


# Test 5: BLOCKED Status Propagation
def test_blocked_status_propagation(valid_payload):
    payload = valid_payload.copy()
    payload["station_id"] = "UNSUPPORTED_STATION"

    response = client.post("/api/v1/decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_data_quality_status"] == "BLOCKED"
    assert data["risk_level"] == "UNSUPPORTED_STATION_SCOPE"


# Test 6: Malformed Request (HTTP 422)
def test_malformed_request_returns_422(valid_payload):
    payload = valid_payload.copy()
    payload.pop("prediction_timestamp")  # Missing required field

    response = client.post("/api/v1/decision", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


# Test 7: Invalid Numeric Values Rejection (NaN / Inf HTTP 422)
def test_invalid_numeric_values_returns_422(valid_payload):
    payload = valid_payload.copy()
    payload["predicted_pm25_1h"] = "NaN"

    response = client.post("/api/v1/decision", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data


# Test 8: Unsupported Station Behavior (HTTP 200 with BLOCKED status)
def test_unsupported_station_behavior(valid_payload):
    payload = valid_payload.copy()
    payload["station_id"] = "INDIRAPURAM_9999"

    response = client.post("/api/v1/decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["overall_data_quality_status"] == "BLOCKED"
    assert data["requires_human_review"] is True


# Test 9: Human Review Invariant ALWAYS True
def test_human_review_invariant_always_true(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["requires_human_review"] is True

    # Check nested recommendations
    for rec in data["recommendations"]:
        assert rec["requires_human_review"] is True


# Test 10: Attempted Client Human Review Override Ignored / Rejected (CHANGE 1)
def test_attempted_human_review_override_ignored(valid_payload):
    payload = valid_payload.copy()
    payload["requires_human_review"] = False  # Client attempts to override invariant

    response = client.post("/api/v1/decision", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["requires_human_review"] is True, "Client MUST NOT be able to override requires_human_review to False"


# Test 11: Action Recommendation Field & Ordering Preservation (CHANGE 2)
def test_action_recommendation_field_preservation(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    recs = data["recommendations"]
    assert len(recs) > 0

    for rec in recs:
        assert "recommendation_id" in rec
        assert "action_type" in rec
        assert "priority" in rec
        assert "title" in rec
        assert "description" in rec
        assert "expected_objective" in rec
        assert "trigger_conditions" in rec
        assert "reason_codes" in rec
        assert "supporting_evidence" in rec
        assert "requires_human_review" in rec
        assert rec["requires_human_review"] is True


# Test 12: Evidence Reference Preservation
def test_evidence_reference_preservation(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    ref = data["evidence_references"]
    assert ref.get("forecast_result_id") == "fc_av_20260330_12"
    assert ref.get("hotspot_id") == "hs_av_20260330_01"
    assert ref.get("fusion_id") == "fus_av_20260330_12"
    assert ref.get("context_artifact_id") == "ctx_av_20260330_01"
    assert "assessment_id" in ref
    assert "action_result_id" in ref


# Test 13: Risk Score Preservation
def test_risk_score_preservation(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["risk_score"], float)
    assert 0.0 <= data["risk_score"] <= 100.0


# Test 14: Risk Level Preservation
def test_risk_level_preservation(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] in ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]


# Test 15: Expiry Timestamp Preservation
def test_expiry_timestamp_preservation(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    assert "expires_timestamp" in data
    assert data["expires_timestamp"].endswith("Z")


# Test 16: No Raw Evidence Blobs Copied
def test_no_raw_evidence_blobs_copied(valid_payload):
    response = client.post("/api/v1/decision", json=valid_payload)
    assert response.status_code == 200
    data = response.json()
    text_content = str(data)

    # Ensure no raw base64 or binary blob signatures present
    assert "data:image/" not in text_content
    assert "data:audio/" not in text_content


# Test 17: Service Initialization Failure (HTTP 503)
def test_service_initialization_failure_returns_503(valid_payload):
    with patch("backend.api.v1.endpoints.decision.get_decision_engine", side_effect=RuntimeError("Mock init error")):
        response = client.post("/api/v1/decision", json=valid_payload)
        assert response.status_code == 503
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "DECISION_SERVICE_UNAVAILABLE"


# Test 18: Unexpected Internal Error (HTTP 500)
def test_unexpected_error_returns_500(valid_payload):
    with patch("backend.api.v1.endpoints.decision.get_decision_engine") as mock_get:
        mock_engine = mock_get.return_value
        mock_engine.orchestrate.side_effect = Exception("Unexpected database failure")

        response = client.post("/api/v1/decision", json=valid_payload)
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "DECISION_ORCHESTRATION_ERROR"


# Test 19: Deterministic Repeated Request Evaluation
def test_deterministic_repeated_request(valid_payload):
    res1 = client.post("/api/v1/decision", json=valid_payload).json()
    res2 = client.post("/api/v1/decision", json=valid_payload).json()

    assert res1["risk_score"] == res2["risk_score"]
    assert res1["risk_level"] == res2["risk_level"]
    assert res1["recommendation_count"] == res2["recommendation_count"]
    assert res1["overall_data_quality_status"] == res2["overall_data_quality_status"]
    assert res1["decision_summary"] == res2["decision_summary"]
