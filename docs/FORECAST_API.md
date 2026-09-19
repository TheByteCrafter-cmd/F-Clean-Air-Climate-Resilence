# VayuDrishti — Forecast API Endpoint Specification

**Phase:** 1E-J2E.2 — Forecast API Endpoint  
**HTTP Route:** `POST /api/v1/forecast`  
**Canonical Station Scope:** `ANAND_VIHAR_8118`  
**Supported Station Aliases:** `ANAND_VIHAR_8118`, `8118`, `LOC_8118`, `LOCATION_8118`  
**Scope Limitation Statement:** "Current forecast API is limited to the Anand Vihar 8118 station-level pilot model and requires a leakage-safe prepared feature vector."  

---

## 1. Architecture & Transport Overview

The `/api/v1/forecast` endpoint provides a production-grade FastAPI transport wrapper around the deterministic `ForecastInferenceEngine` (Phase 1E-J2E.1). The route is responsible solely for request validation, station scope checking, UTC timestamp parsing, delegating to the application-lifetime inference engine, and wrapping output in a standardized JSON response.

> [!IMPORTANT]
> **No External Data Fetching:**  
> The endpoint does NOT perform live network requests to OpenAQ, Open-Meteo, FIRMS, Sentinel-5P, Overpass, or Gemini. The client MUST supply an already assembled, leakage-safe feature vector matching the model manifest.

---

## 2. Request & Response Contracts

### HTTP Request Specification
- **Method:** `POST`
- **URL Path:** `/api/v1/forecast`
- **Content-Type:** `application/json`

#### Request Payload Schema (`ForecastRequest`)
```json
{
  "station_id": "8118",
  "prediction_timestamp": "2025-01-31T12:00:00Z",
  "features": {
    "latitude": 28.6469,
    "longitude": 77.316,
    "pm25_lag_1h": 150.0,
    "pm25_lag_3h": 160.0,
    "pm25_lag_6h": 170.0,
    "pm25_lag_12h": 180.0,
    "pm25_lag_24h": 190.0,
    "pm25_roll_mean_3h": 155.0,
    "pm25_roll_median_3h": 155.0,
    "pm25_roll_mean_6h": 165.0,
    "pm25_roll_median_6h": 165.0,
    "pm25_roll_mean_24h": 175.0,
    "pm25_roll_median_24h": 175.0,
    "temperature_2m": 15.5,
    "relative_humidity_2m": 65.0,
    "wind_speed_10m": 2.5,
    "wind_direction_10m": 180.0,
    "wind_u": -0.5,
    "wind_v": -2.4,
    "surface_pressure": 995.0,
    "boundary_layer_height": 250.0,
    "hour_sin": 0.5,
    "hour_cos": 0.866,
    "day_of_week_sin": 0.0,
    "day_of_week_cos": 1.0,
    "month_sin": 0.5,
    "month_cos": 0.866
  }
}
```

### HTTP Response Specification (HTTP 200 OK)
```json
{
  "status": "SUCCESS",
  "model_scope": "station_level_pilot",
  "canonical_station_id": "ANAND_VIHAR_8118",
  "requested_station_id": "8118",
  "prediction_timestamp": "2025-01-31T12:00:00Z",
  "feature_count": 27,
  "forecasts": [
    {
      "horizon": "+1h",
      "target_column": "pm25_t_plus_1h",
      "predicted_pm25": 142.5042,
      "prediction_negative": false,
      "prediction_intervals": {
        "80_pct": {
          "confidence_level": "80%",
          "conformal_radius": 42.4646,
          "lower_bound": 100.0396,
          "upper_bound": 184.9688,
          "interval_width": 84.9292
        },
        "90_pct": {
          "confidence_level": "90%",
          "conformal_radius": 47.0292,
          "lower_bound": 95.475,
          "upper_bound": 189.5334,
          "interval_width": 94.0584
        }
      }
    },
    {
      "horizon": "+3h",
      "target_column": "pm25_t_plus_3h",
      "predicted_pm25": 148.2105,
      "prediction_negative": false,
      "prediction_intervals": { ... }
    },
    {
      "horizon": "+6h",
      "target_column": "pm25_t_plus_6h",
      "predicted_pm25": 158.4500,
      "prediction_negative": false,
      "prediction_intervals": { ... }
    }
  ]
}
```

---

## 3. Structured Error Mapping & HTTP Status Codes

The API enforces strict, deterministic HTTP error code mappings:

| HTTP Status | Error Code (`code`) | Description / Cause |
| :--- | :--- | :--- |
| **HTTP 400 Bad Request** | `UNSUPPORTED_STATION_SCOPE` | Station ID is outside pilot scope (`ANAND_VIHAR_8118`). |
| **HTTP 400 Bad Request** | `INVALID_TIMESTAMP` | Prediction timestamp is missing or malformed. |
| **HTTP 400 Bad Request** | `MISSING_FEATURES` | Required manifest feature columns missing from payload. |
| **HTTP 400 / 422** | `INVALID_FEATURE_VALUES` | Payload contains non-numeric, `null`, `NaN`, or infinite values. |
| **HTTP 503 Service Unavailable** | `MODEL_NOT_AVAILABLE` | LightGBM model boosters or manifest artifacts missing on server. |
| **HTTP 503 Service Unavailable** | `UNCERTAINTY_ARTIFACT_INVALID` | Conformal uncertainty metrics file missing or unreadable. |
| **HTTP 500 Internal Error** | `INFERENCE_ERROR` | Unexpected server execution exception (stack traces masked). |

---

## 4. Security & Operational Guardrails

1. **Information Disclosure Prevention:** Server exception details, Python tracebacks, absolute filesystem paths, and model file locations are never returned to clients.
2. **Station Isolation:** Unsupported stations are immediately rejected with HTTP 400 (`UNSUPPORTED_STATION_SCOPE`), preventing accidental extrapolation of the single-station pilot model.
3. **Raw Output Integrity:** Point forecasts and conformal lower/upper bounds are returned raw and unclipped without artificial clamping.
