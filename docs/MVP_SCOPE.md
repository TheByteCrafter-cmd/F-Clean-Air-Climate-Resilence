# MVP Scope & Implementation Freeze
## VayuDrishti: Hyper-Local Climate Intelligence & Action Platform
**Hackathon:** Build with AI — Code for Communities, Second Edition  
**Theme:** Clean Air & Climate Resilience  
**Status:** PHASE 0.5 — SCOPE FREEZE COMPLETED  
**Repository:** `https://github.com/TheByteCrafter-cmd/F-Clean-Air-Climate-Resilence`  
**Local Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  

---

## 1. Executive Summary & Freeze Objective

In Phase 0, `docs/PROJECT_BLUEPRINT.md` established the comprehensive architectural vision, operational theory, and public-sector integration strategy for VayuDrishti. 

The objective of **Phase 0.5** is to perform an aggressive, disciplined **MVP simplification**. Hackathons are won by software that executes flawlessly end-to-end, demonstrates undeniable technical credibility, and solves a real problem with rock-solid reliability—not by overengineered architectures with 20 half-implemented modules.

This document establishes the **immutable MVP implementation boundary**. Every theoretical algorithm and complex pipeline from Phase 0 is triaged into **MVP (Must Build)**, **OPTIONAL (Build Only If Time Permits)**, or **FUTURE (Post-Hackathon Research)**.

---

## 2. Core Product Spine (Permanent & Unchanged)

The heart of VayuDrishti remains completely intact through an unbroken operational chain:

```
[Citizen Evidence] (Photos + Voice + GPS)
        │
        ▼
[Gemini Multimodal Triage] (Visual plume check + Opacity + Audio transcript)
        │
        ▼
[Multi-Source Correlation] (Downwind sensors + Wind vector + Satellite thermal)
        │
        ▼
[Hidden Hotspot Detection] (Local anomaly escaping regional CAAQMS baseline)
        │
        ▼
[Short-Term Forecasting] (LightGBM 1h, 3h, 6h PM2.5 corridor projection)
        │
        ▼
[Risk & Decision Support] (Vulnerability context + Statutory GRAP field directives)
        │
        ▼
[Authority Action & Resolution] (Dispatched squad, anti-smog unit, closed loop)
```

---

## 3. Specific Complexity Review & Component Triage

We evaluate each advanced mathematical, geospatial, and machine learning technique proposed in Phase 0 against practical hackathon constraints:

