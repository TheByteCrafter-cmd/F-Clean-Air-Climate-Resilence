# VayuDrishti API Architecture Contract
## Phase 1B Specification & Domain Contracts
**Status:** PHASE 1E-H — MULTI-SOURCE EVIDENCE FUSION OPERATIONAL  
**Target API Version:** v1  
**Default Base URL:** `http://localhost:8000`  
**Frontend Client:** Typed Fetch Client (`frontend/src/api/client.ts`)  

---

## 1. API Versioning Strategy

VayuDrishti enforces an explicit, URI-path-based versioning prefix for all functional domain micro-routes:

```
/api/v1/{domain}
```

### Backward Compatibility Guarantee
The foundational health probe endpoint established in Phase 1A remains available at:
```
GET /api/health
```
This ensures that container health probes (Google Cloud Run, Kubernetes liveness checks, and basic operational monitors) remain stable without coupling to major API version migrations.

---

## 2. Base Endpoints & Operational Verification

### 2.1 Backward-Compatible Health Probe
- **Path:** `GET /api/health`
- **Purpose:** System availability check for infra orchestration and local dev verification.
- **Request Parameters:** None
- **Response Format (200 OK):**
```json
{
  "status": "ok",
  "service": "VayuDrishti API",
  "phase": "1b",
  "timestamp": "2026-09-13T00:30:00Z"
}
```

### 2.2 Versioned API Status
- **Path:** `GET /api/v1/status`
- **Purpose:** Verifies that API version 1 router and schema registry are loaded.
- **Request Parameters:** None
- **Response Format (200 OK):**
```json
{
  "status": "ok",
  "version": "v1",
  "message": "VayuDrishti API v1 skeleton is operational."
}
```

---

## 3. Domain Boundaries

Future operational services in VayuDrishti are partitioned across domain boundaries:

| Domain Boundary | Architectural Responsibility | Planned Phase | Status |
| :--- | :--- | :---: | :---: |
| **Environmental Observations** | Ingestion, normalization, and temporal caching of CAAQMS (OpenAQ) and meteorology (Open-Meteo). | Phase 1E-A/B | **Ingestion Operational** |
| **Satellite Signals** | NASA FIRMS thermal anomaly & Sentinel-5P NO2 column density. | Phase 1E-C/D | **Ingestion Operational** |
| **Geospatial Intelligence** | OSM industrial zones, highways, sensitive receptors, ward boundaries. | Phase 1E-E | **Ingestion Operational** |
| **Citizen Evidence** | Crowdsourced photo/audio evidence intake, anti-abuse filtering, and Gemini multimodal triage. | Phase 1E-F/G | **Operational** |
| **Evidence Fusion** | Deterministic multi-source evidence fusion correlating observations around event anchors. | Phase 1E-H | **OPERATIONAL** |
| **Hotspot Intelligence** | Spatial kriging baseline vs. micro-sensor residual scoring and DBSCAN cluster boundary detection. | Phase 2 | *Planned* |
| **Corridor Forecasting** | LightGBM gradient-boosted 1h, 3h, 6h PM2.5 tabular projections with confidence interval bounds. | Phase 3 | *Planned* |
| **Risk Assessment** | Hazard severity x confidence x sensitive receptor vulnerability scoring. | Phase 4 | *Planned* |
| **Authority Decision Support** | Statutory GRAP mitigation directive matching and flying squad dispatch lifecycle. | Phase 5 | *Planned* |

---

## 4. Request & Response Conventions

1. **Protocol:** HTTP/1.1 and HTTP/2 over TLS (production) or cleartext (local dev).
2. **Payload Serialization:** Strict `application/json; charset=utf-8` for all request bodies and standard responses.
3. **Field Naming Convention:**
   - JSON keys: `snake_case` (e.g., `evidence_id`, `support_score`, `confidence_tier`).
   - Query parameters: `snake_case` (e.g., `?horizon=3h&pollutant=PM2.5`).
   - Pydantic/TypeScript Model Names: `PascalCase` (e.g., `EvidenceFusionResult`, `MatchedRecordRef`).
4. **Time Format:** ISO 8601 UTC representation (e.g., `YYYY-MM-DDTHH:mm:ssZ`).
5. **Spatial Coordinates:** WGS 84 (`EPSG:4326`) format:
   - Latitude: $-90.0 \le \text{lat} \le 90.0$
   - Longitude: $-180.0 \le \text{lon} \le 180.0$

---

## 5. Standardized Error Envelope

