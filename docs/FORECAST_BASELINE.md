# VayuDrishti — Persistence Forecasting Baseline Specification (Phase 1E-J2B)

## 1. Executive Summary & Rationale
Before introducing machine-learning forecasting models (such as LightGBM, XGBoost, or Neural Networks), a transparent, non-parametric **Persistence Baseline** is required. 

Air quality metrics ($PM_{2.5}$) exhibit strong autocorrelation. A naive model assuming that future air quality will match current air quality often sets a high performance bar. Any advanced ML model is only meaningful if it demonstrably outperforms this persistence baseline on a chronologically separated holdout dataset.

---

## 2. Mathematical Definition
For a prediction timestamp $t$ and target horizon $h \in \{+1\text{h}, +3\text{h}, +6\text{h}\}$, the persistence forecast $\hat{y}_{t+h}$ is defined as:

$$\hat{y}_{t+h} = y_{t_{anchor}}$$

where $t_{anchor}$ is the timestamp of the latest valid $PM_{2.5}$ observation available at or before $t$:

$$t_{anchor} = \max \{ t' \le t \mid y_{t'} \text{ is a valid non-negative } PM_{2.5} \text{ observation for the same station} \}$$

---

## 3. Forecast Horizons
The persistence baseline evaluates three operational target horizons:
* **$+1\text{h}$ Horizon:** Short-term persistence for immediate dispersion alerts.
* **$+3\text{h}$ Horizon:** Medium-term persistence for community exposure warnings.
* **$+6\text{h}$ Horizon:** Operational persistence for municipal mitigation planning.

---

## 4. Anchor Observation Rule
* The prediction at timestamp $t$ uses **only** telemetry recorded at or before $t$ ($t_{anchor} \le t$).
* **No Future Data:** Target observations at $t+1\text{h}, t+3\text{h}, t+6\text{h}$ are strictly excluded from prediction generation.
* **Station Isolation:** Observations from Station A can **never** serve as anchor predictions for Station B.

---

## 5. Maximum Anchor Age Policy
To prevent using stale observations during extended telemetry outages, a configurable **Maximum Anchor Age** threshold is enforced:
* **Default Threshold:** $\tau_{max} = 3.0 \text{ hours} \quad (180 \text{ minutes})$.
* **Rule:** If $(t - t_{anchor}) > \tau_{max}$, the persistence prediction $\hat{y}_{t+h}$ is marked **Unavailable (`None`)**.
* **Rationale:** Predictor confidence degrades significantly past 3 hours of telemetry silence; invalid predictions are not invented or forward-filled beyond this cutoff.

---

## 6. Missing-Data & Failure Behavior
* If telemetry is missing at time $t$, the forecaster searches backward up to $t - 3.0\text{h}$ for the latest valid reading.
* If no valid reading exists within 3 hours, $\hat{y}_{t+h}$ evaluates to `None`.
* Pairs where either prediction $\hat{y}_{t+h}$ or actual target $y_{t+h}$ is missing are excluded from error metric summations.

---

## 7. Chronological Partitioning
Random train/test splitting (k-fold cross-validation or random masking) causes catastrophic temporal data leakage in time-series benchmarks. Evaluation MUST follow strict chronological partitioning:
* **Development / Calibration Period (70%):** Earliest historical interval.
* **Validation Period (15%):** Middle historical interval.
* **Holdout Test Period (15%):** Latest historical interval.

All evaluations are evaluated in strictly forward chronological order.

---

## 8. Evaluation Metrics
The persistence forecaster is benchmarked using three standard statistical metrics:

1. **Mean Absolute Error (MAE):**
   $$\text{MAE} = \frac{1}{n} \sum_{i=1}^n |y_i - \hat{y}_i|$$

2. **Root Mean Squared Error (RMSE):**
   $$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^n (y_i - \hat{y}_i)^2}$$

3. **Symmetric Mean Absolute Percentage Error (sMAPE):**
   $$\text{sMAPE} = \frac{100\%}{n} \sum_{i=1}^n \frac{|y_i - \hat{y}_i|}{(|y_i| + |\hat{y}_i|) / 2}$$
   *(Handles values approaching zero without numerical instability).*

---

## 9. Limitations of Persistence Forecasting
* Cannot anticipate rapid meteorological shifts (e.g., sudden wind direction change clearing stubble burning smoke).
* Performance degrades as horizon $h$ increases ($+6\text{h}$ persistence is significantly weaker than $+1\text{h}$).
* Subject to step-lag errors during sharp pollution spikes.

---

## 10. Reproducibility Guarantee
The persistence forecaster is 100% deterministic and stateless. Given identical input CSV/JSON telemetry, re-running the benchmark produces bit-for-bit identical predictions and metrics.

---

## 11. ML Model Benchmark Comparison Gate
In Phase 1E-J2C, any candidate ML model (e.g., LightGBM) must demonstrate statistically significant reduction in MAE and RMSE relative to this persistence baseline on the unseen 15% holdout test set before being eligible for deployment.
