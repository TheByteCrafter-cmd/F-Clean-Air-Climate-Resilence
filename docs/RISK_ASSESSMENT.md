# VayuDrishti — Risk Assessment Engine Documentation

## System Purpose & Non-Medical Scope
The `RiskAssessmentEngine` (`ml/src/risk/risk_engine.py`) is a transparent, auditable environmental decision-support module that converts short-term PM2.5 forecasts (+1h, +3h, +6h predictions and conformal intervals), prediction uncertainty, hotspot corroboration evidence, and spatial/exposure context into a bounded numerical risk score (0–100) and qualitative risk level (`LOW`, `MODERATE`, `HIGH`, `VERY_HIGH`).

> [!IMPORTANT]
> **Non-Medical Operational Disclaimer:**
> VayuDrishti risk scores represent operational environmental risk levels for community and municipal decision support. They do NOT constitute medical diagnosis, patient-specific advice, or disease probabilities.

---

## Architectural Input & Output Contracts

### Input Contract (`RiskAssessmentInput`)
- `station_id`: `ANAND_VIHAR_8118` (or recognized aliases `8118`, `LOC_8118`, `LOCATION_8118`)
- `assessment_timestamp`: ISO 8601 UTC timestamp string
- `forecast_generated_timestamp`: ISO 8601 UTC timestamp string when the input forecast was generated
- `predicted_pm25_1h`, `predicted_pm25_3h`, `predicted_pm25_6h`: Predicted PM2.5 concentrations in $\mu\text{g/m}^3$
- `pm25_1h_lower_90`, `pm25_1h_upper_90` (and corresponding +3h, +6h bounds): 90% Split Conformal prediction intervals
- `hotspot_detected`, `hotspot_id`, `hotspot_support_score`, `hotspot_spatial_extent`, `hotspot_source_families`: Optional hotspot corroboration evidence
- `industrial_context`, `major_road_context`, `sensitive_receptor_context`: Optional spatial exposure modifiers
- `forecast_result_id`, `fusion_id`, `context_artifact_id`: Optional evidence reference IDs

---

## Bounded 0–100 Score Components

The total risk score is the sum of 5 deterministic, transparent components (Maximum score = 100.0):

$$\text{Risk Score} = \min\left(100.0, \text{Severity} + \text{Persistence} + \text{Uncertainty} + \text{Hotspot} + \text{Context}\right)$$

### 1. Forecast Severity Component (0–40 pts / 40% Weight)
Combines peak and mean predicted PM2.5 concentrations across +1h, +3h, +6h:
$$p_{\text{peak}} = \max(p_{+1h}, p_{+3h}, p_{+6h})$$
$$p_{\text{mean}} = \frac{p_{+1h} + p_{+3h} + p_{+6h}}{3.0}$$
$$p_{\text{eff}} = 0.6 \times p_{\text{peak}} + 0.4 \times p_{\text{mean}}$$

Applies the exact piecewise linear severity formula:
- $p_{\text{eff}} < 30.0 \mu\text{g/m}^3$: $\text{score} = 10.0 \times \frac{p_{\text{eff}}}{30.0}$
- $30.0 \le p_{\text{eff}} < 60.0 \mu\text{g/m}^3$: $\text{score} = 10.0 + 10.0 \times \frac{p_{\text{eff}} - 30.0}{30.0}$
- $60.0 \le p_{\text{eff}} < 120.0 \mu\text{g/m}^3$: $\text{score} = 20.0 + 10.0 \times \frac{p_{\text{eff}} - 60.0}{60.0}$
- $p_{\text{eff}} \ge 120.0 \mu\text{g/m}^3$: $\text{score} = 40.0$

### 2. Forecast Persistence Component (0–20 pts / 20% Weight)
Evaluates whether elevated forecast conditions ($\ge 60.0 \mu\text{g/m}^3$) persist across +1h, +3h, +6h:
- 0 or 1 horizon elevated: `0.0 pts` (`FORECAST_SHORT_LIVED`)
- 2 horizons elevated: `10.0 pts` (`FORECAST_MODERATELY_PERSISTENT`)
- 3 horizons elevated: `20.0 pts` (`FORECAST_PERSISTENT`)

### 3. Uncertainty Component (0–15 pts / 15% Weight) & Level Capping Rule
Evaluates relative prediction interval width:
$$w_{\text{rel}} = \frac{\text{upper}_{90} - \text{lower}_{90}}{\max(10.0, |\text{prediction}|)}$$
$$\text{Uncertainty Score} = \min\left(15.0, \text{round}(\bar{w}_{\text{rel}} \times 15.0, 2)\right)$$

> [!NOTE]
> **Uncertainty Capping Rule:**
> Uncertainty is an independent modifier. If the forecast severity score is $< 15.0$ (Low Severity), the maximum qualitative risk level is capped at `MODERATE` regardless of the uncertainty score. High uncertainty alone cannot elevate a low-severity forecast into `HIGH` or `VERY_HIGH` risk.

### 4. Hotspot Corroboration Component (0–15 pts / 15% Weight)
Incorporates audited hotspot support score ($0 - 100$) directly:
$$\text{Hotspot Score} = \min\left(15.0, 15.0 \times \frac{\text{support\_score}}{100.0}\right)$$
Treated strictly as corroboration strength without re-scoring or double-counting underlying evidence.

### 5. Spatial / Exposure Context Component (0–10 pts / 10% Weight)
Evaluates static spatial exposure modifiers:
- `industrial_context`: `+3.5 pts` (`INDUSTRIAL_CONTEXT_PRESENT`)
- `major_road_context`: `+3.0 pts` (`MAJOR_ROAD_CONTEXT_PRESENT`)
- `sensitive_receptor_context`: `+3.5 pts` (`SENSITIVE_RECEPTOR_CONTEXT_PRESENT`)

---

## Qualitative Risk Levels

| Score Range | Risk Level | Description |
|---|---|---|
| `0.0 – 24.99` | `LOW` | Minor environmental operational risk. Baseline conditions. |
| `25.0 – 49.99` | `MODERATE` | Moderate environmental operational risk. Heightened surveillance. |
| `50.0 – 74.99` | `HIGH` | High environmental operational risk. Community advisory level. |
| `75.0 – 100.0` | `VERY_HIGH` | Severe environmental operational risk. Urgent mitigation level. |

---

## Data Quality States & Freshness Policy

- `BLOCKED`: Forecast telemetry is missing, invalid, unsupported station, or forecast age $(\text{assessment\_ts} - \text{forecast\_gen\_ts}) > 120.0\text{ min}$ (`STALE_FORECAST`).
- `READY`: Forecast valid AND optional hotspot + spatial context present.
- `PARTIAL`: Forecast valid, but optional hotspot or spatial context missing (`hotspot_missing: true` / `context_missing: true`). A forecast-only assessment yields a valid deterministic risk score.

---

## Operational Scope Limitations
- Station scope is strictly limited to `ANAND_VIHAR_8118` pilot station.
- Engine performs zero ML inference, zero random sampling, and zero external API calls.
