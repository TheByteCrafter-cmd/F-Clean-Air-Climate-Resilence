# VayuDrishti API Architecture Contract
## Phase 1B Specification & Domain Contracts
**Status:** PHASE 1B — CONTRACT & SKELETON FROZEN  
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

Future operational services in VayuDrishti are partitioned across 8 decoupled domain boundaries:

| Domain Boundary | Architectural Responsibility | Planned Phase |
| :--- | :--- | :---: |
| **Environmental Observations** | Ingestion, normalization, and temporal caching of CAAQMS and low-cost sensor telemetry. | Phase 2 |
| **Geospatial Intelligence** | Base map layers, spatial indexing, administrative ward polygons, and spatial queries. | Phase 3 |
| **Citizen Evidence** | Crowdsourced photo/audio evidence intake, anti-abuse filtering, and Gemini multimodal triage. | Phase 4 |
| **Hotspot Intelligence** | Spatial kriging baseline vs. micro-sensor residual scoring and DBSCAN cluster boundary detection. | Phase 5 |
| **Corridor Forecasting** | LightGBM gradient-boosted 1h, 3h, 6h PM2.5 tabular projections with confidence interval bounds. | Phase 6 |
| **Evidence Fusion** | Bayesian/weighted multi-source evidence synthesis generating composite 0–100 Confidence Scores. | Phase 7 |
| **Risk Assessment** | Hazard severity x confidence x sensitive receptor vulnerability scoring. | Phase 7 |
| **Authority Decision Support** | Statutory GRAP mitigation directive matching and flying squad dispatch lifecycle. | Phase 8 |

---

## 4. Request & Response Conventions

1. **Protocol:** HTTP/1.1 and HTTP/2 over TLS (production) or cleartext (local dev).
2. **Payload Serialization:** Strict `application/json; charset=utf-8` for all request bodies and standard responses.
3. **Field Naming Convention:**
   - JSON keys: `snake_case` (e.g., `evidence_id`, `predicted_value`, `start_time`).
   - Query parameters: `snake_case` (e.g., `?horizon=3h&pollutant=PM2.5`).
   - Pydantic/TypeScript Model Names: `PascalCase` (e.g., `EnvironmentalObservation`, `HotspotSummary`).
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
| **400** | `BAD_REQUEST` | Malformed parameters or unprocessable request. |
| **404** | `HTTP_404` | Requested endpoint or resource entity does not exist. |
| **422** | `VALIDATION_ERROR` | Request body failed Pydantic schema validation (field errors in `details`). |
| **500** | `INTERNAL_SERVER_ERROR` | Unexpected server fault handled safely without stack leak. |

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

### 6.4 Citizen Evidence Metadata
```typescript
interface CitizenEvidenceMetadata {
  evidence_id: string;
  timestamp: string;
  location: Location;
  media_type: string;      // e.g. "image/jpeg", "audio/wav"
  description?: string | null;
  source: string;          // "citizen_report"
  category?: string | null;// e.g. "biomass_burning", "construction_dust"
}
```

### 6.5 Hotspot Summary
```typescript
interface HotspotSummary {
  hotspot_id: string;
  location: Location;
  severity: "LOW" | "MODERATE" | "HIGH" | "SEVERE";
  confidence: number;      // 0.0 to 100.0
  detected_at: string;
  radius_meters?: number | null;
}
```

### 6.6 Corridor Forecast Summary
```typescript
interface ForecastSummary {
  location: Location;
  pollutant: string;
  forecast_horizon: "1h" | "3h" | "6h";
  predicted_value: number; // >= 0.0
  confidence: number;      // 0.0 to 100.0
  lower_bound?: number | null; // P10 prediction interval
  upper_bound?: number | null; // P90 prediction interval
}
```

### 6.7 Risk Assessment Summary
```typescript
interface RiskSummary {
  risk_level: "LOW" | "MODERATE" | "HIGH" | "CRITICAL";
  confidence: number;      // 0.0 to 100.0
  contributing_signals: string[];
  affected_zone?: string | null;
}
```

### 6.8 Authority Recommendation & Action
```typescript
interface AuthorityRecommendation {
  recommendation_id: string;
  priority: "P1_URGENT" | "P2_ELEVATED" | "P3_ROUTINE";
  action: string;
  reason: string;
  grap_stage?: string | null; // e.g. "GRAP-III"
}
```

---

## 7. Frontend Typed API Client (`frontend/src/api/client.ts`)

Components must never issue raw `fetch` calls. All HTTP interaction is routed through the centralized `apiClient`:

```typescript
import { apiClient, ApiError } from '@/api/client';

// Example Phase 1B invocation:
try {
  const status = await apiClient.getV1Status();
  console.log('API V1 Online:', status.version);
} catch (err) {
  if (err instanceof ApiError) {
    console.error(`[${err.code}] ${err.message}`);
  }
}
```

---

## 8. Future Endpoint Roadmap

*The following routes represent the target contract for subsequent phases. In Phase 1B, they are planned architectural boundaries only.*

| Method | Endpoint Route | Planned Domain | Status |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | System Health | **OPERATIONAL (Phase 1A/1B)** |
| `GET` | `/api/v1/status` | API Registry | **OPERATIONAL (Phase 1B)** |
| `GET` | `/api/v1/observations/latest` | Observations | *NOT IMPLEMENTED IN PHASE 1B (Phase 2)* |
| `GET` | `/api/v1/observations/history` | Observations | *NOT IMPLEMENTED IN PHASE 1B (Phase 2)* |
| `POST` | `/api/v1/evidence/upload` | Citizen Evidence | *NOT IMPLEMENTED IN PHASE 1B (Phase 4)* |
| `GET` | `/api/v1/hotspots/active` | Hotspot Intelligence | *NOT IMPLEMENTED IN PHASE 1B (Phase 5)* |
| `GET` | `/api/v1/forecast/corridor` | Forecasting | *NOT IMPLEMENTED IN PHASE 1B (Phase 6)* |
| `GET` | `/api/v1/risk/summary` | Risk Assessment | *NOT IMPLEMENTED IN PHASE 1B (Phase 7)* |
| `GET` | `/api/v1/authority/tasks` | Decision Support | *NOT IMPLEMENTED IN PHASE 1B (Phase 8)* |
| `POST`| `/api/v1/authority/dispatch` | Decision Support | *NOT IMPLEMENTED IN PHASE 1B (Phase 8)* |

---
**PHASE 1B CONTRACT SIGN-OFF:** COMPLETED & FROZEN  
**NEXT PHASE:** PHASE 2 — ENVIRONMENTAL DATA INGESTION PIPELINE