| Component / Technique | Phase 0 Proposed Role | MVP Triage | Practical Engineering Rationale & Simplification |
| :--- | :--- | :---: | :--- |
| **Kriging (Geostatistical Interpolation)** | Regional continuous spatial interpolation of CAAQMS PM2.5. | **OPTIONAL** | *Simplification for MVP:* Replace heavy variogram modeling/Ordinary Kriging with **Inverse Distance Weighting (IDW)** or a **Hexagonal/Grid Voronoi Baseline**. IDW is deterministic, computes in milliseconds in Python/NumPy without convergence errors, and yields visually identical baseline fields for anomaly residuals. |
| **DBSCAN (Spatial Report Clustering)** | Clustering nearby citizen reports into single compound events. | **MVP** | *Retain for MVP:* DBSCAN is lightweight (runs via `scikit-learn` in $<10\text{ms}$ on dozens of coordinates), requires no pre-set cluster count $k$, and naturally isolates isolated noise/spam points. Essential for deduplicating crowd reports. |
| **Bayesian Confidence Formulation** | Dynamic probabilistic weighting of multi-modal evidence. | **MVP (Simplified)** | *Simplification for MVP:* Implement as a **Deterministic Weighted Multi-Source Score with Corroboration Multipliers** ($C = \min(100, \sum w_k S_k \cdot \gamma_k)$). Fully transparent, predictable for judge demonstrations, and eliminates fragile Bayesian prior-tuning. |
| **LightGBM Regressor** | Short-term (1h, 3h, 6h) PM2.5 tabular forecasting along corridors. | **MVP** | *Retain for MVP:* Trains on tabular historical meteorological and sensor lags in seconds; CPU inference in $<5\text{ms}$; natively handles missing telemetry; highly reliable inside lightweight Cloud Run containers. |
| **XGBoost Regressor** | Alternative tabular boosting model for forecasting. | **OPTIONAL** | *Deprecate to Optional:* Having two gradient-boosting libraries creates redundant code. Standardize strictly on **LightGBM** for speed and smaller container footprint. |
| **Quantile Forecasting (P10, P50, P90)** | Providing uncertainty prediction intervals. | **MVP (Simplified)** | *Simplification for MVP:* Train LightGBM with quantile loss ($\alpha=0.5$ for median forecast), or compute symmetric residual standard error bands ($\pm 1.28 \sigma$ for 80% interval). Provides visible credibility to judges without managing 3 separate model pipelines. |
| **Atmospheric Dispersion Physics** | Gaussian plume equations for downwind pollutant spread. | **MVP (Geometric Proxy)** | *Simplification for MVP:* Avoid complex fluid dynamic partial differential equations. Model downwind dispersion as an **Elliptical Angular Sector (Cone)** aligned with prevailing wind direction $\theta \pm 25^\circ$ expanding downwind up to 3 km. Mathematically sound, instantly computable via GeoJSON polygon. |
| **Sentinel-5P TROPOMI NO2** | Daily satellite raster verifying regional tropospheric NO2. | **MVP (Curated Layer)** | *Simplification for MVP:* Rather than live polling massive GEE rasters on every API call (high latency), pre-fetch/cache representative Sentinel-5P raster tiles for the pilot corridor via Earth Engine and overlay as a toggleable map layer. |
| **MODIS / VIIRS (NASA FIRMS)** | Active thermal anomaly/fire point detection. | **MVP** | *Retain for MVP:* NASA FIRMS provides a lightweight open REST API returning CSV/JSON coordinates of active fires within a bounding box. Very simple to integrate, highly visual, and directly validates biomass burning reports. |
| **Federated Model Sharing** | Distributing model updates across independent city nodes. | **FUTURE** | *Defer to Future:* True federated learning (e.g., Flower / TensorFlow Federated) is unnecessary for a 3-minute hackathon demo. Represent federation at MVP through **standardized OpenAPI data contracts** and a **multi-city configuration profile switcher**. |
| **GRAP Statutory Decision Logic** | Mapping detected pollution to statutory Indian mitigation directives. | **MVP** | *Retain for MVP:* Implemented as a clean, deterministic Python dictionary / lookup engine mapping pollutant severity + detected source to statutory Graded Response Action Plan (GRAP-I through GRAP-IV) actions. Highly impactful for judges. |
| **Cross-City Interoperability** | Multi-city architecture demonstrating national scalability. | **MVP (Dual-City Switcher)** | *Retain for MVP:* Provide a seamless one-click toggle between **Delhi NCR** (Primary Pilot) and **Bengaluru** (Secondary Validation City), proving the system is a portable platform rather than a hardcoded single-city prototype. |

---

## 4. The Concrete MVP Boundary: What We Are Building vs. Skipping

### Exactly What Is Built in the MVP (7 Core Capabilities)
1. **Interactive Environmental Intelligence Map:** Mapbox / Google Maps base canvas rendering official CAAQMS stations, low-cost sensor nodes, pre-rendered satellite layers, and computed hotspot bounding polygons with high-contrast, clean visual design.
2. **Citizen Multimodal Evidence Intake:** Responsive web interface (mobile-friendly PWA) allowing photo upload, audio voice note, category selection, and device GPS capture.
3. **Gemini Multimodal Triage Engine:** FastAPI microservice calling Gemini Flash to verify smoke/dust presence, estimate optical haze severity, transcribe vernacular audio, and return structured JSON.
4. **Spatial Anomaly & Hidden Hotspot Engine:** Background calculation comparing localized sensor/crowd readings against regional baseline; flags anomalous clusters with DBSCAN.
5. **Multi-Source Evidence Fusion Matrix:** Calculates an auditable 0–100 Confidence Index by corroborating citizen photos, downwind sensor spikes, wind vectors, and FIRMS thermal fire points.
6. **Short-Term Corridor Forecaster:** Trained LightGBM model generating 1-hour, 3-hour, and 6-hour PM2.5 projections with confidence intervals for major transport/industrial corridors.
7. **Municipal Authority Console & Action Dispatcher:** Professional split-pane interface presenting prioritized incidents, evidence audit trails, Gemini-generated operational briefs, and GRAP mitigation directives.

