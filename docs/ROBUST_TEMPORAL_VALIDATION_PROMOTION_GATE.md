# VayuDrishti — Robust Temporal Validation & Model Promotion Gate Protocol

## Overview (Phase 1E-J2E.5.1)

Phase 1E-J2E.5.1 establishes a production-grade multi-window chronological validation engine and a deterministic **Model Promotion Gate** for VayuDrishti's PM2.5 forecasting system (+1h, +3h, +6h horizons).

The protocol rigorously tests forecasting model performance across multiple rolling/chronological evaluation windows, guaranteeing:
1. **Hard Model Freeze Protection**: Production pilot LightGBM models (`lightgbm_pm25_{1h,3h,6h}.txt`) remain 100% byte-identical (SHA256 verified).
2. **Isolation of Validation Artifacts**: Candidate and validation run boosters are stored strictly in `ml/models/forecasting/validation_runs/`.
3. **Multi-Window Rolling Evaluation**: Models are benchmarked across distinct chronological windows (e.g., Window 1, Window 2, Window 3) to test temporal stability and prevent over-fitting to specific weather regimes.
4. **Comprehensive Benchmarking**: Every evaluation window compares **Persistence Baseline**, **Frozen Production Model**, and **Validation Candidate Model** on identical chronological test slices.
5. **Multi-Dimensional Diagnostics**: Evaluates residual distributions, temporal drift, pollution-regime performance (Moderate vs Poor vs Severe), and conformal uncertainty coverage (80%, 90%, 95%).
6. **Deterministic Promotion Gate**: Resolves promotion readiness into strict status values while enforcing `production_validation_status = "NOT_PRODUCTION_VALIDATED"`.

---

## Architectural Workflow

```
Historical Dataset (forecast_dataset.csv)
                │
                ▼
  Chronological Multi-Window Splitter (Window 1, Window 2, Window 3)
                │
  ┌─────────────┼─────────────────────────────┐
  ▼             ▼                             ▼
Persistence   Frozen Production Model       Validation Run Candidate Model
 Baseline     (SHA256 Hash Guarded)         (Saved to validation_runs/)
  │             │                             │
  └─────────────┼─────────────────────────────┘
                ▼
  Comparative Multi-Horizon Evaluation (+1h, +3h, +6h)
                │
  ┌─────────────┼─────────────────────────────┬─────────────────────────────┐
  ▼             ▼                             ▼                             ▼
Residual    Temporal Drift              Pollution Regime           Conformal Uncertainty
Diagnostics  Span & Stability            Breakdown (Low/Poor/Severe) Coverage (80/90/95%)
  │             │                             │                             │
  └─────────────┴─────────────────────────────┴─────────────────────────────┘
                ▼
      Promotion Gate Evaluator
                │
                ▼
  data/processed/forecasting/
  ├── rolling_temporal_validation_report.json
  └── promotion_gate_report.json
```

---

## Promotion Gate Status Definitions

The Promotion Gate outputs one of four explicit status values:

| Status Code | Description & Trigger Conditions |
|---|---|
| `MORE_EVIDENCE_REQUIRED` | Insufficient data samples (<1000 rows), missing horizons, or insufficient temporal/spatial diversity. |
| `CANDIDATE_SUPPORTED_FOR_REVIEW` | Candidate model outperforms persistence baseline and frozen production model across all windows with low drift variance. |
| `PROMOTION_BLOCKED` | Hard safety block triggered (e.g. frozen model hash mismatch, feature parity failure, or severe performance degradation). |
| `PROMOTION_REVIEW_REQUIRED` | Default operational state for pilot deployments (e.g., Anand Vihar single-station dataset). Candidate is candidate-validated, but production promotion requires manual signoff. |

> [!IMPORTANT]
> Under all circumstances during pilot phases, `production_validation_status` is explicitly set to `"NOT_PRODUCTION_VALIDATED"`. No automated model promotion or file overwriting is permitted.

---

## Verification & Model Integrity

To verify model SHA256 hashes against frozen baselines:

```python
from ml.src.forecasting.robust_temporal_validation import RobustTemporalValidator

validator = RobustTemporalValidator()
hashes = validator.verify_frozen_model_hashes()
print(hashes)
```

Expected Frozen SHA256 Hashes:
- `+1h`: `4C1CF555281AF9ABEE7BDA145C543648CB51F6418C939EE2D1A1DA58CA03AD28`
- `+3h`: `224DD3C4B0A97CC03ABF621B6AA3070610B60F41DAA05D99D02F8D024571C950`
- `+6h`: `0DF954AFBB21F8732814C055EFD5AD380F50AFA4B893942534CE5AD48E8B679F`
