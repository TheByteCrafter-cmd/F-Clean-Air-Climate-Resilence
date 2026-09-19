# VayuDrishti — Live Forecast Pipeline Documentation

## System Overview
The `ForecastPipelineService` (`ml/src/forecasting/pipeline.py`) connects controlled live air quality (OpenAQ v3 API) and meteorology (Open-Meteo API) retrieval directly into the deterministic `ForecastFeatureAssembler` and `ForecastInferenceEngine`.

It operates as an internal, additive service that orchestrates live data refresh, atomic local persistence caching (`data/processed/forecasting/live/`), source freshness auditing, feature assembly, READY-gate enforcement, and model inference execution.

---

## Architectural Data Flow

```
Live OpenAQ v3 API (/sensors/{id}/hours)
        +
Live Open-Meteo Hourly Weather
        │
        ▼
Live Air Quality Provider + Live Weather Provider
        │
        ▼
Atomic Local Cache (data/processed/forecasting/live/)
        │
        ▼
Source Freshness & Availability Audit
        │
        ▼
ForecastFeatureAssembler (27 Features)
        │
        ▼
READY Gate (assembly_status == "READY")
        │
        ▼
ForecastInferenceEngine (+1h, +3h, +6h)
        │
        ▼
LiveForecastResult (Point Forecasts + 80%/90% Conformal Intervals)
```

---

## Key Operational Rules & Policies

### 1. OpenAQ v3 Hourly Endpoint Preference
- Recent PM2.5 history is retrieved using `OpenAQClient.get_sensor_measurements(sensor_id, date_from, date_to)`, querying `GET /v3/sensors/{sensor_id}/hours`.
- Does NOT rely on the `latest` endpoint for constructing the 24h lag and rolling context.

### 2. Flexible Lookback Windowing
- 30-hour MINIMUM lookback window (configurable bounded window, e.g. 30–48 hours) to ensure sufficient context for all 5 PM2.5 lags ($1\text{h}, 3\text{h}, 6\text{h}, 12\text{h}, 24\text{h}$) and 3 rolling features ($3\text{h}, 6\text{h}, 24\text{h}$) even in the presence of minor hourly gaps.
- Missing telemetry is NEVER fabricated or interpolated.

### 3. Open-Meteo Meteorology & Wind Vector Derivation
- Fetches `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`, `surface_pressure`, `boundary_layer_height`.
- Derives $u, v$ wind vector components using meteorological convention:
  $$u = - \text{speed} \times \sin(\text{rad})$$
  $$v = - \text{speed} \times \cos(\text{rad})$$
- Default max weather age threshold is **60 minutes** (`[t - 60 min, t]`). Weather older than 60 minutes yields `WEATHER_STALE`.

### 4. Distinct Failure States
- `LIVE_AQ_STALE`: Latest trusted AQ observation is older than 120 minutes.
- `LIVE_AQ_UNAVAILABLE`: Credentials missing, sensor discovery failed, or HTTP query failed.
- `WEATHER_STALE`: Nearest past weather observation is older than 60 minutes or missing.
- `MISSING_HISTORY`: Telemetry exists but required lag or rolling features cannot be constructed.
- `UNSUPPORTED_STATION`: Requested station is not recognized as Anand Vihar 8118.
- `INVALID_INPUT`: Malformed timestamp or future prediction timestamp string.

### 5. Effective Prediction Timestamp Logic
- **Explicit Timestamp:** Normalized to UTC ISO string; rejected if in the future ($> \text{current UTC time}$); evaluates source observations $\le$ timestamp.
- **Omitted Timestamp:** Defaults to the latest trusted AQ timestamp $\le \text{current UTC time}$.

### 6. Atomic Persistence Caching
Saved under `data/processed/forecasting/live/`:
- `live_air_quality.json`: Operational PM2.5 history records.
- `live_weather.json`: Operational weather records.
- `live_refresh_manifest.json`: Refresh metadata (`retrieval_timestamp`, `sensor_id`, `record_count`, `source_age_minutes`, `aq_status`, `weather_status`).
- Uses temporary file creation and atomic rename (`os.replace`) to prevent corrupted cache reads. Preserves previous valid cache if a refresh attempt fails.

### 7. API Compatibility & Decoupling
- `POST /api/v1/forecast` remains a pure prepared-feature transport/validation route and does NOT trigger network calls or live cache refreshes.
- The live pipeline is encapsulated inside `ForecastPipelineService`.

---

## Python Usage Example

```python
from ml.src.forecasting.pipeline import ForecastPipelineService

# Initialize pipeline service in LIVE or OFFLINE_TEST mode
service = ForecastPipelineService(mode="LIVE")

# Execute end-to-end live refresh, assembly, READY gate, and inference
result = service.execute_live_pipeline(
    station_id="ANAND_VIHAR_8118",
    prediction_timestamp=None  # Defaults to latest trusted AQ observation
)

print(f"Pipeline Status: {result.status}")
if result.status == "READY":
    print(f"Prediction Timestamp: {result.prediction_timestamp}")
    print(f"AQ Source Age: {result.air_quality_age_minutes} min")
    print(f"Weather Source Age: {result.weather_age_minutes} min")
    print("Forecast Horizons:", result.forecast_results.keys())
else:
    print(f"Assembly Status: {result.assembly_status}")
    print(f"Diagnostic Reasons: {result.diagnostic_flags.get('missing_feature_reasons')}")
```

---

## Operational Scope & Temporal Limitations
- Scope is strictly limited to station `ANAND_VIHAR_8118`.
- Model was trained on January 2025 pilot history (`station_level_pilot`).
- Live operational inference across different seasons or years may experience temporal distribution shift. Live output diagnostic flags explicitly state:
  `model_scope = station_level_pilot`, `data_scope = live_operational_input`, `model_validation_scope = January 2025 Anand Vihar pilot`.
