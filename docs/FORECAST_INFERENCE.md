# VayuDrishti — Forecasting Inference Core Specification

**Phase:** 1E-J2E.1 — Forecast Inference Core & Model Artifact Loader  
**Canonical Station Scope:** `ANAND_VIHAR_8118` (Supported Aliases: `ANAND_VIHAR_8118`, `8118`)  
**Scope Statement:** "Current inference scope is limited to the Anand Vihar 8118 station-level pilot model."  

---

## 1. Architecture Overview

The **Forecasting Inference Core** provides deterministic, leakage-safe single-row forecast inference for $PM_{2.5}$ air quality predictions over $+1\text{h}$, $+3\text{h}$, and $+6\text{h}$ target horizons. It integrates trained LightGBM regression boosters, validates metadata from `model_manifest.json`, enforces strict feature schema reordering, and attaches frozen Split Conformal prediction intervals (80% and 90% confidence) validated directly from `uncertainty_metrics.json`.

```
                  ┌───────────────────────────────┐
                  │    Inference Request Input    │
                  │ (station_id, timestamp, features)│
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │   Station & Timestamp Check   │
                  │ (ANAND_VIHAR_8118 / UTC ISO)  │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │ Manifest Feature Reordering   │
                  │ (Strict order from manifest)  │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │   LightGBM Booster Inference  │
                  │     (+1h, +3h, +6h Boosters)  │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │ Conformal Interval Attachment │
                  │  (Frozen q_80, q_90 Radii)    │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │   Structured Forecast Result  │
                  │   (Unclipped bounds, flags)   │
                  └───────────────────────────────┘
```

---

## 2. Model Artifacts & Manifest Validation

The inference core dynamically discovers, loads, and validates the following frozen artifacts:

| Artifact | File Path | Validation Rules |
| :--- | :--- | :--- |
| **Model Manifest** | `ml/models/forecasting/model_manifest.json` | Validates model family, `feature_list`, `feature_count`, station scope, and model entries. |
| **+1h Booster** | `ml/models/forecasting/lightgbm_pm25_1h.txt` | LightGBM booster text model for $+1\text{h}$ target horizon. |
| **+3h Booster** | `ml/models/forecasting/lightgbm_pm25_3h.txt` | LightGBM booster text model for $+3\text{h}$ target horizon. |
| **+6h Booster** | `ml/models/forecasting/lightgbm_pm25_6h.txt` | LightGBM booster text model for $+6\text{h}$ target horizon. |
| **Uncertainty Metrics** | `data/processed/forecasting/model_evaluation/residual_analysis/uncertainty_metrics.json` | Validates existence, finiteness, and non-negativity ($\ge 0$) of conformal radii ($q_{80}, q_{90}$). |

---

## 3. Dynamic Feature Schema Contract

The feature schema is **derived dynamically** from `model_manifest.json -> feature_list`. Inputs are reordered **exactly** to match the manifest order:

1. `latitude`
2. `longitude`
3. `pm25_lag_1h`
4. `pm25_lag_3h`
5. `pm25_lag_6h`
6. `pm25_lag_12h`
7. `pm25_lag_24h`
8. `pm25_roll_mean_3h`
9. `pm25_roll_median_3h`
10. `pm25_roll_mean_6h`
11. `pm25_roll_median_6h`
12. `pm25_roll_mean_24h`
13. `pm25_roll_median_24h`
14. `temperature_2m`
15. `relative_humidity_2m`
16. `wind_speed_10m`
17. `wind_direction_10m`
18. `wind_u`
19. `wind_v`
20. `surface_pressure`
21. `boundary_layer_height`
22. `hour_sin`
23. `hour_cos`
24. `day_of_week_sin`
25. `day_of_week_cos`
26. `month_sin`
27. `month_cos`

---

## 4. Input & Output Data Contracts

### Input Contract (`predict`)
- `station_id` (str): Must map to `ANAND_VIHAR_8118` or alias `"8118"`.
- `prediction_timestamp` (str): Valid ISO 8601 UTC timestamp (e.g. `2025-01-31T12:00:00Z`).
- `feature_row` (dict): Dictionary mapping feature names to numeric values.

### Output Contract
```json
{
  "status": "SUCCESS",
  "scope": "Anand Vihar 8118 Pilot Station Only",
  "canonical_station_id": "ANAND_VIHAR_8118",
  "requested_station_id": "8118",
  "prediction_timestamp": "2025-01-31T12:00:00Z",
  "feature_count": 27,
  "horizons": {
    "+1h": {
      "horizon": "+1h",
      "target_column": "pm25_t_plus_1h",
      "predicted_pm25": 142.5042,
      "prediction_negative": false,
      "prediction_intervals": {
        "80_pct": {
          "confidence_level": "80%",
          "conformal_radius": 42.4646,
          "lower_bound": 100.0396,
          "upper_bound": 184.9688,
          "interval_width": 84.9292
        },
        "90_pct": {
          "confidence_level": "90%",
          "conformal_radius": 47.0292,
          "lower_bound": 95.475,
          "upper_bound": 189.5334,
          "interval_width": 94.0584
        }
      }
    }
  }
}
```

---

## 5. Guardrails & Operational Limitations

1. **Station Scope Guardrail:** Requests for unapproved station IDs fail safely with structured error code `UNSUPPORTED_STATION_SCOPE`.
2. **Unclipped Endpoint Policy:** Interval bounds ($[\hat{y} - q, \hat{y} + q]$) and point forecasts are preserved unclipped to maintain mathematical calibration semantics.
3. **Negative Prediction Handling:** Negative point estimates (if generated by tree regression) are preserved with diagnostic flag `prediction_negative: true`.
4. **Frozen Conformal Radii:** Conformal radii are loaded statically from `uncertainty_metrics.json`. No online recalibration occurs during inference.
