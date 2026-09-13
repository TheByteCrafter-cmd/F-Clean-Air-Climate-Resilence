# VayuDrishti ? NASA FIRMS Thermal Anomaly Ingestion Specification
## Phase 1E-C Documentation: Architecture, Ingestion, Normalization & Quality Auditing

**Status:** PHASE 1E-C ? NASA FIRMS INGESTION ESTABLISHED  
**Project:** VayuDrishti ? Clean Air & Climate Resilience  
**Local Project Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  
**Authoritative Documents:** `docs/DATA_ARCHITECTURE.md`, `docs/DATA_SOURCE_VERIFICATION.md`  

---

## 1. Role of NASA FIRMS in VayuDrishti

The Fire Information for Resource Management System (FIRMS), operated by NASA EOSDIS, delivers near-real-time thermal radiance detections from spaceborne spectroradiometers (VIIRS and MODIS).

Within the VayuDrishti architecture, NASA FIRMS provides a **supporting environmental signal representing active combustion / thermal anomalies**. It does **NOT** measure air quality directly.

```
???????????????????????????     ??????????????????????????     ????????????????????????
?  Continuous Air Quality ?     ?     Meteorological     ?     ?  Thermal Anomalies   ?
?   Ground CAAQMS PM2.5   ?     ? Boundary Layer & Winds ?     ?   NASA FIRMS VIIRS   ?
?    (OpenAQ v3 API)      ?     ?   (Open-Meteo API)     ?     ? (Regional CSV Stream)?
???????????????????????????     ??????????????????????????     ????????????????????????
             ?                              ?                             ?
             ??????????????????????????????????????????????????????????????
                                            ?
                           ????????????????????????????????????
                           ?    Future Multi-Source Fusion    ?
                           ?   (Phase 2 Correlation Engine)   ?
                           ????????????????????????????????????
```

---

## 2. Product and Data Source Used

* **Product:** Suomi-NPP VIIRS Collection 2 (C2) 375m Active Fire Near-Real-Time (NRT).
* **Primary Regional Feed:** `SUOMI_VIIRS_C2_South_Asia_24h.csv`
* **Upstream URL:**
  `https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_24h.csv`
* **Sensor / Instrument:** Visible Infrared Imaging Radiometer Suite (VIIRS).
* **Nominal Ground Pixel Resolution:** 375 meters at nadir (I-bands: I4 thermal at 3.74 ?m, I5 thermal at 11.45 ?m).
* **Revisit Cadence:** Twice daily overpass per satellite (approx. 13:30 daytime, 01:30 nighttime local solar time).

---

## 3. Authentication & Access Strategy

* **Regional Stream Protocol:** Open HTTP GET, zero authentication required.
* **Licensing:** NASA Open Data Policy (Public Domain).
* **Secondary Keyed API Support:** The client optionally supports the targeted area API (`/api/area/csv/{map_key}/...`) via the environment variable `NASA_FIRMS_MAP_KEY`.
* **Security Rule:** No API keys are hardcoded, logged, or exposed client-side.

---

## 4. Retrieval & Ingestion Strategy

* **Execution Architecture:** Implemented in `backend/ingestion/firms_client.py` using `httpx`.
* **Timeout:** Explicit 15.0-second network timeout.
* **Bounded Retries:** Maximum 2 retries with exponential backoff (`0.5s`, `1.0s`) on transient network dropped connections or HTTP 5xx server errors.
* **Payload Safety:** Enforces a 10 MB maximum payload ceiling (`MAX_PAYLOAD_BYTES`) to protect against memory exhaustion.
* **No Daemon / No Streaming:** Bounded batch execution triggered on-demand or via scheduled sync.

---

## 5. Pilot Geography & Spatial Filtering

* **Regional Scope:** The raw upstream feed covers South Asia (India, Pakistan, Bangladesh, Nepal, Bhutan, Myanmar, Thailand).
* **Target Pilot Geography:** Delhi National Capital Region (NCR).
* **Delhi NCR Bounding Box:**
  * Latitude: `[28.0000, 29.5000]`
  * Longitude: `[76.5000, 78.0000]`
