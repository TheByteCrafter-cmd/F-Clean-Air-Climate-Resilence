# VayuDrishti ? Sentinel-5P / Earth Engine Satellite Environmental Signal Specification
## Phase 1E-D Documentation: Catalog Contract, Access Strategy, Quality Filtering & Cached Provenance

**Status:** PHASE 1E-D ? SENTINEL-5P SIGNAL FOUNDATION ESTABLISHED  
**Project:** VayuDrishti ? Clean Air & Climate Resilience  
**Local Project Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  
**Authoritative Documents:** `docs/DATA_ARCHITECTURE.md`, `docs/DATA_SOURCE_VERIFICATION.md`  

---

## 1. Role of Sentinel-5P in VayuDrishti

The Sentinel-5 Precursor (Sentinel-5P) satellite, carrying the TROPOspheric Monitoring Instrument (TROPOMI), provides daily global coverage of atmospheric trace gases. Within the VayuDrishti platform architecture, Sentinel-5P provides a **macro-level satellite environmental signal representing total tropospheric nitrogen dioxide ($NO_2$) vertical column density**.

```
??????????????????????????????????     ?????????????????????????????????
?     Macro Satellite Signal     ?     ?    Continuous Micro Signal    ?
?  Sentinel-5P TROPOMI NO2 L3    ?     ?   CAAQMS Ground In-Situ PM    ?
? (tropospheric column in mol/m?)?     ?   (OpenAQ v3 stations, ?g/m?) ?
??????????????????????????????????     ?????????????????????????????????
                ?                                      ?
                ????????????????????????????????????????
                                   ?
              ????????????????????????????????????????????
              ?     Multi-Source Evidence Fusion         ?
              ?  (Phase 2 Spatial-Temporal Correlator)   ?
              ????????????????????????????????????????????
```

---

## 2. Earth Engine Dataset & Catalog Contract

* **Earth Engine Collection ID:** `COPERNICUS/S5P/NRTI/L3_NO2` (Near Real-Time Level 3 product)
* **Offline Equivalent Collection ID:** `COPERNICUS/S5P/OFFL/L3_NO2`
* **Data Provider:** European Union / European Space Agency (ESA) Copernicus Programme
* **Sensor / Instrument:** TROPOMI spectrometer
* **Spatial Resolution:** $1113.2\,	ext{m}$ gridded in Earth Engine ($3.5 	imes 5.5\,	ext{km}$ nadir footprint)
* **Temporal Resolution:** Daily overpass at approximately 13:30 local solar time (ascending orbital node)
* **Official Data Catalog Reference:**
  `https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S5P_NRTI_L3_NO2`

---

## 3. Band Selection

| Band Name | Description | Units | Role in MVP |
| :--- | :--- | :--- | :--- |
| `tropospheric_NO2_column_number_density` | Integrated vertical column density from ground to tropopause | $	ext{mol/m}^2$ | **PRIMARY SIGNAL** |
| `cloud_fraction` | Effective cloud cover fraction | Dimensionless ($0.0 - 1.0$) | **QA FILTERING** |
| `stratospheric_NO2_column_number_density` | Model-assimilated stratospheric background column | $	ext{mol/m}^2$ | Supporting Metadata |
| `NO2_column_number_density` | Total atmospheric vertical column | $	ext{mol/m}^2$ | Supporting Metadata |

---

## 4. Access & Authentication Strategy

* **Runtime Authentication Status:** **`GEE RUNTIME ACCESS NOT CONFIGURED`**
  * The local execution environment does not possess initialized Earth Engine user credentials (`~/.config/earthengine/credentials`) or Google Cloud service account keys (`GOOGLE_APPLICATION_CREDENTIALS`).
  * In strict compliance with hackathon guidelines, credentials are NOT fabricated, mock accounts are NOT auto-generated, and authentication failure is handled defensively.
* **Dual Operation Strategy:**
  1. **Live GEE Mode:** Supported via `scripts/ingest_sentinel5p.py --live` when the operator has executed `earthengine authenticate`.
  2. **Offline Cache Fallback Mode:** Provides deterministic, fully validated satellite signals stored in `data/processed/satellite/` for offline judging resilience.

---

## 5. Region of Interest (ROI) & Spatial Representation

* **Pilot Region of Interest (Delhi NCR):**
  * Latitude: `[28.4000, 28.8500]`
  * Longitude: `[76.9000, 77.3500]`
* **Spatial Representation Decision (Option A):**
  * **Option A Selected: Representative Centroid Point + Sampled Footprint Metadata.**
  * Rationale: Centroid coordinate points (`GeoJSON Point`) with preserved spatial resolution footprint metadata (`approx_resolution_km: 5.5`) enable rapid spatial distance querying, immediate vector map rendering, and minimal storage overhead compared to complex polygon grids.

---

## 6. Temporal Handling & Observation Cadence

* **Non-Continuous Observation:** Unlike continuous CAAQMS ground monitors (OpenAQ) and hourly weather models (Open-Meteo), Sentinel-5P provides **one daily observation** during early afternoon (~13:30 local time).
* **Observation Timestamps:** Retained strictly in UTC (`datetime.timezone.utc`).
* **Cross-Temporal Caveat:** Morning rush-hour traffic emissions and nighttime stagnation episodes are invisible to optical satellite instruments. Downstream correlation engines must account for this temporal separation.

---

## 7. Quality Screening & Cloud Filtering

