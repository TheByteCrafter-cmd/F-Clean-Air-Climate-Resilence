# VayuDrishti — Decision Intelligence API Specification

**Phase**: 1E-J2E.4.5  
**Endpoint**: `POST /api/v1/decision`  
**Status**: OPERATIONAL  

---

## 1. Executive Summary & Architecture

The Decision Intelligence API (`POST /api/v1/decision`) provides a single, unified HTTP interface to the authoritative `DecisionIntelligenceEngine`. It synthesizes multi-horizon PM2.5 forecasts (+1h, +3h, +6h), conformal uncertainty bounds, corroborating thermal/spatial hotspots, and geospatial exposure contexts into a time-bounded, prioritized, human-reviewable Decision Intelligence artifact.

```
 Client Request (JSON)
          │
          ▼
   POST /api/v1/decision  ──(Pydantic Request Validation)
          │
          ▼
   DecisionIntelligenceEngine.orchestrate()
   ┌────────────────────────────────────────────────────────┐
   │ 1. Station Scope Validation (ANAND_VIHAR_8118)         │
   │ 2. RiskAssessmentEngine.assess_risk()                   │
   │ 3. ActionRecommendationEngine.recommend_actions()       │
   │ 4. Status Precedence (BLOCKED > PARTIAL > READY)       │
   │ 5. Earliest Expiry Timestamp Rule                      │
   │ 6. Non-Causal Summary Generation                      │
   └────────────────────────────────────────────────────────┘
          │
          ▼
   HTTP 200 OK (JSON Response with requires_human_review = True)
```

---

## 2. Request & Response Schemas

### 2.1 Request Schema (`DecisionIntelligenceRequest`)

```json
{
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
  "hotspot_detected": true,
  "hotspot_id": "hs_av_20260330_01",
  "hotspot_support_score": 85.0,
  "hotspot_spatial_extent": 4.5,
  "hotspot_source_families": ["INDUSTRIAL_STACK", "TRAFFIC_CORRIDOR"],
  "industrial_context": true,
  "major_road_context": true,
  "sensitive_receptor_context": true,
  "forecast_result_id": "fc_av_20260330_12",
  "fusion_id": "fus_av_20260330_12",
  "context_artifact_id": "ctx_av_20260330_01"
}
```

### 2.2 Response Schema (`DecisionIntelligenceResponse`)

```json
{
  "status": "SUCCESS",
  "decision_result_id": "dec_7184da4be2f7",
  "station_id": "ANAND_VIHAR_8118",
  "prediction_timestamp": "2026-03-30T12:00:00Z",
  "created_timestamp": "2026-09-19T19:46:52Z",
  "expires_timestamp": "2026-03-30T13:00:00Z",
  "forecast_status": "READY",
  "risk_status": "READY",
  "action_status": "READY",
  "overall_data_quality_status": "READY",
  "forecast_reference": {
    "forecast_result_id": "fc_av_20260330_12",
    "status": "READY",
    "prediction_timestamp": "2026-03-30T12:00:00Z"
  },
  "risk_reference": {
    "assessment_id": "risk_c1a62ee6bb06",
    "risk_score": 88.14,
    "risk_level": "VERY_HIGH",
    "data_quality_status": "READY"
  },
  "action_reference": {
    "result_id": "act_a4fbd76177a3",
    "recommendation_count": 6,
    "status": "READY"
  },
  "evidence_references": {
    "forecast_result_id": "fc_av_20260330_12",
    "assessment_id": "risk_c1a62ee6bb06",
    "action_result_id": "act_a4fbd76177a3",
    "hotspot_id": "hs_av_20260330_01",
    "fusion_id": "fus_av_20260330_12",
    "context_artifact_id": "ctx_av_20260330_01"
  },
  "risk_score": 88.14,
  "risk_level": "VERY_HIGH",
  "recommendation_count": 6,
  "recommendations": [ ... ],
  "missing_evidence": [],
  "decision_summary": "Anand Vihar 8118 environmental decision intelligence assessment yields a risk score of 88.1 (VERY_HIGH risk level)...",
  "requires_human_review": true,
  "model_scope": "Anand Vihar 8118 station-level pilot",
  "calculation_version": "1.0",
  "non_medical_disclaimer": "VayuDrishti action recommendations are operational environmental decision-support suggestions for human authority review...",
  "non_causal_disclaimer": "Decision intelligence outputs synthesize environmental forecast, risk, and action evidence..."
}
```

---

## 3. HTTP Status Codes & Error Behavior

| HTTP Code | Condition | Behavior / Response Body |
| :--- | :--- | :--- |
| **200 OK** | Valid decision request (including domain `BLOCKED` states) | Returns full `DecisionIntelligenceResponse` payload with preserved statuses |
| **422 Unprocessable Entity** | Malformed JSON, missing required fields, or non-finite float values | Structured Pydantic validation error envelope (`code: "VALIDATION_ERROR"`) |
| **503 Service Unavailable** | Engine initialization or singleton dependency failure | Structured error response (`code: "DECISION_SERVICE_UNAVAILABLE"`) |
| **500 Internal Server Error** | Unexpected internal server exception | Structured error response (`code: "DECISION_ORCHESTRATION_ERROR"`) |

---

## 4. Key Transport & Policy Invariants

1. **Mandatory Human Review Invariant (`requires_human_review = true`)**:
   - The request payload schema (`DecisionIntelligenceRequest`) does NOT expose `requires_human_review`.
   - If a client attempts to send `"requires_human_review": false` in the request JSON, it is ignored by the parser and the API response **ALWAYS** returns `"requires_human_review": true`.

2. **Domain Status Preservation**:
   - `forecast_status`, `risk_status`, `action_status`, and `overall_data_quality_status` are preserved exactly as produced by `DecisionIntelligenceEngine`.
   - Precedence rule: $\text{overall\_data\_quality\_status} = \text{BLOCKED} > \text{PARTIAL} > \text{READY}$.

3. **Pilot Station Scope**:
   - Strictly bounded to `ANAND_VIHAR_8118` (and alias `8118`).
   - Unsupported stations return HTTP 200 with `overall_data_quality_status = "BLOCKED"` and `risk_level = "UNSUPPORTED_STATION_SCOPE"`.

4. **Zero Live Network Dependencies**:
   - The API operates 100% offline without live external API calls (OpenAQ, NASA FIRMS, Sentinel, Open-Meteo).

5. **No Medical / No Automated Enforcement Guarantees**:
   - All recommendations are decision-support suggestions for human authority review.
   - Non-medical and non-causal disclaimers are attached to every response artifact.