### Explicitly Excluded from MVP (Deferred to Future)
- ❌ NO custom native Android / iOS app store builds (Mobile web PWA is sufficient).
- ❌ NO live video stream / RTSP CCTV processing.
- ❌ NO physical IoT hardware fabrication or deployment.
- ❌ NO complex full-stack deep learning architectures (Transformers / LSTMs).
- ❌ NO continuous real-time planetary GEE raster compute on every user request (use cached GEE rasters).
- ❌ NO distributed federated learning cluster infrastructure.
- ❌ NO dark-mode or glowing neon dashboard aesthetics.

---

## 5. Google Technology Stack Review (Minimum & Meaningful)

To achieve maximum hackathon judging alignment without adding architectural bloat, we lock the Google stack to 5 core services:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              FOCUSED GOOGLE AI & CLOUD STACK                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. GEMINI API (Gemini Flash via google-genai SDK) [MUST HAVE]                          │
│    - Role: Multimodal perception (smoke verification, optical opacity), audio          │
│      transcription (Hindi/vernacular to English), and structured JSON incident briefs. │
│    - Why: Sub-2s latency, high multimodal reasoning, native support for JSON schema.   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. GOOGLE MAPS PLATFORM (JavaScript API + Geocoding) [MUST HAVE]                       │
│    - Role: Vector base map, client-side spatial rendering, reverse geocoding to        │
│      exact street landmarks for flying squad dispatch.                                 │
│    - Why: Gold standard for Indian street geometry, landmark naming, and spatial UI.   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. GOOGLE EARTH ENGINE (GEE Python API) [MUST HAVE / CACHED PIPELINE]                  │
│    - Role: Extracting representative Sentinel-5P NO2 and aerosol rasters for the       │
│      Delhi and Bengaluru pilot bounding boxes.                                         │
│    - Why: Unrivaled satellite catalog access for environmental ground-truthing.        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. CLOUD RUN [MUST HAVE]                                                               │
│    - Role: Serverless containerized deployment of the FastAPI backend and LightGBM     │
│      inference service.                                                                │
│    - Why: Auto-scaling, low cost, fast deploys, frictionless live URL for hackathon.   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 5. FIREBASE (Firestore & Cloud Storage) [MUST HAVE]                                    │
│    - Role: Reactive real-time document store for active incidents and authority        │
│      dispatch states; cloud storage bucket for uploaded citizen photos.                │
│    - Why: Real-time UI synchronization without building custom WebSocket servers.      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ DEFERRED / CONDITIONAL SERVICES:                                                       │
│ • BigQuery: OPTIONAL — Use SQLite / DuckDB locally in MVP; stream to BigQuery only     │
│   if cloud analytical audit logs are required during Phase 8.                          │
│ • Vertex AI: FUTURE — Local LightGBM inside Cloud Run container is faster, cheaper,   │
│   and less prone to cloud authentication delays during live hackathon judging.         │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Data Strategy Review (Minimum Viable Datasets)

*In compliance with Phase 0 rules, no data is downloaded or created in Phase 0.5. Sources are triaged strictly for downstream implementation.*

### 6.1 REQUIRED for MVP
1. **Official Air Quality Baseline (Delhi & Bengaluru):**
   - Public CAAQMS stations via OpenAQ REST API or CPCB public telemetry feed.
   - Fields: Station name, lat/long, timestamp, PM2.5, PM10, AQI.
   - Role: Macro-monitoring background against which hyper-local anomalies are computed.
2. **Hourly Meteorological Telemetry & Forecasts:**
   - Open-Meteo Historical & Hourly Forecast API (Open access, verified).
   - Fields: Temperature, Relative Humidity, Wind Speed (10m), Wind Direction (10m), Surface Pressure, Planetary Boundary Layer Height (PBLH).
   - Role: Inputs for LightGBM corridor forecasting and downwind dispersion cone calculations.
3. **Active Fire & Thermal Anomalies:**
   - NASA FIRMS REST API (Open access, verified).
   - Fields: Lat, Long, Brightness, Confidence, Satellite (MODIS/VIIRS), Timestamp.
   - Role: Macro-corroboration of open biomass/industrial burning reports.
4. **Representative Sentinel-5P Satellite Layer:**
   - Google Earth Engine (COPERNICUS/S5P/NRTI/L3_NO2).
   - Pre-rendered spatial raster overlay for Delhi NCR and Bengaluru corridors.
5. **Curated Validation & Demonstration Scenarios:**
   - 5–8 realistic citizen report test fixtures (real photographic evidence of smoke plumes, leaf burning, unpaved construction dust, and clear control scenes) with exact timestamps and GPS tags.