Following ESA TROPOMI Product User Manual (PUM) guidance:
* **Cloud Radiance Fraction:** Cloud cover obscures ground emissions. Observations with `cloud_fraction > 0.50` are filtered out or flagged as low-quality.
* **Clear Sky Tier:** Observations with `cloud_fraction <= 0.30` and `qa_value >= 0.75` are classified as `HIGH` quality.
* **Nominal Tier:** Observations with `cloud_fraction <= 0.50` are classified as `NOMINAL` quality.

---

## 8. Scientifically Valid Negative Values

* **Physical Origin:** Sentinel-5P DOAS retrieval computes trace gas absorption against a reference solar spectrum and subtracts stratospheric background. Noise in low-concentration regions or over clean rural background can produce slightly negative vertical column densities (e.g., $-15\,\mu	ext{mol/m}^2$).
* **Official Directive:** **DO NOT ZERO-CLAMP.** Clamping negative values to $0.0\,	ext{mol/m}^2$ introduces systematic positive bias into regional spatial averages.
* **Outlier Boundary:** Values below $-0.0001\,	ext{mol/m}^2$ ($-100\,\mu	ext{mol/m}^2$) indicate severe retrieval failure and are rejected.

---

## 9. Canonical Normalization & Schema Contract

Implemented in `backend/ingestion/sentinel5p_normalizer.py`. Converts Earth Engine samples into `Sentinel5PNO2Signal` (specializing `SatelliteSignal`):
* `signal_id`: `s5p:no2:trop:{lat:.5f}:{lon:.5f}:{timestamp_utc}`
* `acquisition_time`: UTC datetime
* `satellite`: `"Sentinel-5P"`
* `instrument`: `"TROPOMI"`
* `signal_type`: `"SATELLITE_NO2_COLUMN"`
* `geometry`: `{"type": "Point", "coordinates": [lon, lat]}`
* `value`: Tropospheric NO2 column density in $	ext{mol/m}^2$
* `unit`: `"mol/m?"` (strictly preserved)
* `quality_indicator`: `"HIGH" | "NOMINAL" | "LOW"`
* `tropospheric_no2_mol_m2`: Raw numerical density
* `cloud_fraction`: Effective cloud fraction

---

## 10. Provenance & Auditability

Every record preserves full data lineage:
* Upstream dataset identifier (`COPERNICUS/S5P/NRTI/L3_NO2`)
* Primary band name (`tropospheric_NO2_column_number_density`)
* Retrieval mode (`CACHED_FALLBACK` vs `LIVE_GEE`)
* Negative value policy declaration
* Retrieval timestamp and processing version

---

## 11. Offline Cache & Storage Strategy

* **Storage Location:** `data/processed/satellite/`
* **Canonical JSONL Cache:** `sentinel5p_delhi_no2_20260913_183815.jsonl` (6 validated Delhi pilot corridor records)
* **Raw JSON Snapshot:** `data/raw/sentinel5p_delhi_no2_sample_20260913_183815.json`
* **Quality Reports:**
  * JSON: `data/processed/satellite/sentinel5p_delhi_no2_report_20260913_183815.json`
  * Markdown: `data/processed/satellite/sentinel5p_delhi_no2_report_20260913_183815.md`

---

## 12. Verification Breakdown: Live Status vs. Unit Tested

| Dimension | Mode | Evidence |
| :--- | :---: | :--- |
| **Catalog Contract** | **SPEC VERIFIED** | Verified against official GEE catalog for `COPERNICUS/S5P/NRTI/L3_NO2` |
| **GEE Runtime Auth** | **AUDITED LIVE** | Evaluated via `ee.Initialize()`; confirmed `GEE RUNTIME ACCESS NOT CONFIGURED` |
| **Graceful Handling** | **UNIT TESTED** | `GEEAuthenticationError` raised cleanly; no uncaught exceptions |
| **Band & Unit Mapping** | **UNIT TESTED** | Verified `mol/m?` preserved, zero PM2.5 or ?g/m? conversions |
| **Negative Preservation**| **UNIT TESTED** | $-15\,\mu	ext{mol/m}^2$ noise preserved without zero-clamping |
| **Cloud Screening** | **UNIT TESTED** | Observations with cloud fraction $> 0.50$ filtered |
| **Spatial ROI Filter** | **UNIT TESTED** | Delhi pilot ROI bounded; out-of-ROI Punjab records rejected |
| **Cached Ingestion** | **LIVE VERIFIED** | 6 Delhi pilot signals normalized, validated, and persisted |

---

## 13. Scientific Limitations & Boundaries

> **CRITICAL SCIENTIFIC DIRECTIVE:**  
> 1. **Column Density $
eq$ Surface Concentration:** Sentinel-5P measures the total moles of $NO_2$ in a vertical atmospheric column ($	ext{mol/m}^2$). It does NOT measure ground-level breathing zone concentrations ($\mu	ext{g/m}^3$).  
> 2. **No Particulate Proxy:** $NO_2$ column density is NOT a measure of $PM_{2.5}$ or $PM_{10}$. No conversion formula from satellite column density to particulate matter exists.  
> 3. **Meteorological Inversion Trap:** Surface temperature inversions can trap high concentrations of surface $NO_2$ in a shallow 100m layer without producing an abnormally large total vertical column anomaly. Conversely, an elevated transport plume in the free troposphere can produce high column density with zero surface impact.  
> 4. **No Single-Source Attribution:** Satellite $NO_2$ indicates regional tropospheric abundance; it cannot prove single-point emissions without wind-vector dispersion modeling and ground validation.
