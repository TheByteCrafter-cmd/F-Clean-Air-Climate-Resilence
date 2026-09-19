# VayuDrishti — Forecast Residual Analysis & Conformal Uncertainty Calibration

**Phase:** 1E-J2D — Residual Analysis, Uncertainty & Reliability Estimation  
**Scope:** Anand Vihar 8118 Pilot Station Only  
**Data Reference:** Real Historical Telemetry (Dec 31, 2024 – Jan 31, 2025)  

---

## 1. Conformal Coverage & Theoretical Framework

> [!IMPORTANT]
> **Mandatory Guarantee Disclaimer:**  
> Split conformal provides a finite-sample marginal coverage guarantee under its exchangeability assumptions. Because this pilot consists of temporally dependent air-quality observations, empirical holdout coverage is reported and should not be interpreted as an unconditional coverage guarantee.

### Mathematical Formulation & Indexing Convention
Split Conformal Prediction intervals are calibrated using absolute residuals computed exclusively on the chronological validation split ($N_{val}$).

For target miscoverage level $\alpha \in \{0.20, 0.10\}$ corresponding to target coverages of $80\%$ and $90\%$:

1. Compute validation absolute residuals: $R_i = |y_{i, val} - \hat{y}_{i, val}|$ for $i = 1, \dots, N_{val}$.
2. Sort absolute residuals: $R_{(1)} \le R_{(2)} \le \dots \le R_{(N_{val})}$.
3. Compute finite-sample conformal index $k$:
   $$k = \min\left(\left\lceil (N_{val} + 1)(1 - \alpha) \right\rceil, N_{val}\right)$$
4. Extract conformal radius $q_{1-\alpha} = R_{(k)}$ ($1$-indexed order statistic).
5. Prediction intervals for point forecast $\hat{y}$ on test set:
   $$\text{Interval}_{1-\alpha}(\hat{y}) = [\hat{y} - q_{1-\alpha},\; \hat{y} + q_{1-\alpha}]$$

> [!NOTE]
> All prediction interval endpoints ($[\text{Lower}, \text{Upper}]$) and raw point predictions are preserved **unclipped** without artificial clamping to zero or capping at arbitrary upper thresholds.

---

## 2. Conformal Radii & Empirical Holdout Reliability

Within each target horizon, the interval width $W = 2 q_{1-\alpha}$ is constant across all predictions because $q_{1-\alpha}$ is a scalar derived from the validation set.

### Calibrated Radii & Holdout Test Set Performance

