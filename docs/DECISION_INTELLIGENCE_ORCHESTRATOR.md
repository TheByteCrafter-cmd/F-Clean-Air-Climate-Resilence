# VayuDrishti — End-to-End Decision Intelligence Orchestrator

**Phase**: 1E-J2E.4.4  
**Scope**: Anand Vihar 8118 (`ANAND_VIHAR_8118`) Station-Level Pilot  
**Status**: COMPLETE  

---

## 1. Overview & Architecture

The End-to-End Decision Intelligence Orchestrator (`ml/src/decision/`) composes the complete downstream decision-support pipeline into a single auditable output artifact (`DecisionIntelligenceResult`).

```
                              [ Input Telemetry & Context ]
                                            │
                                            ▼
                           ┌──────────────────────────────────┐
                           │   Forecast Inference Engine      │
                           │   (+1h, +3h, +6h Split Conformal)│
                           └──────────────────────────────────┘
                                            │
                                            ▼
                           ┌──────────────────────────────────┐
                           │     Risk Assessment Engine       │
                           │   (5 Auditable Components: 0-100)│
                           └──────────────────────────────────┘
                                            │
                                            ▼
                           ┌──────────────────────────────────┐
                           │ Authority Action Recommendation  │
                           │              Engine              │
                           └──────────────────────────────────┘
                                            │
                                            ▼
                           ┌──────────────────────────────────┐
                           │   Decision Intelligence Engine   │
                           │    (Composite Output Orchestrator)│
                           └──────────────────────────────────┘
                                            │
                                            ▼
                           [ DecisionIntelligenceResult JSON ]
```

---

## 2. Core Invariants & Governance Guarantees

1. **Mandatory Human Review (`requires_human_review = True`)**: Every output artifact explicitly enforces `requires_human_review = True`. Automated execution of government actions, notifications, or interventions is strictly prohibited.
2. **Station Scope Lock**: Execution is strictly bounded to the Anand Vihar 8118 pilot station (`ANAND_VIHAR_8118`). Attempts to supply unsupported station IDs return `BLOCKED` status with `UNSUPPORTED_STATION_SCOPE` reason code.
3. **Deterministic Status Precedence**: Data quality status is derived using the rule:
   $$\text{overall\_data\_quality\_status} = \text{BLOCKED} > \text{PARTIAL} > \text{READY}$$
4. **Earliest Expiry Timestamp Rule**: The overall artifact expiration timestamp is computed as:
   $$\text{expires\_timestamp} = \min(\text{risk\_expires\_timestamp}, \text{action\_expires\_timestamp})$$
5. **No Double-Counting**: Risk scoring (0-100) and action prioritization logic are completely decoupled. The orchestrator composes results without modifying component calculations or priorities.
6. **Disclaimers & Non-Causal Language**: Synthesized decision summaries use objective, non-medical, non-causal language and carry mandatory disclaimers.

---

## 3. Package Structure

- `ml/src/decision/__init__.py`: Package export interface.
- `ml/src/decision/decision_config.py`: Versioned configuration (`1.0`), validity parameters, status precedence rules.
- `ml/src/decision/decision_schemas.py`: Dataclass and Pydantic validation contracts (`DecisionIntelligenceInput`, `DecisionIntelligenceResult`).
- `ml/src/decision/decision_engine.py`: Core orchestrator engine (`DecisionIntelligenceEngine`).
- `data/processed/decision/decision_intelligence.json`: Sample validated production artifact.

---

## 4. Usage Example

```python
from ml.src.decision import DecisionIntelligenceEngine, DecisionIntelligenceInput

engine = DecisionIntelligenceEngine()

input_data = DecisionIntelligenceInput(
    station_id="ANAND_VIHAR_8118",
    prediction_timestamp="2026-03-30T12:00:00Z",
    predicted_pm25_1h=145.2,
    pm25_1h_lower_90=120.0,
    pm25_1h_upper_90=170.4,
    predicted_pm25_3h=158.0,
    pm25_3h_lower_90=130.0,
    pm25_3h_upper_90=186.0,
    predicted_pm25_6h=172.5,
    pm25_6h_lower_90=140.0,
    pm25_6h_upper_90=205.0,
    hotspot_detected=True,
    hotspot_id="hs_av_20260330_01",
    hotspot_support_score=85.0,
    industrial_context=True,
    major_road_context=True,
    sensitive_receptor_context=True,
)

result = engine.orchestrate(input_data)
print(f"Risk Score: {result.risk_score} ({result.risk_level})")
print(f"Recommendations: {result.recommendation_count}")
print(f"Requires Human Review: {result.requires_human_review}")
```
