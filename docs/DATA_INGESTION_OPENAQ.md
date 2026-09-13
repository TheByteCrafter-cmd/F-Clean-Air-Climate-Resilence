# VayuDrishti Air Quality Ingestion Architecture ? OpenAQ v3
## Phase 1E-A Specification: Ingestion Pipeline, Normalization, Validation & Provenance Contracts

**Status:** PHASE 1E-A COMPLETE  
**Project:** VayuDrishti ? Clean Air & Climate Resilience  
**Local Project Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  
**Remote Repository:** `https://github.com/TheByteCrafter-cmd/F-Clean-Air-Climate-Resilence.git`  
**Pipeline Version:** `1.0`  
**Target Pilot Corridor:** Delhi NCR (Connaught Place, Anand Vihar, Punjabi Bagh, Mandir Marg)  

---

## 1. Role of OpenAQ v3 in VayuDrishti

OpenAQ acts as the standardized aggregator and physical normalization gateway for Indian regulatory air quality telemetry. Instead of relying on fragile, unversioned web scraping of state pollution control portals (such as Delhi DPCC or Central CPCB), VayuDrishti connects directly to OpenAQ REST API v3 to ingest continuous ambient air quality monitoring station (CAAQMS) readings.

### Core Architectural Responsibilities:
- **Baseline Ambient Ground Truth:** Supplies baseline ground-level microgram concentrations ($\mu\text{g/m}^3$) across critical criteria pollutants.
- **Physical Ground Correlation:** Serves as the ground receptor baseline against which downwind plume dispersion models, satellite columns (Sentinel-5P NO2), and thermal anomalies (NASA FIRMS) are correlated.
- **Auditable Lineage:** Preserves exact upstream sensor identifiers, station coordinates, and fetch timestamps.

---

## 2. Authentication Requirements & Credential Safety

OpenAQ API v3 strictly mandates an API key for all queries (HTTP 401 Unauthorized is returned without authentication).

### Strict Security Rules:
1. **Environment Variable:** The API key is read strictly from the `OPENAQ_API_KEY` environment variable (via `.env`).
2. **Zero Leaks:** The API key is **NEVER** hardcoded, logged, written into raw data files, embedded in error payloads, or exposed to the frontend client.
3. **Graceful Degradation:** If `OPENAQ_API_KEY` is not present:
   - The system **does not crash or throw unhandled exceptions**.
   - Live network requests are aborted with a clean, informative message:  
     `"Live OpenAQ verification skipped because OPENAQ_API_KEY is not configured."`
   - Automated unit tests and offline demonstrations use sanitized local recorded fixtures located in `tests/fixtures/openaq_delhi_sample.json`.

---

## 3. Configuration Contract

| Environment Variable | Description | Default / Example | Required for Offline | Required for Live |
| :--- | :--- | :--- | :---: | :---: |
| `OPENAQ_API_KEY` | Upstream OpenAQ v3 API Key | *(Secret token)* | No | **Yes** |
| `LOCAL_DATA_DIR` | Base directory for data storage | `./data` | Yes | Yes |

---

## 4. Endpoints & Query Strategy

OpenAQ REST API v3 base URL:  
`https://api.openaq.org/v3`

### Endpoints Implemented:
1. **`GET /v3/locations`**:
   - **Query Parameters:**
     - `coordinates`: `28.6139,77.2090` (Delhi city center)
     - `radius`: `25000` (25 km bounding radius)
     - `limit`: Controlled small batch (`3` locations default)
     - `iso`: `IN` (India)
   - **Purpose:** Discovers active reference monitoring stations in the Delhi pilot corridor.
2. **`GET /v3/locations/{locations_id}/latest`**:
   - **Purpose:** Fetches the most recent sensor measurements for each discovered station.
3. **`GET /v3/locations/{locations_id}/sensors`**:
   - **Purpose:** Inspects hardware sensor properties and parameter metadata.

---

## 5. Controlled Request & Rate Limiting Strategy

