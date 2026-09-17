# VayuDrishti — Multi-Source Evidence Fusion Foundation
**Phase:** PHASE 1E-H  
**Status:** COMPLETED & VERIFIED  
**Date:** September 2026  
**Implementation:** `backend/ingestion/evidence_fusion_engine.py`, `backend/api/v1/endpoints/fusion.py`

---

## 1. Executive Summary

Phase 1E-H establishes the **Multi-Source Evidence Fusion Foundation** for VayuDrishti. The fusion engine provides a deterministic, rule-based, completely offline evidence synthesis engine that correlates crowdsourced citizen reports with independently established environmental telemetry and geospatial layers.

Crucially, the engine strictly maintains the scientific distinction:
$$\text{OBSERVATION} \ne \text{SIGNAL} \ne \text{INFERENCE} \ne \text{PREDICTION} \ne \text{RISK}$$

It **never** asserts that a pollution source is causally proven. Instead, it measures qualitative spatial and temporal correlation across 6 distinct evidence families to produce a transparent, reproducible **Support Score (0.0 – 100.0)** and qualitative **Confidence Tier** (`LOW_SUPPORT`, `MODERATE_SUPPORT`, `HIGH_SUPPORT`).

---

## 2. Core Scientific & System Boundaries

1. **Deterministic Rule-Based Logic:** The engine operates without relying on non-deterministic external AI model calls or opaque ML black boxes during fusion scoring.
2. **Offline Execution:** Execution is 100% offline, scanning locally persisted JSON, JSONL, and GeoJSON artifacts under `data/processed/`.
3. **Event Anchoring:** All multi-source matching is anchored to a citizen evidence report (`ev_<uuid_hex>`) with WGS84 geolocation and ISO 8601 submission timestamp.
4. **Single Evidence Family Grouping:** Citizen Report and Gemini Multimodal AI Analysis are grouped as 1 single evidence family (`CITIZEN_GEMINI`) to prevent double-counting.
5. **No Negative Penalty for Missing Data:** Absent environmental data layers are classified under `unavailable_signals` rather than penalizing the event with negative score reductions.
6. **Explicit Conflicting Signal Categorization:** Baseline clean sensor readings matched within distance/time windows are categorized under `conflicting_signals`.

---

## 3. Evidence Families & Weight Allocation

The total Support Score is capped at 100.0 points across 6 independent evidence families:

| Evidence Family (`source_family`) | Data Source | Max Weight | Proximity & Temporal Windows | Scoring Criteria |
| :--- | :--- | :---: | :--- | :--- |
| **`CITIZEN_GEMINI`** | Citizen Intake & Gemini AI | **25 pts** | Anchored (`0 km / 0 min`) | Base report: 10 pts; Gemini relevant + high confidence: 25 pts; partial: 18 pts. |
| **`AIR_QUALITY`** | OpenAQ CAAQMS | **25 pts** | $\le 10\text{ km}$, $\le 60\text{ min}$ | $d \le 1\text{km}$ & elevated PM2.5/PM10: 25 pts; $d \le 3\text{km}$: 20 pts; $d \le 10\text{km}$: 12 pts; baseline value: Conflicting. |
| **`THERMAL_ANOMALY`** | NASA FIRMS VIIRS/MODIS | **15 pts** | $\le 15\text{ km}$, $\le 720\text{ min}$ | $d \le 3\text{km}$ & FRP $\ge 5\text{MW}$: 15 pts; $d \le 10\text{km}$: 10 pts; $d \le 15\text{km}$: 5 pts. |
| **`WEATHER`** | Open-Meteo Weather | **15 pts** | $\le 25\text{ km}$, $\le 180\text{ min}$ | Stagnant wind $\le 2.0\text{ m/s}$: 15 pts; $\le 3.5\text{ m/s}$: 10 pts; higher wind: 5 pts. |
| **`SATELLITE_NO2`** | Sentinel-5P TROPOMI | **10 pts** | $\le 30\text{ km}$, $\le 1440\text{ min}$ | $d \le 15\text{km}$: 10 pts; $d \le 30\text{km}$: 5 pts. |
| **`GEOSPATIAL_CONTEXT`** | OpenStreetMap Layers | **10 pts** | $\le 5\text{ km}$ (static layer) | Industrial zone / highway $d \le 2\text{km}$: 10 pts; $d \le 5\text{km}$: 5 pts. |

