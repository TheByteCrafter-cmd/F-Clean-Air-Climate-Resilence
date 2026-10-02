# HISTORICAL SOURCE EXPANSION & STATION COMPATIBILITY RECOVERY

**Project:** VayuDrishti — Clean Air & Climate Resilience  
**Phase:** Phase 1E-J2E.5.3 — Historical Source Expansion & Station Compatibility Recovery  
**Workspace:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  
**Git Remote:** `https://github.com/TheByteCrafter-cmd/F-Clean-Air-Climate-Resilence.git` (`main` branch)

---

## 1. Executive Summary & Objective

Phase 1E-J2E.5.3 conducted a systematic historical data source discovery and station compatibility investigation across all six representative Delhi pilot air quality monitoring stations:
1. `ANAND_VIHAR_8118` (Anand Vihar, Delhi - DPCC)
2. `PUNJABI_BAGH_8122` (Punjabi Bagh, Delhi - DPCC)
3. `MANDIR_MARG_8125` (Mandir Marg, Delhi - DPCC)
4. `RK_PURAM_8124` (RK Puram, Delhi - DPCC)
5. `ITO_8120` (ITO, Delhi - CPCB)
6. `DHIER_PUR_8119` (Dheerpur, Delhi - IITM)

The primary goal of this phase is to distinguish:
- **Genuinely unavailable PM2.5 history** from
- **PM2.5 history that exists but was missed** due to source partition, sensor ID, parameter naming, or REST API vs. S3 archive coverage differences.

---

## 2. Core Invariants & Data Integrity Principles

1. **Zero Synthetic PM2.5 Data Generation:** No PM2.5 observations are manufactured, interpolated across wide gaps, or synthetically imputed.
2. **Zero Parameter Cross-Inference:** PM2.5 is **never** inferred or converted from PM10, NO2, O3, SO2, CO, temperature, humidity, or AQI. Non-PM2.5 parameters are logged and classified as `UNSUPPORTED_PARAMETER`.
3. **Zero Unsafe Sensor Mixing:** Observations from different sensors or locations are strictly segregated and tagged with explicit sensor IDs and provenance metadata.
4. **Strict Model & Scope Freeze:**
   - **No model training**, retraining, or candidate model creation was executed.
   - **Frozen model SHA256 hashes** remain 100% byte-identical.
   - `ANAND_VIHAR_8118` remains the **sole primary pilot station** for live production inference; recovered stations are designated **validation-only**.
   - `production_validation_status` remains strictly `"NOT_PRODUCTION_VALIDATED"`.

---

## 3. Discovered Sensor & Parameter Mapping Summary

| Station ID | Location ID | Discovered Sensor IDs | Parameter(s) Found | Units | Source Partition | Recovery Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **ANAND_VIHAR_8118** | 8118 | `23534`, `24151`, `24152`, `24153` | `pm25` (PM2.5), `pm10`, `no2` | `µg/m³` | AWS S3 Archive + REST API | **RECOVERED** (Full Archive) |
| **PUNJABI_BAGH_8122** | 8122 | `5078389`, `24201`, `24202`, `24203`, `24204` | `o3`, `pm25` (PM2.5), `pm10`, `so2`, `co` | `µg/m³`, `ug/m3`, `mg/m³` | REST API Snapshot (O3 in S3 archive) | **RECOVERED_SNAPSHOT_ONLY** |
| **MANDIR_MARG_8125** | 8125 | `23591`, `24301`, `24302`, `24398`, `24399` | `o3`, `pm25` (PM2.5), `o3`, `wind_speed` | `µg/m³`, `m/s` | REST API Snapshot (O3 in S3 archive) | **RECOVERED_SNAPSHOT_ONLY** |
| **RK_PURAM_8124** | 8124 | `5078922`, `5079064`, `5078714` | `o3`, `no2`, `so2` | `µg/m³` | AWS S3 Archive | **VERIFIED_UNAVAILABLE** (No PM2.5) |
| **ITO_8120** | 8120 | `23572` | `o3` | `µg/m³` | AWS S3 Archive | **VERIFIED_UNAVAILABLE** (No PM2.5) |
| **DHIER_PUR_8119** | 8119 | `23541` | `no2` | `µg/m³` | AWS S3 Archive | **VERIFIED_UNAVAILABLE** (No PM2.5) |