To prevent quota exhaustion and unnecessary network traffic:
- **Batch Size:** Controlled to 3 locations per ingestion run.
- **Timeout:** Explicit 15.0-second HTTP request timeout (`httpx.Timeout(15.0)`).
- **Retry Policy:** Up to 2 retries with exponential backoff (`0.5s`, `1.0s`) strictly for transient errors (HTTP 5xx, network timeouts).
- **Immediate Failure:** No retries on HTTP 401 (Authentication), 403 (Forbidden), 404 (Not Found), or 429 (Rate Limit).

---

## 6. Raw Data Handling & Sanitization

Every ingestion run creates an immutable snapshot of the raw upstream API payload:
- **Location:** `data/raw/openaq_delhi_sample_<timestamp>.json`
- **Sanitization Guarantee:** Raw payloads are parsed and sanitized to ensure no query strings containing secrets or authorization headers are written to disk.
- **Traceability Metadata:**
  ```json
  {
    "metadata": {
      "source": "OpenAQ REST API v3",
      "base_url": "https://api.openaq.org/v3",
      "retrieved_at": "2026-09-13T18:08:38Z",
      "query": {
        "target": "Delhi NCR Pilot",
        "coordinates": "28.6139,77.2090",
        "radius_meters": 25000,
        "location_limit": 3
      },
      "locations_retrieved": 3
    }
  }
  ```

---

## 7. Normalization Engine

The normalization engine (`backend/ingestion/normalizer.py`) converts heterogeneous raw reading structures into canonical `EnvironmentalObservation` models.

### 7.1 Pollutant Mapping
| OpenAQ Parameter Name | Canonical Pollutant Name |
| :--- | :---: |
| `pm25`, `pm2.5`, `pm_25`, `pm 2.5` | **PM2.5** |
| `pm10`, `pm_10`, `pm 10` | **PM10** |
| `no2`, `nitrogen dioxide` | **NO2** |
| `so2`, `sulfur dioxide` | **SO2** |
| `co`, `carbon monoxide` | **CO** |
| `o3`, `ozone` | **O3** |
| *Other parameters (e.g. wind_speed, temperature)* | *Rejected / Flagged* |

### 7.2 Unit Normalization Rules
- **Canonical Unit:** `?g/m?` (micrograms per cubic meter).
- **Variants Normalized:** `ug/m3`, `ug/m^3`, `?g/m3`, `ug/m?`, `ugm-3` $\rightarrow$ `?g/m?`.
- **CO Conversion:** When carbon monoxide arrives in milligrams per cubic meter (`mg/m?`):  
  $$\text{Value}_{\mu\text{g/m}^3} = \text{Value}_{\text{mg/m}^3} \times 1000.0$$  
  The conversion is deterministic and recorded in `raw_payload.unit_note`.
- **Unknown Units:** If unit conversion is not deterministically defined, the source unit is preserved and the record is flagged.

### 7.3 Timestamp Parsing
- Upstream ISO-8601 strings or OpenAQ `DatetimeObject` structures (`{'utc': '...', 'local': '...'}`) are parsed into Python timezone-aware UTC `datetime` instances.

### 7.4 Physical Concentration Bounds
- Concentrations must be non-negative ($value \ge 0.0$). Negative values caused by sensor baseline drift (e.g. $-8.5\,\mu\text{g/m}^3$) are strictly flagged as physical violations and rejected.

---

## 8. Validation, Deduplication & Data Quality

Every candidate record undergoes automated auditing via `ObservationValidator` (`backend/ingestion/validator.py`).

### 8.1 Validation Rules:
1. **Coordinate Validity:** $-90.0 \le \text{latitude} \le 90.0$ and $-180.0 \le \text{longitude} \le 180.0$.
2. **Temporal Sanity:** Timestamp not null and not more than 24 hours in the future.
3. **Physical Feasibility:** Concentration value $\ge 0.0$.
4. **Pollutant Validity:** Must belong to the canonical criteria pollutant set.
5. **Completeness:** Non-empty unit and non-empty source attribution.

### 8.2 Idempotency & Deduplication Strategy
To avoid duplicate canonical records across repetitive runs or overlapping query windows, each observation receives a deterministic fingerprint:
$$\text{Fingerprint} = \text{station\_id} + \text{":"} + \text{pollutant} + \text{":"} + \text{timestamp\_iso}$$
If the fingerprint has already been recorded during the run, the record is flagged as `DUPLICATE`, excluded from the processed output, and tallied in the quality report.