### 6.2 OPTIONAL (Integrate only if time permits)
- Real-time low-cost IoT nodes (PurpleAir / Atmos open public sensors) in Delhi NCR.

### 6.3 FUTURE (Post-Hackathon)
- Citywide continuous CCTV video streams.
- Real-time vehicular GPS tracking from state transit corporations.

---

## 7. 3–5 Minute MVP Live Demonstration Narrative

The demo tells **one single, high-stakes, realistic story** that proves the complete intelligence spine:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        3–5 MINUTE COHESIVE DEMO TIMELINE                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [0:00 - 0:45] ACT 1: THE MONITORING BLINDSPOT                                         │
│ • Open VayuDrishti Map: View Delhi NCR. Official CAAQMS stations show "Moderate" air.  │
│ • Point out Mayapuri Industrial Corridor: 4 km gap between stations; ground reality is│
│   unmonitored.                                                                         │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [0:45 - 1:45] ACT 2: CITIZEN EVIDENCE & GEMINI MULTIMODAL INTAKE                       │
│ • Switch to Citizen Mobile Web PWA: Citizen snaps a photo of dense black smoke from an │
│   unauthorized scrap furnace, adding an audio note in Hindi.                           │
│ • Click "Submit Report". Show live backend processing:                                 │
│   - Gemini Flash analyzes visual plume (detects industrial furnace smoke, High opacity)│
│   - Transcribes Hindi audio to English text.                                           │
│   - Demonstrates guardrail: Show instant rejection of an invalid photo (e.g. coffee cup)│
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [1:45 - 2:45] ACT 3: MULTI-SOURCE CORRELATION & HIDDEN HOTSPOT FLAGGED                 │
│ • Back to Intelligence Map: The report appears. Nearby IoT sensor shows rising PM2.5.  │
│ • Weather layer shows stagnant air (wind 1.4 m/s from NW, boundary layer 220m).        │
│ • System calculates spatial residual (+190 µg/m³ above regional baseline).             │
│ • A prominent amber/red "HIDDEN HOTSPOT" polygon appears on the map.                   │
│ • Inspect the Confidence Card: 92/100, citing verified photo + wind + sensor spike.    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [2:45 - 3:45] ACT 4: CORRIDOR FORECAST & AUTHORITY GRAP DISPATCH                       │
│ • Click "Corridor Forecast": LightGBM predicts plume spreading across Anand Vihar      │
│   transit corridor over the next 3 hours (projecting Severe AQI > 350 µg/m³).          │
│ • Switch to Municipal Authority Console: High-priority incident card is waiting.       │
│ • Show Gemini operational brief with statutory GRAP directives:                        │
│   - "Dispatch Flying Squad Team 3 to Gate 4; Halt unpaved transit; Deploy mist cannon."│
│ • Officer clicks "Acknowledge & Dispatch" -> status updates in real-time.              │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [3:45 - 4:30] ACT 5: CROSS-CITY INTEROPERABILITY PROOF & CLOSING                       │
│ • Click City Selector: Toggle from "Delhi NCR" to "Bengaluru (Peenya)".                │
│ • Map smoothly transitions, loading Bengaluru CAAQMS and local industrial boundaries   │
│   using the exact same data schema and UI components.                                  │
│ • Close: "VayuDrishti turns passive air quality data into active civic enforcement."   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Permanent UI/UX Design Lock & Aesthetic Standards

