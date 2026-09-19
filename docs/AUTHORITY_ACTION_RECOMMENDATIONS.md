# VayuDrishti — Authority Action Recommendation Engine Documentation

## System Purpose & Operational Scope
The `ActionRecommendationEngine` (`ml/src/actions/action_engine.py`) is a transparent, auditable environmental decision-support module that transforms a `RiskAssessmentResult` and spatial context/hotspot evidence into time-bounded, human-reviewable `ActionRecommendationResult` artifacts.

> [!IMPORTANT]
> **Decision Support & Human Review Mandatory:**
> VayuDrishti action recommendations are decision-support suggestions provided solely for human authority review. They do NOT execute automated legal or enforcement actions, send public broadcasts, or constitute legally binding orders. Every recommendation contains `requires_human_review = true`.

> [!NOTE]
> **Non-Medical Operational Scope:**
> Recommendations address operational environmental surveillance and pollution mitigation reviews. They do NOT constitute medical diagnosis, patient advice, or clinical care guidelines.

---

## Action Catalog & Priority Levels

### Action Catalog
1. `MONITOR_LOCAL_AIR_QUALITY`: Baseline or enhanced air monitoring in station vicinity.
2. `INCREASE_INSPECTION_PRIORITY`: Priority allocation of field inspection teams for corroborated risk zones.
3. `REVIEW_INDUSTRIAL_ACTIVITY`: Operational compliance review for industrial proximity zones.
4. `REVIEW_MAJOR_ROAD_TRAFFIC_CONDITIONS`: Traffic congestion and road dust suppression review along primary corridors.
5. `VERIFY_SENSITIVE_RECEPTOR_EXPOSURE_CONTEXT`: Protective measure verification for sensitive receptors (schools, healthcare facilities).
6. `ISSUE_PUBLIC_INFORMATION_ADVISORY`: Public awareness advisory recommendation for persistent high risk.
7. `EXPAND_LOCAL_MONITORING`: Sensor verification or mobile monitoring deployment for high prediction uncertainty.

### Deterministic Priority Levels
- `INFORMATIONAL`: Baseline awareness, low risk.
- `WATCH`: Moderate risk or heightened uncertainty.
- `PRIORITY`: High risk or corroborated environmental signals.
- `URGENT_REVIEW`: Operational attention level for severe persistent risk. *(Not an emergency declaration or legal order)*

---

## Trigger Matrix & Rule Precedence

When multiple rules trigger for the same `action_type`:
1. Deduplicate identical `action_type`.
2. Merge all valid `trigger_conditions` and `reason_codes`.
3. Select the highest priority (`URGENT_REVIEW` > `PRIORITY` > `WATCH` > `INFORMATIONAL`).
4. Preserve deterministic ordering matching the catalog list.

---

## Uncertainty, Hotspot, and Context Integration

- **Uncertainty Handling:** High prediction uncertainty (`FORECAST_UNCERTAINTY_HIGH`) triggers `EXPAND_LOCAL_MONITORING` with `WATCH` priority to resolve uncertainty rather than escalating to urgent enforcement.
- **Hotspot Corroboration:** Corroborated hotspots trigger `INCREASE_INSPECTION_PRIORITY`. Absence of hotspot corroboration preserves forecast recommendations with `hotspot_missing = true`.
- **Spatial Exposure Context:** Static proximity flags (`industrial_context`, `major_road_context`, `sensitive_receptor_context`) trigger targeted review categories without implying source causation.

---

## Non-Causal Language Rules

All action titles and descriptions strictly adhere to non-causal decision-support phrasing:
- **Forbidden:** *"Factory X caused the pollution spike."*
- **Required:** *"Industrial-context review recommended given elevated forecast risk and corroborating hotspot evidence."*

---

## Data Quality Gates & Expiry Policy

- **BLOCKED Gate:** If the input risk assessment is `BLOCKED`, the recommendation status is set to `BLOCKED`, returning an empty recommendation list with reason `RISK_ASSESSMENT_BLOCKED`.
- **Expiry Policy:** Recommendations are valid for a configurable window (`default_validity_minutes = 120.0`). Expired recommendations reflect status `EXPIRED`.