---

## 9. Storage Paths & Formats

All ingestion outputs reside within the locked project directory:

```
data/
??? raw/
?   ??? openaq_delhi_sample_<YYYYMMDD_HHMMSS>.json    # Sanitized raw API response
??? processed/
    ??? openaq_delhi_observations_<YYYYMMDD_HHMMSS>.jsonl  # Canonical EnvironmentalObservation records
    ??? openaq_delhi_validation_report_<YYYYMMDD_HHMMSS>.json # Machine-readable quality metrics
    ??? openaq_delhi_validation_report_<YYYYMMDD_HHMMSS>.md   # Human-readable quality report
```

### Format Specification:
- **`observations.jsonl`:** JSON Lines format. Each line contains an independent, fully self-contained `EnvironmentalObservation` object adhering to the canonical schema:
  ```json
  {
    "timestamp": "2026-09-13T16:00:00Z",
    "location": {
      "latitude": 28.6476,
      "longitude": 77.3158,
      "address": "Anand Vihar, Delhi - DPCC"
    },
    "pollutant": "PM2.5",
    "value": 142.5,
    "unit": "?g/m?",
    "source": "CPCB_CAAQMS",
    "station_id": "ANAND_VIHAR_8118",
    "source_record_id": "openaq-loc-8118-sensor-24151-PM2.5-20260913160000",
    "retrieved_at": "2026-09-13T18:08:38.981179Z",
    "source_url": "https://api.openaq.org/v3/locations/8118",
    "normalization_version": "1.0",
    "raw_payload": { ... }
  }
  ```

---

## 10. Command-Line Usage

The pipeline can be executed directly from the terminal via `scripts/ingest_openaq.py`:

```bash
# Offline verification run using sanitized fixture (default when key is absent)
python scripts/ingest_openaq.py

# Explicit offline run with custom fixture
python scripts/ingest_openaq.py --fixture tests/fixtures/openaq_delhi_sample.json

# Live OpenAQ fetch (requires OPENAQ_API_KEY in .env)
python scripts/ingest_openaq.py --live --limit 3
```

---

## 11. Testing & Verification Summary

### 11.1 Distinction Between Live Verified and Unit Tested

| Component | Status | Notes |
| :--- | :---: | :--- |
| **OpenAQ v3 API Key Requirement** | **LIVE VERIFIED** | Empirically verified in Phase 1D (HTTP 401 without key). |
| **OpenAQ v3 OpenAPI Schemas** | **LIVE VERIFIED** | Extracted from `https://api.openaq.org/openapi.json`. |
| **Normalization Engine** | **UNIT TESTED** | 100% test coverage using sanitized Delhi fixture. |
| **Observation Validation & Deduplication** | **UNIT TESTED** | Verified physical checks, out-of-bounds, duplicates. |
| **Controlled Ingestion Pipeline** | **UNIT TESTED** | Verified end-to-end fixture execution to `.jsonl`. |
| **Live OpenAQ Ingestion Run** | **SKIPPED (GRACEFUL)** | `OPENAQ_API_KEY` not configured in development environment. |

### 11.2 Test Execution Results
All **20/20** automated tests pass cleanly:
- `10/10` Phase 1B API Contract Tests
- `10/10` Phase 1E-A OpenAQ Ingestion Tests

```
======================= 20 passed, 2 warnings in 0.69s ========================
```

---

## 12. Known Limitations & Future Phase Scope

1. **Diurnal Gaps:** CAAQMS stations report periodically (typically hourly). Sensor maintenance can result in occasional null windows.
2. **Spatial Density:** Fixed regulatory stations provide sparse spatial resolution (~40 stations across Delhi NCT). Phase 2 and Phase 4 will fuse satellite raster plumes and citizen crowdsourced reports to bridge inter-station gaps.
3. **No AQI Calculation in Phase 1E-A:** Raw concentration data ($\mu\text{g/m}^3$) is intentionally kept distinct from Indian National Air Quality Index (NAQI) sub-indices, which are computed in downstream analytics phases.