The design rules from Phase 0 are strictly reaffirmed for all subsequent development phases:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              HUMAN-DESIGNED UI/UX CONTRACT                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ • VISUAL THEME: Light, Calm, Utilitarian, Civic, Professional.                         │
│ • BASE CANVAS: Crisp white (#FFFFFF) and subtle slate (#F8FAFC).                       │
│ • TYPOGRAPHY: Inter or Plus Jakarta Sans. Clean, legible, high typographic hierarchy.  │
│ • COLOR LANGUAGE:                                                                      │
│   - Slate Navy (#0F172A) for chrome and primary navigation.                            │
│   - Forest Sage (#15803D) for Good/Moderate air quality.                               │
│   - Warm Amber (#D97706) for Poor/Unhealthy air quality.                               │
│   - Terracotta Rust (#DC2626) for Severe/Hazardous air quality.                        │
│   - Thin slate borders (#E2E8F0). High whitespace ratio.                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ STRICTLY PROHIBITED (PERMANENT BAN):                                                   │
│   ❌ Dark-mode hacker / cyberpunk themes.                                              │
│   ❌ Neon green, glowing cyan, or purple glowing card borders.                         │
│   ❌ Blurry translucent glassmorphism panels.                                          │
│   ❌ Decorative floating 3D spheres, animated particles, or robotic AI branding.      │
│   ❌ Unreadable, cluttered chart graveyards.                                           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Sequential Implementation Roadmap (Phases 1 to 10)

To maintain rigorous engineering control, development proceeds through 10 strictly bounded, sequential phases. **Each phase must be tested and committed before starting the next.**

```
Phase 1: Architecture & Foundation Setup
  ├── Establish FastAPI backend skeleton & configuration loader
  ├── Establish React (Vite + Tailwind CSS) frontend scaffold
  └── Connect base health endpoints and environment validation

Phase 2: Environmental Data Ingestion Pipeline
  ├── Ingest CPCB/OpenAQ CAAQMS telemetry for Delhi & Bengaluru
  ├── Connect Open-Meteo weather endpoint (wind, temp, PBLH)
  └── Fetch NASA FIRMS active fire anomalies

Phase 3: Interactive Geospatial Intelligence Map
  ├── Render Google Maps / Mapbox base canvas
  ├── Plot CAAQMS stations with dynamic color-coded AQI markers
  └── Add layer toggles for weather wind vectors & satellite thermal anomalies

Phase 4: Citizen Multimodal Evidence Engine
  ├── Build responsive mobile-web PWA photo/voice reporting modal
  ├── Integrate Gemini Flash Multimodal API for visual plume & optical density triage
  └── Implement Gemini vernacular audio transcription and anti-spam rejection filter

Phase 5: Spatial Anomaly & Hidden Hotspot Engine
  ├── Compute regional baseline via Inverse Distance Weighting (IDW)
  ├── Compute spatial residual anomalies from localized reports and sensors
  └── Execute DBSCAN clustering to generate hotspot bounding polygons

Phase 6: Short-Term Corridor Forecasting Engine
  ├── Train lightweight LightGBM regressor on meteorological and sensor lag features
  ├── Generate 1h, 3h, 6h PM2.5 predictions with confidence interval bands
  └── Expose forecasting inference endpoint to frontend corridor view

Phase 7: Multi-Source Evidence Fusion & GRAP Decision Support
  ├── Implement multi-source weighted scoring engine (0–100 Confidence Index)
  ├── Map detected incidents to statutory CPCB/GRAP standard operating procedures
  └── Generate plain-language operational incident briefs via Gemini

Phase 8: Municipal Authority Console & Dispatch Workflow
  ├── Build high-priority incident triage drawer and evidence inspection modal
  ├── Implement incident status lifecycle (Pending -> Dispatched -> Resolved)
  └── Integrate cross-city profile switcher (Delhi NCR <-> Bengaluru)

Phase 9: UI/UX Audit & Human-Centered Refinement
  ├── Execute strict visual audit against non-neon, civic-tech design standards
  ├── Optimize responsive layout, spacing, typography, and contrast accessibility
  └── Add loading skeletons, error fallbacks, and polished empty states

Phase 10: Production Deployment & Live Demo Rehearsal
  ├── Deploy backend container to Google Cloud Run
  ├── Deploy frontend to Firebase Hosting / Cloud Run
  └── Rehearse and record the 3–5 minute end-to-end demo incident storyline
```

---

## 10. Final Scope Freeze Agreement

This agreement permanently locks the MVP boundaries for VayuDrishti:

- **What Will Be Delivered:** A working, live-demonstrable, end-to-end prototype covering citizen multimodal reporting, Gemini Flash visual/audio triage, multi-source evidence fusion, spatial hidden hotspot discovery, LightGBM corridor forecasting, and a GRAP-aligned municipal authority console operating across Delhi and Bengaluru.
- **What Will Not Be Attempted:** Distributed federated learning clusters, hardware sensor fabrication, real-time planetary GEE raster recalculations on client requests, native mobile app store packages, or dark/neon futuristic UI styles.
- **Next Action:** Await user confirmation, then begin **Phase 1 (Architecture & Foundation Setup)** strictly within `F:\CLEAN AIR & CLIMATE RESILIENCE`.

---
**PHASE 0.5 SCOPE FREEZE SIGN-OFF:** LOCKED & IMMUTABLE  
**STATUS:** READY FOR PHASE 1 FOUNDATIONAL SETUP
