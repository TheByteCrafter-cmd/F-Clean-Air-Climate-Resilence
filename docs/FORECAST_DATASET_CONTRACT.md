# VayuDrishti Forecasting Dataset Contract & Specification
**Status:** PHASE 1E-J1 — FORECASTING DATASET & FEATURE ENGINEERING FOUNDATION  
**Target API Version:** v1  
**Project:** VayuDrishti — Clean Air & Climate Resilience  
**Local Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  

---

## 1. Executive Overview & Purpose

The VayuDrishti Air Quality Forecasting Pipeline uses a deterministic, leakage-safe supervised-learning dataset construction architecture. This contract governs the exact data grain, temporal boundaries, feature engineering rules, target horizon definitions, missing-data handling, weather alignment, quality validation, and readiness assessment for short-term ambient air quality prediction.

> [!IMPORTANT]
> **No Model Training Phase:** Phase 1E-J1 establishes the data preparation, feature engineering, and leakage validation foundation ONLY. No machine learning models (LightGBM/XGBoost) or inference endpoints are deployed in this phase.

---

## 2. Canonical Dataset Grain & Target Definitions

### 2.1 Forecasting Grain
The canonical dataset row grain is strictly defined as:
$$\text{ONE ROW} = \text{ONE STATION} + \text{ONE PREDICTION TIMESTAMP (t)}$$

