# VayuDrishti Forecasting Feature Dictionary
**Status:** PHASE 1E-J1 — FORECASTING DATASET & FEATURE ENGINEERING FOUNDATION  
**Target API Version:** v1  
**Project:** VayuDrishti — Clean Air & Climate Resilience  

---

## Feature Dictionary Table

| COLUMN | TYPE | UNIT | SOURCE | TEMPORAL RELATION | DESCRIPTION | ALLOWED MISSINGNESS | LEAKAGE RISK |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `station_id` | string | Identifier | OpenAQ Metadata | $t$ | Canonical station identifier | 0.0% | NONE |
| `prediction_timestamp` | string (ISO 8601 UTC) | Timestamp | Data Pipeline | $t$ | Prediction anchor timestamp $t$ | 0.0% | NONE |
| `latitude` | float | degrees N | OpenAQ Metadata | Static | Station WGS84 latitude coordinate | 0.0% | NONE |
| `longitude` | float | degrees E | OpenAQ Metadata | Static | Station WGS84 longitude coordinate | 0.0% | NONE |
| `station_name` | string | Text | OpenAQ Metadata | Static | Canonical station name or location label | 100.0% | NONE |
| `pm25_t0` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $t$ | Primary pollutant PM2.5 concentration at prediction time $t$ | 0.0% | NONE |
| `pm10_t0` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $t$ | Secondary pollutant PM10 concentration at prediction time $t$ | 100.0% | NONE |
| `pm25_lag_1h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $t - 1\text{h}$ | Historical PM2.5 observation 1 hour prior to $t$ | ALLOWED | NONE |
| `pm25_lag_3h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $t - 3\text{h}$ | Historical PM2.5 observation 3 hours prior to $t$ | ALLOWED | NONE |
| `pm25_lag_6h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $t - 6\text{h}$ | Historical PM2.5 observation 6 hours prior to $t$ | ALLOWED | NONE |
| `pm25_lag_12h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $t - 12\text{h}$ | Historical PM2.5 observation 12 hours prior to $t$ | ALLOWED | NONE |
| `pm25_lag_24h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $t - 24\text{h}$ | Historical PM2.5 observation 24 hours prior to $t$ | ALLOWED | NONE |
| `pm25_roll_mean_3h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $[t - 3\text{h}, t]$ | Backward rolling mean PM2.5 over 3-hour window | ALLOWED | NONE |
| `pm25_roll_mean_6h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $[t - 6\text{h}, t]$ | Backward rolling mean PM2.5 over 6-hour window | ALLOWED | NONE |
| `pm25_roll_mean_24h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $[t - 24\text{h}, t]$ | Backward rolling mean PM2.5 over 24-hour window | ALLOWED | NONE |
| `pm25_roll_median_3h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $[t - 3\text{h}, t]$ | Backward rolling median PM2.5 over 3-hour window | ALLOWED | NONE |
| `pm25_roll_median_6h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $[t - 6\text{h}, t]$ | Backward rolling median PM2.5 over 6-hour window | ALLOWED | NONE |
| `pm25_roll_median_24h` | float | $\mu\text{g/m}^3$ | OpenAQ Telemetry | $[t - 24\text{h}, t]$ | Backward rolling median PM2.5 over 24-hour window | ALLOWED | NONE |
| `temperature_2m` | float | $^\circ\text{C}$ | Open-Meteo | $\le t$ | Aligned 2-meter ambient temperature | ALLOWED | NONE |
| `relative_humidity_2m` | float | $\%$ | Open-Meteo | $\le t$ | Aligned 2-meter relative humidity | ALLOWED | NONE |
| `wind_speed_10m` | float | $\text{m/s}$ | Open-Meteo | $\le t$ | Aligned 10-meter wind speed | ALLOWED | NONE |
| `wind_direction_10m` | float | degrees | Open-Meteo | $\le t$ | Aligned 10-meter wind direction (0-360) | ALLOWED | NONE |
| `wind_u` | float | $\text{m/s}$ | Open-Meteo | $\le t$ | Aligned zonal wind component (west-to-east) | ALLOWED | NONE |
| `wind_v` | float | $\text{m/s}$ | Open-Meteo | $\le t$ | Aligned meridional wind component (south-to-north) | ALLOWED | NONE |
| `surface_pressure` | float | $\text{hPa}$ | Open-Meteo | $\le t$ | Aligned surface barometric pressure | ALLOWED | NONE |
| `boundary_layer_height` | float | $\text{m}$ | Open-Meteo | $\le t$ | Aligned planetary boundary layer height | ALLOWED | NONE |
| `hour_sin` | float | $[-1.0, 1.0]$ | Transformation | $t$ | Cyclic sine encoding of hour of day ($\sin(2\pi \cdot h / 24)$) | 0.0% | NONE |
| `hour_cos` | float | $[-1.0, 1.0]$ | Transformation | $t$ | Cyclic cosine encoding of hour of day ($\cos(2\pi \cdot h / 24)$) | 0.0% | NONE |
| `day_of_week_sin` | float | $[-1.0, 1.0]$ | Transformation | $t$ | Cyclic sine encoding of day of week ($\sin(2\pi \cdot dow / 7)$) | 0.0% | NONE |
| `day_of_week_cos` | float | $[-1.0, 1.0]$ | Transformation | $t$ | Cyclic cosine encoding of day of week ($\cos(2\pi \cdot dow / 7)$) | 0.0% | NONE |
| `month_sin` | float | $[-1.0, 1.0]$ | Transformation | $t$ | Cyclic sine encoding of month ($\sin(2\pi \cdot (m-1) / 12)$) | 0.0% | NONE |
| `month_cos` | float | $[-1.0, 1.0]$ | Transformation | $t$ | Cyclic cosine encoding of month ($\cos(2\pi \cdot (m-1) / 12)$) | 0.0% | NONE |
| `pm25_t_plus_1h` | float | $\mu\text{g/m}^3$ | Target Shifting | $t + 1\text{h}$ | **Primary Target:** PM2.5 concentration at $t + 1\text{h}$ | ALLOWED | TARGET ONLY |
| `pm25_t_plus_3h` | float | $\mu\text{g/m}^3$ | Target Shifting | $t + 3\text{h}$ | **Primary Target:** PM2.5 concentration at $t + 3\text{h}$ | ALLOWED | TARGET ONLY |
| `pm25_t_plus_6h` | float | $\mu\text{g/m}^3$ | Target Shifting | $t + 6\text{h}$ | **Primary Target:** PM2.5 concentration at $t + 6\text{h}$ | ALLOWED | TARGET ONLY |
| `pm10_t_plus_1h` | float | $\mu\text{g/m}^3$ | Target Shifting | $t + 1\text{h}$ | **Secondary Target:** PM10 concentration at $t + 1\text{h}$ | ALLOWED | TARGET ONLY |
| `pm10_t_plus_3h` | float | $\mu\text{g/m}^3$ | Target Shifting | $t + 3\text{h}$ | **Secondary Target:** PM10 concentration at $t + 3\text{h}$ | ALLOWED | TARGET ONLY |
| `pm10_t_plus_6h` | float | $\mu\text{g/m}^3$ | Target Shifting | $t + 6\text{h}$ | **Secondary Target:** PM10 concentration at $t + 6\text{h}$ | ALLOWED | TARGET ONLY |