* **Broader North India Scope:** `[26.0, 32.0, 74.0, 80.0]` (covering Punjab and Haryana stubble agricultural corridors).
* **Filtering Policy:** The full stream is fetched once, raw data preserved, and spatial filtering applied deterministically during validation to isolate pilot-relevant anomalies without redundant queries.

---

## 6. Raw Data Storage & Preservation

Raw snapshots are preserved in:
`F:\CLEAN AIR & CLIMATE RESILIENCE\data\raw\`

* **Naming Convention:** `firms_delhi_sample_<timestamp>.csv`
* **Integrity:** Retains the exact verbatim CSV payload returned by NASA EOSDIS servers, including source headers and byte count.

---

## 7. Parsing & Column Mapping

Parsed using standard RFC 4180 CSV reader with whitespace stripping and BOM protection:

| CSV Header Field | Meaning | Type | Unit |
| :--- | :--- | :--- | :--- |
| `latitude` | Centroid latitude | Float | Decimal degrees WGS84 |
| `longitude` | Centroid longitude | Float | Decimal degrees WGS84 |
| `bright_ti4` | VIIRS I-4 channel brightness temperature | Float | Kelvin (K) |
| `scan` | Along-scan spatial footprint dimension | Float | Kilometers (km) |
| `track` | Along-track spatial footprint dimension | Float | Kilometers (km) |
| `acq_date` | Date of satellite overpass | String | `YYYY-MM-DD` |
| `acq_time` | Time of satellite overpass | String | `HHMM` (UTC) |
| `satellite` | Satellite platform identifier (`N` = Suomi-NPP, `1` = NOAA-20, `2` = NOAA-21) | String | Code |
| `confidence` | Detection confidence level | String / Float | `low`, `nominal`, `high` (or % for MODIS) |
| `version` | Processing algorithm version | String | e.g. `2.0NRT` |
| `bright_ti5` | VIIRS I-5 channel brightness temperature | Float | Kelvin (K) |
| `frp` | Fire Radiative Power | Float | Megawatts (MW) |
| `daynight` | Solar illumination flag | String | `D` (Day) or `N` (Night) |

---

## 8. Canonical Normalization & Schema Contract

Implemented in `backend/ingestion/firms_normalizer.py`. Converts raw CSV records into the canonical `FireSignal` model which specializes `SatelliteSignal` (`docs/DATA_ARCHITECTURE.md` Section 3.3).

### Canonical `FireSignal` Attributes
* `signal_id`: Deterministic identifier `firms:{satellite}:{lat:.5f}:{lon:.5f}:{date}:{time}`
* `acquisition_time`: Explicit timezone-aware UTC datetime (`datetime.timezone.utc`)
* `satellite`: Standardized name (`Suomi-NPP`, `NOAA-20`, `NOAA-21`)
* `instrument`: Sensor name (`VIIRS`)
* `signal_type`: `"THERMAL_FIRE_PIXEL"`
* `geometry`: GeoJSON Point `{"type": "Point", "coordinates": [lon, lat]}`
* `value`: FRP magnitude in MW (or 0.0)
* `unit`: `"MW"`
* `quality_indicator`: Standardized indicator (`"LOW"`, `"NOMINAL"`, `"HIGH"`)
* `confidence`: Standardized category string
* `raw_confidence`: Exact verbatim string from source
* `frp_mw`: Fire Radiative Power in MW
* `bright_ti4_k` / `bright_ti5_k`: Dual-band brightness in Kelvin
* `daynight`: `"D"` or `"N"`
* `source`: `"NASA_FIRMS"`
* `provenance`: Ingestion endpoint, retrieval timestamp, normalization version

---

## 9. Validation Rules

Implemented in `backend/ingestion/firms_validator.py`:

1. **Coordinate Boundaries:** Latitude $\in [-90.0, 90.0]$, Longitude $\in [-180.0, 180.0]$.
2. **Timestamp Validation:** Valid calendar dates, valid 24-hour time ($0 \le H \le 23$, $0 \le M \le 59$).
3. **Fire Radiative Power:** $	ext{FRP} \ge 0.0\,	ext{MW}$. Negative values rejected.
4. **Brightness Temperature Limits:**
   * $150.0\,	ext{K} \le 	ext{bright\_ti4} \le 600.0\,	ext{K}$
   * $150.0\,	ext{K} \le 	ext{bright\_ti5} \le 500.0\,	ext{K}$
5. **Spatial Bounding Box Filter:** Rejects records outside the active pilot bounding box while recording the rejection count in the quality report.

---

## 10. Deduplication Strategy

* **Identity Key:** `signal_id = f"firms:{sat_slug}:{lat:.5f}:{lon:.5f}:{acq_date}:{acq_time_padded}"`
* **Rule:** A set of visited `signal_id` keys is maintained per ingestion run. Duplicate occurrences are rejected and logged to `duplicate_count`.
* **Temporal Disambiguation:** Multiple detections at the same coordinate on different orbits or times generate distinct unique IDs.

---

## 11. Data Quality Reporting

Every execution produces dual quality reports stored in `data/processed/`:
* Machine-readable JSON: `firms_delhi_fire_report_<timestamp>.json`
* Human-readable Markdown: `firms_delhi_fire_report_<timestamp>.md`

Reports capture: total rows received, rows retained, syntax rejections, out-of-bbox counts, duplicates, geographic bounding extent, acquisition time range, satellite distribution, confidence distribution, day/night distribution, and FRP statistics.

---

## 12. Verification Breakdown: Live Verified vs. Unit Tested

| Dimension | Verification Mode | Evidence |
| :--- | :---: | :--- |
| **HTTP Connectivity & Status** | **LIVE VERIFIED** | HTTP 200 OK from `firms.modaps.eosdis.nasa.gov` in ~1.8s |
| **Payload Size & CSV Header** | **LIVE VERIFIED** | 77,260 bytes, 954 rows, 13 standard VIIRS C2 columns |
| **Delhi NCR Filtering** | **LIVE VERIFIED** | 3 active fire detections isolated in South NCR / Faridabad |
| **Artifact Persistence** | **LIVE VERIFIED** | Raw CSV, processed JSONL, JSON report, Markdown report created |
| **Boundary Rejections** | **UNIT TESTED** | Out-of-range coords, negative FRP, invalid times verified rejected |
| **Duplicate Elimination** | **UNIT TESTED** | Identical records filtered out and counted |
| **HTTP Error Handling** | **UNIT TESTED** | Mocked 429 rate limit, 401 auth error, 500 retry backoff pass |
| **Pipeline from Fixture** | **UNIT TESTED** | 11-row test fixture evaluated with 100% assertion pass |

---

## 13. Limitations & Constraints

1. **Diurnal Blind Spot:** VIIRS instruments observe any given geographic coordinate twice daily (~13:30 and ~01:30 local solar time). Rapid, short-lived daytime burning (e.g. morning trash fires) between satellite overpasses will not be detected by FIRMS.
2. **Cloud and Heavy Haze Obscuration:** Heavy cloud cover or extreme optical depth can attenuate thermal radiance, causing false negatives.
3. **Spatial Resolution Footprint:** While 375m VIIRS pixel resolution is superior to 1km MODIS, multiple small burning piles within one 375m cell are aggregated into a single detection centroid.

---

## 14. Scientific Integrity & Interpretation Boundaries

> **CRITICAL SCIENTIFIC DIRECTIVE:**  
> 1. **FIRMS detects thermal radiance / active fires.** It does **NOT** measure particulate matter ($PM_{2.5}$ or $PM_{10}$).  
> 2. **Fire Radiative Power (MW) is a measure of radiant heat release**, **NOT** an emission mass, exposure concentration, or pollution severity level.  
> 3. **Thermal anomaly $
eq$ verified pollution plume.** A high-temperature kiln or furnace may produce thermal radiance with minimal particulate emissions, whereas a smoldering low-temperature waste fire produces dense toxic smoke with low FRP.  
> 4. **No Direct Attribution:** Cross-correlation between thermal anomalies and CAAQMS air quality spikes belongs strictly to multi-source evidence fusion in Phase 2, requiring trajectory modeling and boundary layer height context.