- **Station Identity:** Expressed via canonical `station_id` (e.g., `ANAND_VIHAR_8118`). Station identity is explicitly preserved in every row to allow spatial grouping and station-aware model training.
- **Prediction Timestamp ($t$):** Standard ISO 8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`) representing the exact moment at which a forecast is generated using only past and present observations.

### 2.2 Primary & Secondary Target Variables
- **Primary Target Variable:** `PM2.5` concentration in $\mu\text{g/m}^3$.
- **Secondary Target Variable:** `PM10` concentration in $\mu\text{g/m}^3$ (included when available in source observations).

### 2.3 Forecast Horizons
For any row anchored at prediction timestamp $t$, the dataset constructs three strictly future-looking target horizons:
1. `pm25_t_plus_1h`: $\text{PM2.5}$ observation at $t + 1\text{ hour}$ ($+60\text{ mins}$)
2. `pm25_t_plus_3h`: $\text{PM2.5}$ observation at $t + 3\text{ hours}$ ($+180\text{ mins}$)
3. `pm25_t_plus_6h`: $\text{PM2.5}$ observation at $t + 6\text{ hours}$ ($+360\text{ mins}$)

If `PM10` observations are present, corresponding secondary targets are constructed: `pm10_t_plus_1h`, `pm10_t_plus_3h`, `pm10_t_plus_6h`.

> [!CAUTION]
> **Zero Temporal Leakage Boundary:** Information from $t + \Delta h$ ($\Delta h > 0$) MUST appear ONLY in target columns. Future pollution observations, future weather, or future event labels must NEVER be included in feature columns for timestamp $t$.

---

## 3. Feature Engineering Specifications

Features are grouped into 5 versioned categories:

### Group A: Historical PM2.5 Lags & Rolling Statistics
All historical features for a station row at timestamp $t$ are derived strictly from observations at or before $t$ ($\le t$).

1. **Lag Features:**
   - `pm25_lag_1h`: Observation at $t - 1\text{h}$
   - `pm25_lag_3h`: Observation at $t - 3\text{h}$
   - `pm25_lag_6h`: Observation at $t - 6\text{h}$
   - `pm25_lag_12h`: Observation at $t - 12\text{h}$
   - `pm25_lag_24h`: Observation at $t - 24\text{h}$

2. **Rolling Window Statistics:**
   - `pm25_roll_mean_3h`, `pm25_roll_median_3h`: Over window $[t - 3\text{h}, t]$
   - `pm25_roll_mean_6h`, `pm25_roll_median_6h`: Over window $[t - 6\text{h}, t]$
   - `pm25_roll_mean_24h`, `pm25_roll_median_24h`: Over window $[t - 24\text{h}, t]$

*Rolling Window Constraints:*
- Rolling windows must **never** be centered.
- Windows are backward-looking only ($[t - W, t]$).
- A minimum observation threshold ($\ge 2$ valid points) is required to compute rolling statistics; otherwise, the feature remains `NaN` / missing.

### Group B: Weather Features & Temporal Alignment
Weather parameters are integrated from normalized Open-Meteo representations.

- **Parameters:** `temperature_2m` ($^\circ\text{C}$), `relative_humidity_2m` ($\%$), `wind_speed_10m` ($\text{m/s}$), `wind_direction_10m` ($\text{deg}$), `wind_u` ($\text{m/s}$), `wind_v` ($\text{m/s}$), `surface_pressure` ($\text{hPa}$), `boundary_layer_height` ($\text{m}$).
- **Cartesian Wind Vectors:** $u = -v_{\text{wind}} \cdot \sin(\theta)$, $v = -v_{\text{wind}} \cdot \cos(\theta)$.
- **Alignment Policy:** Weather records are aligned to prediction timestamp $t$ using exact hourly match or nearest observation within tolerance window $[t - 60\text{ mins}, t]$. Weather observations from $t + \Delta$ ($> t$) are strictly prohibited.

### Group C: Cyclic Temporal Features
Deterministic calendar features use continuous sine/cosine transformations:
- `hour_sin` = $\sin\left(\frac{2\pi \cdot \text{hour}}{24}\right)$, `hour_cos` = $\cos\left(\frac{2\pi \cdot \text{hour}}{24}\right)$
- `day_of_week_sin` = $\sin\left(\frac{2\pi \cdot \text{dow}}{7}\right)$, `day_of_week_cos` = $\cos\left(\frac{2\pi \cdot \text{dow}}{7}\right)$
- `month_sin` = $\sin\left(\frac{2\pi \cdot (\text{month}-1)}{12}\right)$, `month_cos` = $\cos\left(\frac{2\pi \cdot (\text{month}-1)}{12}\right)$

### Group D: Station Metadata
- `station_id`, `latitude` (WGS84), `longitude` (WGS84), `station_name`.

### Group E: Static Geospatial Context (Optional)
- Distance to major road corridors or land use tags (if static and co-located). Dynamic hotspot outputs or future event labels are explicitly excluded.

---

## 4. Missing Data & Imputation Policy

1. **Target Columns:** Missing target values are **never** forward-filled or imputed. If target $t + h$ is missing, the row is flagged as unavailable for training horizon $+h$.
2. **Lag Features:** If historical observation at $t - k$ is unavailable due to missing sampling or data gaps, the lag feature remains `NaN` / missing.
3. **Rolling Features:** Requires $\ge 2$ valid observations within the window. Insufficient points result in `NaN`.
4. **Weather Features:** Missing weather fields remain distinguishable from valid zero values.

*Default Principle:* Prefer dropping or excluding an incomplete training pair over fabricating physical environmental telemetry.

---

## 5. Mandatory Leakage Protections & Automated Verification

The dataset builder includes 7 automated temporal leakage tests (`verify_zero_temporal_leakage`):
1. **Test 1:** Mutating $\text{PM2.5}$ at $t+1\text{h}$ does NOT alter any feature value at $t$.
2. **Test 2:** Mutating $\text{PM2.5}$ at $t+3\text{h}$ does NOT alter any feature value at $t$.
3. **Test 3:** Mutating $\text{PM2.5}$ at $t+6\text{h}$ does NOT alter any feature value at $t$.
4. **Test 4:** Mutating future weather observations ($> t$) does NOT alter feature values at $t$.
5. **Test 5:** Rolling window bounds strictly satisfy $\text{timestamp} \le t$.
6. **Test 6:** Rolling and lag features are strictly isolated per `station_id`.
7. **Test 7:** Target shifting is strictly forward ($t + 1\text{h}$, $t + 3\text{h}$, $t + 6\text{h}$) and never backward.

---

## 6. Dataset Readiness & Synthetic Fixture Policy

### 6.1 Readiness Evaluation
The dataset builder evaluates data readiness against formal criteria:
- Minimum stations: $\ge 3$
- Minimum historical time range: $\ge 48\text{ hours}$
- Minimum usable rows for $+1\text{h}$: $\ge 100\text{ rows}$

If real project data fails these criteria (e.g., single timestamp snapshot), the dataset manifest honestly records:
`"readiness_status": "NOT_READY"` with explicit non-readiness reasons. Fake training data is **never** fabricated for real execution.

### 6.2 Synthetic Test Fixture Policy
- Small synthetic test fixtures are created strictly under `tests/fixtures/forecasting/`.
- Synthetic records use fake station IDs (`syn_st_01`, `syn_st_02`) and are labeled **TEST ONLY**.
- Synthetic fixtures are used exclusively in unit/integration test suites and are **never** written to production dataset locations or used for real model training.

---

## 7. Artifact Persistence Layout

Forecasting artifacts are stored under `data/processed/forecasting/`:
- `forecast_dataset.csv`: Standard CSV dataset containing features and target columns.
- `forecast_dataset_manifest.json`: Machine-readable metadata (creation timestamp, input artifacts, row count, station count, time range, readiness status).
- `forecast_data_quality.json`: Detailed 14-point validation audit report.
- `forecast_data_readiness.json`: Deterministic dataset readiness assessment.
