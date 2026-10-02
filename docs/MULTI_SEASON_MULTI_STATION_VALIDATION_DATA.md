# VayuDrishti — Multi-Season & Multi-Station Validation Data Expansion

## Overview (Phase 1E-J2E.5.2)

Phase 1E-J2E.5.2 expands the historical validation evidence base for VayuDrishti's PM2.5 forecasting engine (+1h, +3h, +6h horizons) across multiple monitoring stations and historical time periods.

The primary objective of this phase is to establish whether forecasting model behavior is robust across different geographic locations and historical seasons, adhering strictly to the **Primary Principle of Evidence Integrity**:
- **Zero Evidence Fabrication**: No synthetic observations, artificial data generation, or silent imputation of target values.
- **Zero Sensor/Station Mixing**: Each station's telemetry is evaluated independently against the 27-feature canonical contract.
- **Honest Limitation Reporting**: Stations lacking required PM2.5 telemetry or historical date ranges are explicitly recorded as `INCOMPATIBLE` or `UNAVAILABLE`.

---

## Station Discovery & Eligibility Breakdown

All six representative Delhi pilot stations were evaluated against the 27-feature PM2.5 forecasting contract:

| Station ID | Location ID | Latitude | Longitude | Archive Files | Total Obs | PM2.5 Obs | PM2.5 Available | Eligibility Status | Incompatibility Rationale |
|---|---|---|---|---|---|---|---|---|---|
| **ANAND_VIHAR_8118** | 8118 | 28.6476 | 77.3158 | 32 | 768 | 768 | **YES** | **ELIGIBLE & SUFFICIENT** | Fully compatible with 27-feature contract |
| **PUNJABI_BAGH_8122** | 8122 | 28.6740 | 77.1310 | 25 | 92 | 0 | **NO** | **INCOMPATIBLE** | Missing PM2.5 telemetry (reports O3 only) |
| **MANDIR_MARG_8125** | 8125 | 28.6364 | 77.2011 | 25 | 93 | 0 | **NO** | **INCOMPATIBLE** | Missing PM2.5 telemetry (reports O3 only) |
| **RK_PURAM_8124** | 8124 | 28.5632 | 77.1869 | 25 | 279 | 0 | **NO** | **INCOMPATIBLE** | Missing PM2.5 telemetry (reports O3/NO2/SO2 only) |
| **ITO_8120** | 8120 | 28.6286 | 77.2410 | 20 | 59 | 0 | **NO** | **INCOMPATIBLE** | Missing PM2.5 telemetry (reports O3 only) |
| **DHIER_PUR_8119** | 8119 | 28.7041 | 77.1925 | 24 | 98 | 0 | **NO** | **INCOMPATIBLE** | Missing PM2.5 telemetry (reports NO2 only) |

---

## Historical Period / Seasonal Coverage

Historical period boundaries were audited across available OpenAQ S3 Archive telemetry:

| Period ID | Period Name | Start UTC | End UTC | Status | Matching Stations |
|---|---|---|---|---|---|
| `WINTER_2024_2025` | Winter 2024-2025 Baseline | 2024-12-31T00:00:00Z | 2025-01-31T23:59:59Z | **AVAILABLE** | `ANAND_VIHAR_8118` |
| `PRE_MONSOON_2025` | Pre-Monsoon 2025 | 2025-03-01T00:00:00Z | 2025-05-31T23:59:59Z | **UNAVAILABLE** | None (Archive coverage absent) |
| `MONSOON_2025` | Monsoon 2025 | 2025-06-01T00:00:00Z | 2025-09-30T23:59:59Z | **UNAVAILABLE** | None (Archive coverage absent) |
| `POST_MONSOON_2025` | Post-Monsoon 2025 | 2025-10-01T00:00:00Z | 2025-12-30T23:59:59Z | **UNAVAILABLE** | None (Archive coverage absent) |

---

## Model Performance Benchmarking (Anand Vihar Baseline)

Evaluated on the exact same 648 chronological test rows across horizons (+1h, +3h, +6h):

```
========================================================================================
Horizon | Persistence MAE | Frozen Model MAE | Candidate MAE | Conformal Coverage (80%)
========================================================================================
 +1h    |    24.51 µg/m³   |    18.12 µg/m³    |   16.84 µg/m³  |      81.4 %
 +3h    |    42.18 µg/m³   |    31.05 µg/m³    |   29.41 µg/m³  |      80.8 %
 +6h    |    65.40 µg/m³   |    48.20 µg/m³    |   45.10 µg/m³  |      82.1 %
========================================================================================
```

---

## Hard Invariants & Frozen Model SHA256 Verification

| Model Target | Expected SHA256 Checksum | Actual Verified Checksum | Status |
|---|---|---|---|
| `lightgbm_pm25_1h.txt` | `4C1CF555281AF9ABEE7BDA145C543648CB51F6418C939EE2D1A1DA58CA03AD28` | `4C1CF555281AF9ABEE7BDA145C543648CB51F6418C939EE2D1A1DA58CA03AD28` | **MATCH** |
| `lightgbm_pm25_3h.txt` | `224DD3C4B0A97CC03ABF621B6AA3070610B60F41DAA05D99D02F8D024571C950` | `224DD3C4B0A97CC03ABF621B6AA3070610B60F41DAA05D99D02F8D024571C950` | **MATCH** |
| `lightgbm_pm25_6h.txt` | `0DF954AFBB21F8732814C055EFD5AD380F50AFA4B893942534CE5AD48E8B679F` | `0DF954AFBB21F8732814C055EFD5AD380F50AFA4B893942534CE5AD48E8B679F` | **MATCH** |

- **Evidence Status**: `LIMITED_COVERAGE`
- **Production Validation Status**: `NOT_PRODUCTION_VALIDATED` *(Hard-locked invariant)*

---

## Artifacts Persisted

1. `data/processed/forecasting/multi_period_station_readiness_report.json`
2. `data/processed/forecasting/multi_station_validation_dataset_report.json`
3. `data/processed/forecasting/validation_coverage_matrix.json`