---

## 4. Key Discovery Findings & Recovery Breakdown

### 4.1 Station Recovery Classifications
1. **ANAND_VIHAR_8118 (`RECOVERED`):**
   - **Archive Provenance:** 1,322 PM2.5 observations across 56 daily files in `data/raw/forecasting/openaq_aws/`.
   - **Sensors:** S3 Archive sensor `23534`, REST API sensor `24151`.
   - **Feature Contract:** Fully satisfies the 27-feature contract (`pm25_lag_*`, `pm25_roll_*`, weather, time harmonics).

2. **PUNJABI_BAGH_8122 (`RECOVERED_SNAPSHOT_ONLY`):**
   - **Finding:** OpenAQ REST API / snapshot fixture records sensor `24201` as an active PM2.5 sensor (118.0 µg/m³). However, S3 archive partition `location-8122-*.csv.gz` contained only O3 sensor `5078389`.
   - **Resolution:** Recovered as snapshot-compatible. Archive historical time series remains unavailable in S3 daily partition.

3. **MANDIR_MARG_8125 (`RECOVERED_SNAPSHOT_ONLY`):**
   - **Finding:** OpenAQ REST API / snapshot fixture records sensor `24301` as an active PM2.5 sensor (96.0 µg/m³). S3 archive partition contained only O3 sensor `23591`. Sensor `24398` reported invalid negative value (-8.5 µg/m³) and was rejected by physical boundaries validator.
   - **Resolution:** Recovered as snapshot-compatible. Archive historical time series remains unavailable in S3 daily partition.

4. **RK_PURAM_8124, ITO_8120, DHIER_PUR_8119 (`VERIFIED_UNAVAILABLE`):**
   - **Finding:** Verified that archive files and API metadata for these 3 stations contain non-PM2.5 parameters (O3, NO2, SO2). No PM2.5 sensor exists in the archived data partitions.
   - **Resolution:** Honestly classified as `VERIFIED_UNAVAILABLE` for PM2.5 forecasting without data fabrication.

---

## 5. Duplicate & Sensor Collision Resolution

When multiple sensors provide PM2.5 for the same location and UTC timestamp (e.g. S3 archive sensor `23534` vs. REST API sensor `24151` for Anand Vihar):
- Both sensor identities are preserved in provenance metadata.
- A **deterministic selection rule** is enforced: S3 Archive sensor series takes precedence for historical time-series alignment, while REST API snapshot sensor is used for real-time inference.
- Observations are **never averaged** across sensors to artificially pad dataset length.

---

## 6. Generated Processed Artifacts

The following machine-readable JSON artifacts were generated in `data/processed/forecasting/`:
1. `historical_source_compatibility_report.json`: Overall summary of source discovery, station recovery statuses, and data quality states.
2. `station_sensor_parameter_matrix.json`: Exhaustive matrix of all discovered sensors, location IDs, parameters, units, and source partitions.
3. `recovered_validation_coverage_matrix.json`: Detailed validation matrix covering hourly compatibility, 27-feature contract status, and multi-season coverage.

---

## 7. Verification & Audit Results

- **Focused Unit Test Suite:** `tests/test_historical_source_compatibility.py` (26 passed, 0 failed).
- **Full Pytest Suite:** 496 passed, 1 skipped, 0 failed.
- **Frontend Build:** `npm --prefix frontend run build` (Exit Code 0).
- **Frozen Model Hashes (Byte-Identical):**
  - `lightgbm_pm25_1h.txt`: `4C1CF555281AF9ABEE7BDA145C543648CB51F6418C939EE2D1A1DA58CA03AD28`
  - `lightgbm_pm25_3h.txt`: `224DD3C4B0A97CC03ABF621B6AA3070610B60F41DAA05D99D02F8D024571C950`
  - `lightgbm_pm25_6h.txt`: `0DF954AFBB21F8732814C055EFD5AD380F50AFA4B893942534CE5AD48E8B679F`
