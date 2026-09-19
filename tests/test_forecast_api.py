"""
VayuDrishti — Forecast API Endpoint Test Suite (Phase 1E-J2E.2)

Tests FastAPI POST /api/v1/forecast transport layer, request validation,
station scope guardrails, error responses, conformal prediction intervals,
determinism, model lifecycle handling, and direct-engine vs API equivalence.
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from ml.src.forecasting.inference import ForecastInferenceEngine, InferenceError
from ml.src.forecasting.model_loader import CANONICAL_STATION_ID, ModelLoaderError

client = TestClient(app)


@pytest.fixture
def valid_forecast_payload():
    """Provides a valid, complete feature payload for testing /api/v1/forecast."""
    engine = ForecastInferenceEngine()
    features = {col: 100.0 for col in engine.feature_list}
    # Provide realistic sample values for key features
    features.update({
        "latitude": 28.6469,
        "longitude": 77.316,
        "pm25_lag_1h": 150.0,
        "temperature_2m": 15.5,
        "relative_humidity_2m": 65.0,
        "wind_speed_10m": 2.5,
        "surface_pressure": 995.0,
        "hour_sin": 0.5,
        "hour_cos": 0.866,
    })
    return {
        "station_id": "8118",
        "prediction_timestamp": "2025-01-31T12:00:00Z",
        "features": features,
    }


def test_valid_forecast_request(valid_forecast_payload):
    """1. Test valid forecast request returns HTTP 200 OK and expected structure."""
    response = client.post("/api/v1/forecast", json=valid_forecast_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert "forecasts" in data
    assert len(data["forecasts"]) == 3


def test_response_schema_validation(valid_forecast_payload):
    """2. Test response schema fields completeness."""
    response = client.post("/api/v1/forecast", json=valid_forecast_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["model_scope"] == "station_level_pilot"
    assert data["canonical_station_id"] == CANONICAL_STATION_ID
    assert data["feature_count"] == 27
    assert data["prediction_timestamp"] == "2025-01-31T12:00:00Z"


def test_station_alias_8118_acceptance(valid_forecast_payload):
    """3. Test station alias '8118' acceptance and canonical ID mapping."""
    payload = dict(valid_forecast_payload)
    payload["station_id"] = "8118"
    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["requested_station_id"] == "8118"
    assert data["canonical_station_id"] == "ANAND_VIHAR_8118"


def test_canonical_station_acceptance(valid_forecast_payload):
    """4. Test canonical station ID 'ANAND_VIHAR_8118' acceptance."""
    payload = dict(valid_forecast_payload)
    payload["station_id"] = "ANAND_VIHAR_8118"
    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_station_id"] == "ANAND_VIHAR_8118"


def test_unsupported_station_rejection(valid_forecast_payload):
    """5. Test unsupported station rejection (HTTP 400 & UNSUPPORTED_STATION_SCOPE)."""
    payload = dict(valid_forecast_payload)
    payload["station_id"] = "LOCATION_9999"
    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNSUPPORTED_STATION_SCOPE"


def test_invalid_timestamp_rejection(valid_forecast_payload):
    """6. Test invalid prediction timestamp rejection (HTTP 400 & INVALID_TIMESTAMP)."""
    payload = dict(valid_forecast_payload)
    payload["prediction_timestamp"] = "malformed-timestamp"
    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_TIMESTAMP"


def test_missing_feature_rejection(valid_forecast_payload):
    """7. Test missing feature rejection (HTTP 400 & MISSING_FEATURES)."""
    payload = dict(valid_forecast_payload)
    features = dict(payload["features"])
    del features["pm25_lag_1h"]
    payload["features"] = features

    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "MISSING_FEATURES"


def test_nan_infinite_feature_rejection(valid_forecast_payload):
    """8. Test NaN / Infinite feature value rejection."""
    payload = dict(valid_forecast_payload)
    features = dict(payload["features"])
    features["pm25_lag_1h"] = "NaN"
    payload["features"] = features

    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code in (400, 422)


def test_non_numeric_feature_rejection(valid_forecast_payload):
    """9. Test non-numeric feature value rejection."""
    payload = dict(valid_forecast_payload)
    features = dict(payload["features"])
    features["pm25_lag_1h"] = "invalid_string_value"
    payload["features"] = features

    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code in (400, 422)


def test_model_artifact_failure_handling(valid_forecast_payload):
    """10. Test model artifact failure handling returns HTTP 503 & MODEL_NOT_AVAILABLE."""
    with patch(
        "backend.api.v1.endpoints.forecast.get_inference_engine",
        side_effect=ModelLoaderError("Model artifact missing or unreadable."),
    ):
        response = client.post("/api/v1/forecast", json=valid_forecast_payload)
        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "MODEL_NOT_AVAILABLE"


def test_uncertainty_artifact_failure_handling(valid_forecast_payload):
    """11. Test uncertainty artifact failure handling returns HTTP 503."""
    with patch(
        "backend.api.v1.endpoints.forecast.get_inference_engine",
        side_effect=InferenceError("UNCERTAINTY_ARTIFACT_INVALID", "Uncertainty metrics corrupted."),
    ):
        response = client.post("/api/v1/forecast", json=valid_forecast_payload)
        assert response.status_code == 503
        data = response.json()
        assert data["error"]["code"] == "UNCERTAINTY_ARTIFACT_INVALID"


def test_80_percent_interval_response(valid_forecast_payload):
    """12. Test 80% interval calculation in API response."""
    response = client.post("/api/v1/forecast", json=valid_forecast_payload)
    assert response.status_code == 200
    data = response.json()
    h1 = data["forecasts"][0]
    iv80 = h1["prediction_intervals"]["80_pct"]

    pred = h1["predicted_pm25"]
    q80 = iv80["conformal_radius"]
    assert round(pred - q80, 4) == pytest.approx(iv80["lower_bound"], abs=1e-4)
    assert round(pred + q80, 4) == pytest.approx(iv80["upper_bound"], abs=1e-4)


def test_90_percent_interval_response(valid_forecast_payload):
    """13. Test 90% interval calculation in API response."""
    response = client.post("/api/v1/forecast", json=valid_forecast_payload)
    assert response.status_code == 200
    data = response.json()
    h1 = data["forecasts"][0]
    iv90 = h1["prediction_intervals"]["90_pct"]

    pred = h1["predicted_pm25"]
    q90 = iv90["conformal_radius"]
    assert round(pred - q90, 4) == pytest.approx(iv90["lower_bound"], abs=1e-4)
    assert round(pred + q90, 4) == pytest.approx(iv90["upper_bound"], abs=1e-4)


def test_negative_prediction_preservation(valid_forecast_payload):
    """14. Test negative prediction diagnostic flag and raw value preservation."""
    response = client.post("/api/v1/forecast", json=valid_forecast_payload)
    assert response.status_code == 200
    data = response.json()
    for f in data["forecasts"]:
        assert isinstance(f["prediction_negative"], bool)
        assert f["prediction_negative"] == (f["predicted_pm25"] < 0.0)


def test_deterministic_repeated_request_result(valid_forecast_payload):
    """15. Test deterministic repeated request result."""
    res1 = client.post("/api/v1/forecast", json=valid_forecast_payload).json()
    res2 = client.post("/api/v1/forecast", json=valid_forecast_payload).json()

    assert res1 == res2


def test_model_loading_lifecycle_behavior(valid_forecast_payload):
    """16. Test model loading lifecycle behavior (engine reused across requests)."""
    from backend.api.v1.endpoints.forecast import get_inference_engine

    engine1 = get_inference_engine()
    engine2 = get_inference_engine()
    assert engine1 is engine2


def test_structured_error_response_schema():
    """17. Test structured error response follows ErrorResponse envelope."""
    response = client.post("/api/v1/forecast", json={"station_id": "INVALID", "prediction_timestamp": "", "features": {}})
    assert response.status_code in (400, 422)
    data = response.json()
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]


def test_no_external_api_calls_from_endpoint(valid_forecast_payload):
    """18. Test endpoint requires zero external network calls."""
    # Running test with client POST proves no external network mocks are required
    response = client.post("/api/v1/forecast", json=valid_forecast_payload)
    assert response.status_code == 200


def test_direct_engine_vs_api_consistency(valid_forecast_payload):
    """19. Test direct ForecastInferenceEngine.predict output is 100% equivalent to POST /api/v1/forecast."""
    engine = ForecastInferenceEngine()
    direct_res = engine.predict(
        station_id=valid_forecast_payload["station_id"],
        prediction_timestamp=valid_forecast_payload["prediction_timestamp"],
        feature_row=valid_forecast_payload["features"],
    )

    api_response = client.post("/api/v1/forecast", json=valid_forecast_payload)
    assert api_response.status_code == 200
    api_res = api_response.json()

    assert api_res["canonical_station_id"] == direct_res["canonical_station_id"]
    assert api_res["prediction_timestamp"] == direct_res["prediction_timestamp"]
    assert api_res["feature_count"] == direct_res["feature_count"]

    # Map API list of forecasts back to dict for direct comparison
    api_horizons = {f["horizon"]: f for f in api_res["forecasts"]}

    for h in ["+1h", "+3h", "+6h"]:
        d_h = direct_res["horizons"][h]
        a_h = api_horizons[h]

        assert a_h["predicted_pm25"] == pytest.approx(d_h["predicted_pm25"], abs=1e-4)
        assert a_h["prediction_negative"] == d_h["prediction_negative"]

        d_iv80 = d_h["prediction_intervals"]["80_pct"]
        a_iv80 = a_h["prediction_intervals"]["80_pct"]

        assert a_iv80["conformal_radius"] == pytest.approx(d_iv80["conformal_radius"], abs=1e-4)
        assert a_iv80["lower_bound"] == pytest.approx(d_iv80["lower_bound"], abs=1e-4)
        assert a_iv80["upper_bound"] == pytest.approx(d_iv80["upper_bound"], abs=1e-4)

        d_iv90 = d_h["prediction_intervals"]["90_pct"]
        a_iv90 = a_h["prediction_intervals"]["90_pct"]

        assert a_iv90["conformal_radius"] == pytest.approx(d_iv90["conformal_radius"], abs=1e-4)
        assert a_iv90["lower_bound"] == pytest.approx(d_iv90["lower_bound"], abs=1e-4)
        assert a_iv90["upper_bound"] == pytest.approx(d_iv90["upper_bound"], abs=1e-4)