---

## 4. Confidence Tiering Scale

$$\text{Support Score} = \sum_{i=1}^{6} \text{FamilyScore}_i \quad \in [0.0, 100.0]$$

- **`HIGH_SUPPORT` ($\ge 70.0$ pts):** Multi-source alignment across majority of independent observation families (e.g. Citizen + OpenAQ + FIRMS + Stagnant Weather).
- **`MODERATE_SUPPORT` ($40.0 - 69.9$ pts):** Partial multi-source alignment (e.g. Citizen + OpenAQ or Citizen + FIRMS).
- **`LOW_SUPPORT` ($< 40.0$ pts):** Isolated citizen observation without corroborating environmental telemetry.

---

## 5. Artifact Storage & Provenance

Fusion results are persisted to `data/processed/fusion/<fusion_id>.json` where `<fusion_id>` is `fu_<uuid_hex>`.

```json
{
  "fusion_id": "fu_8f291a7c3b4e4d6fa01e92c184712019",
  "event_anchor_id": "ev_f47a112233445566778899aabbccdd00",
  "created_at": "2026-09-17T23:56:00Z",
  "support_score": 85.0,
  "confidence_tier": "HIGH_SUPPORT",
  "supporting_signals": [
    {
      "source_family": "CITIZEN_GEMINI",
      "source_type": "CitizenReport_GeminiCombined",
      "record_id": "ev_f47a112233445566778899aabbccdd00",
      "distance_km": 0.0,
      "time_difference_minutes": 0.0,
      "key_values": { "category": "industrial_smoke", "gemini_relevance": "relevant" },
      "provenance_ref": "data/processed/citizen_evidence/manifests/ev_f47a112233445566778899aabbccdd00.json"
    },
    {
      "source_family": "AIR_QUALITY",
      "source_type": "OpenAQ",
      "record_id": "openaq_st_1",
      "distance_km": 0.55,
      "time_difference_minutes": 0.0,
      "key_values": { "pollutant": "PM2.5", "value": 185.0, "unit": "µg/m³" },
      "provenance_ref": "data/processed/openaq_delhi_observations.jsonl"
    }
  ],
  "unavailable_signals": [],
  "conflicting_signals": [],
  "explanation": "Multi-source evidence fusion evaluated support score of 85.0/100 (HIGH_SUPPORT). Supporting evidence families matched: [CITIZEN_GEMINI, AIR_QUALITY, THERMAL_ANOMALY, WEATHER, SATELLITE_NO2, GEOSPATIAL_CONTEXT].",
  "uncertainty_notes": [
    "Observations correlate spatially and temporally but do NOT establish causal pollution source proof."
  ],
  "provenance_sources": [
    "data/processed/citizen_evidence/manifests/ev_f47a112233445566778899aabbccdd00.json",
    "data/processed/openaq_delhi_observations.jsonl"
  ],
  "config_version": "1.0-provisional",
  "schema_version": "1.0"
}
```

---

## 6. REST API Endpoints

- **`POST /api/v1/fusion/evidence/{evidence_id}`**: Triggers multi-source evidence fusion for an ingested citizen report. Returns `EvidenceFusionResult`.
- **`GET /api/v1/fusion/{fusion_id}`**: Retrieves a persisted fusion result artifact by `fusion_id` (or `evidence_id`).

---

## 7. Verification & Regression Coverage

Full test suite in `tests/test_evidence_fusion.py` verifies:
- Haversine distance and time difference calculations.
- Enforced spatial & temporal matching windows.
- Single evidence family grouping (Citizen + Gemini).
- Scenarios A through G (Strong support, Citizen only, Conflicting AQ, Partial sources, Poor spatial, Poor temporal, Thermal only).
- REST API endpoint behavior and idempotent file persistence.
- Complete regression suite (109 passing unit/integration tests).