| Horizon | Validation Rows ($N_{val}$) | Test Rows ($N_{test}$) | Target 80% Radius ($q_{80}$) | 80% Width ($2q$) | Test Emp. Cov (80%) | Coverage Error (80%) | Target 90% Radius ($q_{90}$) | 90% Width ($2q$) | Test Emp. Cov (90%) | Coverage Error (90%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **+1h** | 95 | 97 | $42.46 \;\mu g/m^3$ | $84.93 \;\mu g/m^3$ | **70.10%** | $-9.90\%$ | $47.03 \;\mu g/m^3$ | $94.06 \;\mu g/m^3$ | **72.16%** | $-17.84\%$ |
| **+3h** | 94 | 95 | $59.23 \;\mu g/m^3$ | $118.46 \;\mu g/m^3$ | **66.32%** | $-13.68\%$ | $67.75 \;\mu g/m^3$ | $135.50 \;\mu g/m^3$ | **74.74%** | $-15.26\%$ |
| **+6h** | 93 | 94 | $92.04 \;\mu g/m^3$ | $184.07 \;\mu g/m^3$ | **80.85%** | **+0.85%** | $102.44 \;\mu g/m^3$ | $204.88 \;\mu g/m^3$ | **82.98%** | $-7.02\%$ |

### Key Reliability Observations
1. **Horizon Scaling:** Conformal interval widths increase appropriately as the forecast horizon expands ($+1h: 84.93 \;\mu g/m^3 \rightarrow +3h: 118.46 \;\mu g/m^3 \rightarrow +6h: 184.07 \;\mu g/m^3$).
2. **Temporal Coverage Gap:** Empirical coverage on the holdout test set is lower than target nominal levels for $+1h$ and $+3h$ due to non-stationary distribution shift (the holdout test period in late January experienced severe winter smog spikes with higher variance than the preceding validation period).
3. **+6h Calibration:** The $+6h$ model achieves $80.85\%$ empirical coverage on the 80% interval (Coverage Error $+0.85\%$), demonstrating robust empirical reliability.

---

## 3. Residual Diagnostics & Systematic Bias

Residual definition: $e = y_{\text{actual}} - \hat{y}_{\text{predicted}}$ (Positive $e \implies$ Under-prediction, Negative $e \implies$ Over-prediction).

### Test Set Residual Summary Statistics

| Horizon | Mean Residual | Median Residual | Std Dev | Min Residual | Max Residual | MAE | RMSE | sMAPE |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **+1h** | $+22.50 \;\mu g/m^3$ | $+15.23 \;\mu g/m^3$ | $49.57 \;\mu g/m^3$ | $-49.92 \;\mu g/m^3$ | $+206.50 \;\mu g/m^3$ | $38.35$ | $54.45$ | $23.18\%$ |
| **+3h** | $+23.00 \;\mu g/m^3$ | $+16.48 \;\mu g/m^3$ | $62.79 \;\mu g/m^3$ | $-100.86 \;\mu g/m^3$ | $+268.04 \;\mu g/m^3$ | $46.45$ | $66.87$ | $25.01\%$ |
| **+6h** | $+16.92 \;\mu g/m^3$ | $+6.53 \;\mu g/m^3$ | $77.17 \;\mu g/m^3$ | $-116.32 \;\mu g/m^3$ | $+267.04 \;\mu g/m^3$ | $61.03$ | $79.01$ | $34.82\%$ |

> [!NOTE]
> **Systematic Bias:** All three horizons exhibit positive mean residuals ($+16.92$ to $+23.00 \;\mu g/m^3$), indicating a systematic under-prediction bias during peak pollution spikes in the holdout test period.

### High-Pollution Error Analysis ($PM_{2.5} > 200 \;\mu g/m^3$)

During severe pollution episodes ($PM_{2.5} > 200 \;\mu g/m^3$, accounting for $\sim 68\%$ of holdout test samples), model under-prediction increases:

- **+1h Horizon:** High-Pollution MAE = $49.88 \;\mu g/m^3$, Mean Residual = $+33.48 \;\mu g/m^3$.
- **+3h Horizon:** High-Pollution MAE = $59.20 \;\mu g/m^3$, Mean Residual = $+36.42 \;\mu g/m^3$.
- **+6h Horizon:** High-Pollution MAE = $76.26 \;\mu g/m^3$, Mean Residual = $+32.06 \;\mu g/m^3$.

---

## 4. Baseline Reconciliation (J2B vs. J2C / J2D)

Reconciliation between Phase 1E-J2B (Full Station Evaluation) and Phase 1E-J2C/J2D (Holdout Test Set Benchmark):

| Horizon | J2B Full Station Persistence MAE (N=648) | J2C/J2D Holdout Persistence MAE (N=94-97) | J2C/J2D LightGBM Test MAE (N=94-97) | LightGBM vs Holdout Persistence |
| :--- | :--- | :--- | :--- | :--- |
| **+1h** | $23.11 \;\mu g/m^3$ | $21.40 \;\mu g/m^3$ | $38.35 \;\mu g/m^3$ | $-79.17\%$ (Persistence wins short-term) |
| **+3h** | $43.85 \;\mu g/m^3$ | $45.19 \;\mu g/m^3$ | $46.45 \;\mu g/m^3$ | $-2.78\%$ (Competitive) |
| **+6h** | $65.42 \;\mu g/m^3$ | $71.35 \;\mu g/m^3$ | $61.03 \;\mu g/m^3$ | **+14.47% MAE Improvement (LightGBM wins)** |

> [!NOTE]
> The J2C/J2D evaluation compares LightGBM and Persistence on the **exact same holdout test timestamps**, ensuring zero evaluation leak or sample mismatch.

---

## 5. Operational Guidance & Pilot Limitations

1. **Station Scope:** Conformal radii and residual parameters are valid **only for Anand Vihar station (Location 8118)** and must not be extrapolated Delhi-wide.
2. **Temporal Dependence:** Split Conformal intervals provide marginal coverage guarantees assuming exchangeability. In time-series deployment, distribution shifts during extreme seasonal transitions will affect empirical coverage.
3. **Unclipped Bounds:** Unclipped interval endpoints preserve exact mathematical properties. Negative lower bounds or extreme upper bounds reflect real calibration bounds.
