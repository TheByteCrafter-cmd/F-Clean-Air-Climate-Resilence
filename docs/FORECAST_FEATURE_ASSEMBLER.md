# VayuDrishti — Real-Time-Safe Forecast Feature Assembler Documentation

## Overview
The `ForecastFeatureAssembler` (`ml/src/forecasting/feature_assembler.py`) is a deterministic, leakage-safe feature assembly engine designed to convert historical local air quality and weather telemetry into the exact 27-feature input vector required by the `ForecastInferenceEngine` (Phase 1E-J2E.1).

It operates purely on local files (`data/processed/forecasting/`) or in-memory lists without making external network calls, interpolating synthetic data, or violating temporal causality.

---

## Key Design Principles & Corrections

### 1. Canonical Station Registry Integration
Coordinates are loaded dynamically from `DELHI_PILOT_STATIONS` in `ml/src/forecasting/historical_ingestion.py`.
- Station ID: `ANAND_VIHAR_8118` (Aliases: `8118`, `LOC_8118`, `LOCATION_8118`).
- Canonical Latitude: `28.6476`
- Canonical Longitude: `77.3158`
- External payloads cannot override canonical coordinates.

### 2. Weather Staleness Policy & Training/Inference Parity
- Default `max_weather_staleness_minutes`: **60.0 minutes** (`[t - 60 minutes, t]`), matching Phase 1E-J1 dataset builder and `ForecastingConfig.weather_tolerance_minutes`.
- If the nearest past weather observation $\le t$ is older than 60 minutes, assembly status evaluates to `WEATHER_STALE`.
- Configurable via constructor for future contract revisions.

### 3. Strict Temporal Leakage Protection
- All PM2.5 observations used for lags and rolling statistics must satisfy `timestamp <= t`.
- All weather observations used for meteorology alignment must satisfy `timestamp <= t`.
- Any observation $> t$ is strictly excluded before feature extraction.

### 4. Mathematical Feature Parity Guarantee
For any timestamp $t$ present in the training set `forecast_dataset.csv`, `ForecastFeatureAssembler.assemble_features(t)` reproduces the exact row features across all 27 columns (PM2.5 lags, rolling statistics, weather variables, wind components, cyclic time encodings, latitude, longitude) within floating-point tolerance ($10^{-4}$).

### 5. Failure Diagnostics & Status Mapping
When assembly fails to compute a complete feature vector, `assembly_status` reflects the primary root cause while `missing_feature_reasons` contains detailed diagnostic strings.

| Status | Description | Example `missing_feature_reasons` |
|---|---|---|
| `READY` | All 27 features assembled successfully. | `[]` |
| `MISSING_HISTORY` | Insufficient past PM2.5 observations to compute lags/rolling stats. | `"pm25_lag_24h unavailable"`, `"pm25_roll_median_24h insufficient valid observations"` |
| `WEATHER_STALE` | Past weather observation $> 60.0$ min old or missing. | `"weather observation age = 87.0 minutes > 60.0 minute threshold"` |
| `UNSUPPORTED_STATION` | Station ID is not recognized as Anand Vihar 8118. | `"Station '9999' is unsupported. Canonical station scope: ANAND_VIHAR_8118."` |
| `INVALID_INPUT` | Unparseable ISO timestamp or invalid parameters. | `"Invalid prediction_timestamp 'invalid-date'..."` |

---

## Python API Usage

```python
from ml.src.forecasting.feature_assembler import ForecastFeatureAssembler

# Initialize assembler (uses default data_dir="data/processed/forecasting", max_weather_staleness_minutes=60.0)
assembler = ForecastFeatureAssembler()

# Assemble feature vector for Anand Vihar at target timestamp
result = assembler.assemble_features(
    station_id="ANAND_VIHAR_8118",
    prediction_timestamp="2025-01-01T12:00:00Z"
)

if result.assembly_status == "READY":
    print("Features assembled successfully!")
    print(f"Feature count: {len(result.features)}")
    # Pass directly into ForecastInferenceEngine.predict(result.features)
else:
    print(f"Assembly failed: {result.assembly_status}")
    print(f"Reasons: {result.missing_feature_reasons}")
```

---

## Operational Scope & Limitations
- Current scope is strictly limited to the Anand Vihar `8118` pilot station.
- Requires at least 24 hours of continuous preceding PM2.5 data to compute all lags and rolling statistics.
- Performs zero imputation or synthetic data generation. Missing data results in explicit diagnostic failures.