All HTTP errors (4xx and 5xx) return a deterministic error wrapper to prevent client-side parsing failures and avoid exposing internal server stack traces:

```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable description of error.",
    "details": null
  }
}
```

### Standard Error Codes

| HTTP Status | Error Code (`code`) | Meaning |
| :--- | :--- | :--- |
| **400** | `INVALID_EVIDENCE_ID` / `FUSION_ERROR` | Malformed parameters or unprocessable request. |
| **404** | `ANCHOR_NOT_FOUND` / `FUSION_RESULT_NOT_FOUND` | Requested evidence manifest or fusion artifact does not exist. |
| **422** | `VALIDATION_ERROR` | Request body failed Pydantic schema validation. |
| **500** | `PERSISTENCE_ERROR` / `INTERNAL_FUSION_ERROR` | Server storage or execution fault handled safely. |

---

## 6. Core Data Schemas (Frozen Pydantic & TypeScript Contracts)

### 6.1 Spatial Location
```typescript
interface Location {
  latitude: number;   // -90.0 to 90.0
  longitude: number;  // -180.0 to 180.0
  address?: string | null;
}
```

### 6.2 Temporal Range
```typescript
interface TimeRange {
  start_time: string; // ISO 8601 UTC
  end_time: string;   // ISO 8601 UTC (must be >= start_time)
}
```

### 6.3 Environmental Observation
```typescript
interface EnvironmentalObservation {
  timestamp: string;
  location: Location;
  pollutant: string;       // e.g. "PM2.5", "PM10", "NO2", "AQI"
  value: number;           // >= 0.0
  unit: string;            // e.g. "µg/m³", "AQI"
  source: string;          // e.g. "CAAQMS", "IoT_Sensor"
  station_id?: string | null;
}
```

### 6.4 Multi-Source Evidence Fusion Schema (Phase 1E-H)
```typescript
interface MatchedRecordRef {
  source_family: string;   // "CITIZEN_GEMINI" | "AIR_QUALITY" | "THERMAL_ANOMALY" | "WEATHER" | "SATELLITE_NO2" | "GEOSPATIAL_CONTEXT"
  source_type: string;     // e.g. "OpenAQ", "NASA_FIRMS", "OpenMeteo", "Sentinel-5P_TROPOMI", "OpenStreetMap"
  record_id: string;
  distance_km?: number | null;
  time_difference_minutes?: number | null;
  key_values: Record<string, unknown>;
  provenance_ref: string;
}

interface EvidenceFusionResult {
  fusion_id: string;              // fu_<uuid_hex>
  event_anchor_id: string;        // ev_<uuid_hex>
  created_at: string;             // ISO 8601 UTC
  support_score: number;          // 0.0 to 100.0
  confidence_tier: 'LOW_SUPPORT' | 'MODERATE_SUPPORT' | 'HIGH_SUPPORT';
  supporting_signals: MatchedRecordRef[];
  unavailable_signals: string[];
  conflicting_signals: MatchedRecordRef[];
  explanation: string;
  uncertainty_notes: string[];
  provenance_sources: string[];
  config_version: string;
  schema_version: string;
}
```

---

## 7. Operational Endpoint Roadmap

| Method | Endpoint Route | Planned Domain | Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System Health | **OPERATIONAL (Phase 1A/1B)** |
| `GET` | `/api/v1/status` | API Registry | **OPERATIONAL (Phase 1B)** |
| `POST` | `/api/v1/evidence` | Citizen Evidence Intake | **OPERATIONAL (Phase 1E-F)** |
| `POST` | `/api/v1/evidence/{evidence_id}/analyze` | Gemini Multimodal Evidence Analysis | **OPERATIONAL (Phase 1E-G)** |
| `GET` | `/api/v1/evidence/{evidence_id}/analysis` | Gemini AI Analysis Artifact | **OPERATIONAL (Phase 1E-G)** |
| `POST` | `/api/v1/fusion/evidence/{evidence_id}` | Multi-Source Evidence Fusion | **OPERATIONAL (Phase 1E-H)** |
| `GET` | `/api/v1/fusion/{fusion_id}` | Evidence Fusion Result Artifact | **OPERATIONAL (Phase 1E-H)** |
| `GET` | `/api/v1/observations/latest` | Observations | *PLANNED* |
| `GET` | `/api/v1/hotspots/active` | Hotspot Intelligence | *PLANNED* |

---
**PHASE 1E-H MULTI-SOURCE EVIDENCE FUSION CONTRACT:** OPERATIONAL & VERIFIED  
