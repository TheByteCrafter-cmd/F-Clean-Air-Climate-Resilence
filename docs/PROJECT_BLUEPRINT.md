# Project Blueprint
## VayuDrishti: Hyper-Local Climate Intelligence & Action Platform
**Hackathon:** Build with AI — Code for Communities, Second Edition  
**Theme:** Clean Air & Climate Resilience  
**Status:** PHASE 0 — BLUEPRINT & SCOPE LOCK COMPLETED  
**Repository:** `https://github.com/TheByteCrafter-cmd/F-Clean-Air-Climate-Resilence`  
**Local Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  

---

## 1. Executive Summary

Urban India confronts an acute, persistent air quality crisis. While national and state environmental agencies operate Continuous Ambient Air Quality Monitoring Stations (CAAQMS) across major urban centers, these government stations are spatially sparse—typically 10 to 40 monitors servicing metropolises spanning over 1,000 to 1,500 square kilometers. Consequently, official networks capture regional, macro-level atmospheric trends but remain structurally blind to hyper-local, episodic pollution anomalies: unauthorized municipal waste burning in peri-urban pockets, nocturnal industrial emissions bypassing filters, localized construction dust, fugitive road dust on freight corridors, and agricultural stubble fires on urban fringes.

**VayuDrishti** (*Sanskrit for "Vision of the Air"*) is an AI-powered, federated environmental intelligence and decision-support platform designed specifically for the Indian civic operational context. Rather than acting as another passive, descriptive Air Quality Index (AQI) dashboard, VayuDrishti bridges the gap between macro-monitoring and street-level enforcement by fusing multimodal citizen evidence (geotagged photos, audio descriptions, structured reports), low-cost IoT sensor data, satellite Earth observation (Sentinel-5P TROPOMI, MODIS/VIIRS thermal anomalies), and hyper-local meteorological feeds.

Through a multi-source evidence fusion matrix, VayuDrishti:
1. Detects and validates "hidden hotspots" that escape sparse CAAQMS grids.
2. Forecasts short-term (3 to 6-hour) pollutant spikes across critical urban and economic corridors using gradient-boosted time-series learning.
3. Quantifies uncertainty with explainable confidence scoring, tracing every alert back to its physical and visual evidentiary sources.
4. Equips municipal ward officers and pollution control flying squads with context-aware, actionable intervention directives aligned with India's Graded Response Action Plan (GRAP).

Architected for cross-city interoperability, VayuDrishti enables Indian cities and states to share predictive model weights, sensor protocols, and regional air-shed intelligence without centralizing proprietary municipal databases.

---

## 2. Problem Understanding

### 2.1 The Macro vs. Micro Disconnect
Official monitoring infrastructure under the Central Pollution Control Board (CPCB) and State Pollution Control Boards (SPCBs) relies on regulatory-grade CAAQMS installations costing upwards of Rs 1–1.5 Crore ($120k–$180k USD) each. Due to high procurement and maintenance capital, monitor density is strictly limited:
- **Spatial Blindspots:** In a city like Delhi NCR (over 1,484 km2), ~40 stations yield an average spatial resolution of roughly 1 station per 37 km2. In Bengaluru or Pune, coverage drops to 1 station per 70–100 km2. Air pollution, however, exhibits intense micro-spatial heterogeneity: PM2.5 concentrations can surge from 90 ug/m3 to 480 ug/m3 within 400 meters of an unpaved construction corridor, illegal waste fire, or industrial cluster.
- **Temporal Smoothing:** CAAQMS reports are predominantly published as rolling 1-hour, 8-hour, or 24-hour averages. Transient, high-intensity pollution events (e.g., 2:00 AM industrial furnace flaring or 5:00 AM roadside leaf burning) are smoothed out, masking severe peak exposures from regulatory action.
- **Topographic & Dispersion Blindness:** Surface-level temperature inversions, common during Indian winters (October–February), trap micro-plumes in local thermal pockets that never rise to the height of regional monitoring towers.

### 2.2 Operational Roadblocks for Authorities
Municipal enforcement bodies (e.g., Municipal Corporation of Delhi [MCD], Bruhat Bengaluru Mahanagara Palike [BBMP]) and Pollution Control Boards operate with limited flying-squad personnel. They face two paralyzing operational bottlenecks:
1. **Unverified Grievance Deluge:** Citizen complaint portals (such as Green Delhi App or generic municipal complaint systems) receive thousands of raw, unstructured reports daily. Without automated validation or visual triage, enforcement officers cannot distinguish between an urgent illegal industrial emission and an unverified duplicate, leading to alert fatigue and delayed field response.
2. **Absence of Prognostic Decision Support:** Existing environmental portals are purely retrospective—they show what *already happened*. They do not forecast where a plume will drift over the next 3 to 6 hours based on boundary-layer dynamics, nor do they specify *which exact intervention* (anti-smog gun dispatch, mechanized sweeping, traffic diversion, factory inspection) delivers the highest mitigation yield.

### 2.3 The Core Architectural Need
The system must move through an unbroken analytical chain:
Observation -> Detection -> Correlation -> Prediction -> Risk Assessment -> Decision Support

---

## 3. Product Vision

VayuDrishti transforms urban environmental management from **passive retrospective monitoring** to **proactive, evidence-grounded civic intervention**. 

The system treats air pollution not as a static atmospheric number, but as a dynamic spatial phenomenon driven by identifiable emission sources, transport physics, and human activity. By integrating citizen eyes on the ground with satellite eyes in the sky and mathematical dispersion physics, VayuDrishti provides a trusted, auditable common operating picture for both civil society and regulatory authorities.

---

## 4. Product Name & Identity

- **Official Product Name:** **VayuDrishti**
- **Sub-Title:** *Hyper-Local Climate Intelligence & Action Platform*
- **Etymology:** Derived from *Vayu* (Sanskrit for wind/air) and *Drishti* (Sanskrit for vision/insight).
- **One-Line Value Proposition:** "Bridging the gap between satellite horizons and street-level air through multi-source evidence fusion, predictive corridor forecasting, and actionable civic intervention."

---

## 5. Target Users

To avoid feature bloat, VayuDrishti focuses on four well-defined user personas across the public sector and civil society:

| User Persona | Institutional Affiliation | Core Problem | Required Information | Platform-Enabled Action |
| :--- | :--- | :--- | :--- | :--- |
| **Municipal Ward Officer / Flying Squad Leader** *(Primary)* | Urban Local Bodies (e.g., MCD, BBMP, BMC Ward Offices) | Receives delayed or vague complaints; lacks real-time verification before deploying expensive ground resources (water sprinklers, anti-smog guns). | Geotagged micro-hotspot alerts, AI-verified image evidence, optical severity estimate, exact street landmark, priority ranking. | Dispatches targeted anti-smog water misting, halts non-compliant construction, inspects localized waste burning, logs resolution with photo verification. |
| **SPCB / CPCB Environmental Scientist & Regulator** *(Primary)* | State Pollution Control Boards (DPCC, KSPCB, MPCB) | Blind to nighttime industrial emissions and peripheral stubble/waste burning; cannot isolate localized point-source violations from regional background. | Multi-source evidence score, satellite thermal anomaly overlay, downwind sensor divergence, industrial zone buffer correlation, plume trajectory forecast. | Issues regulatory show-cause notices, executes surprise nocturnal industrial audits, coordinates inter-district emergency interventions. |
| **Civic Community Champion / Resident** *(Secondary)* | Resident Welfare Associations (RWAs), Civil Society Groups, Commuters | Experiences severe local smog without official recognition; citizen reports disappear into bureaucratic black holes without feedback. | Hyper-local neighborhood exposure risk, short-term (3-hr) spike forecast, transparent status of community-submitted evidence. | Submits geotagged photographic/voice evidence of episodic pollution; plans outdoor activities; mobilizes neighborhood-level clean air compliance. |
| **Urban Environmental Planner & Policy Analyst** *(Secondary)* | Urban Development Authorities, NCAP Research Nodes | Lacks granular historical spatial data to identify recurring micro-corridor pollution bottlenecks for infrastructure planning. | Spatial-temporal heatmaps of recurrent hidden hotspots, corridor emission profiles, intervention efficacy audits. | Designs targeted green buffer zones, optimizes low-emission transit routes, adjusts zoning bylaws for industrial and logistics hubs. |

---

## 6. Critical User Journeys

### Journey A: Citizen Reports an Episodic Pollution Event
- **User Action:** A citizen encounters heavy black smoke billowing from an unauthorized industrial scrap furnace at 6:30 AM. Using the mobile web interface, the citizen snaps a photo, adds a brief voice note in Hindi (*"Yahan factory se bahut kaala dhuan nikal raha hai"*), and submits with GPS location.
- **Data Ingestion:** The client captures image payload, EXIF timestamp, device GPS coordinates, and audio binary, posting to the ingestion endpoint.
- **Processing & Multimodal AI:**
  1. Image is processed by **Gemini Multimodal**: verifies presence of smoke plume, checks optical opacity, classifies source type as `industrial_smoke`, rejects non-pollution images (e.g., selfies, clear sky).
  2. Audio note is transcribed and translated via **Gemini Audio / Speech Intelligence** to extract contextual cues.
  3. Image perceptual hash (pHash) and spatial bounding checks ensure deduplication against other nearby submissions.
- **Result:** System creates a verified `CitizenObservationEvent` with an initial visual confidence score of 0.88.
- **Action:** Citizen receives instant verification receipt with incident tracking ID.

### Journey B: System Detects and Correlates a "Hidden Hotspot"
- **System Action:** Background cron triggers the Spatial Correlation Engine for the industrial corridor grid.
- **Data Integration:**
  1. Gathers citizen observation from Journey A (location at time t).
  2. Queries nearest official CAAQMS station (3.8 km away): reports moderate PM2.5 (110 ug/m3)—failing to indicate an emergency.
  3. Queries two nearby low-cost IoT nodes (500m and 900m downwind): both show sharp PM2.5 spikes from 120 to 340 ug/m3 within 25 minutes.
  4. Fetches real-time weather: wind speed 1.8 m/s from NW (315 deg), low planetary boundary layer (240m), high atmospheric stability.
  5. Checks MODIS/VIIRS satellite feed: detects low-confidence thermal anomaly pixel 350m upwind.
- **AI/ML Processing:** Multi-Source Evidence Fusion Matrix computes a composite **Hotspot Confidence Index of 92/100** and flags a `HIDDEN_HOTSPOT_ALERT`.
- **Result:** System isolates an unmonitored point-source emission event that CAAQMS completely missed.
- **Action:** Alert is pushed into the Municipal/SPCB Authority Incident Queue.

### Journey C: Short-Term Pollution Spike Forecasting
- **System Action:** Forecasting Engine runs hourly inference over major economic transport and industrial corridors.
- **Data Ingestion:** Lagged 6-hour pollutant concentrations, forecasted wind vectors, boundary layer height, temperature inversion index, and historical diurnal traffic trends.
- **ML Processing:** **LightGBM / XGBoost Corridor Regressor** predicts PM2.5 trajectory for the next 1, 3, and 6 hours. Model projects a 65% surge in PM2.5 (reaching 380 ug/m3 - *Severe*) along the freight corridor between 8:00 PM and 11:00 PM due to evening freight influx and plunging boundary layer height.
- **Result:** Pre-incident advisory generated 3 hours before peak exposure occurs.
- **Action:** Operational alert dispatched to traffic police and municipal teams to initiate pre-emptive wet-sweeping and freight staging.

### Journey D: Authority Receives and Triumphs an Actionable Alert
- **User Action:** Ward Flying Squad Officer opens the VayuDrishti Authority Console on a tablet.
- **System Presentation:** Console presents an urgent high-priority incident card:
  - *Location:* Mayapuri Industrial Phase-II, Grid Ref: 28.628, 77.114.
  - *Confidence:* 91% (Evidence: 3 citizen photos verified by Gemini, 2 IoT sensor spikes, wind vector alignment).
  - *Identified Cause:* Nocturnal metal burning / scrap melting.
  - *Recommended GRAP Action:* Dispatch flying squad team #4; inspect scrap yard clusters; deploy Mobile Anti-Smog Unit #2.
- **Action:** Officer clicks "Acknowledge & Dispatch Squad", routing coordinates directly to the squad vehicle navigation.

### Journey E: Authority Field Investigation and Resolution Closure
- **User Action:** Flying squad arrives at the coordinates, halts unauthorized burning, douses embers with municipal water support, and issues a statutory penalty.
- **Data Submission:** Officer captures geotagged post-intervention photo and logs resolution notes into the console.
- **System Update:** Gemini validates smoke cessation in the follow-up image; downwind IoT sensors register PM2.5 decline back to baseline.
- **Result:** Incident status transitions from `DISPATCHED` -> `RESOLVED`.
- **Action:** Audit trail logged to BigQuery; resolution confirmation notified back to reporting citizens to build civic trust.

---

## 7. Core MVP Scope & Capabilities

The hackathon MVP strictly emphasizes depth, technical integrity, and working multi-source intelligence over sheer feature quantity.

| Capability | Purpose | Inputs | Processing | Output | User Value | Google Tech Stack | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Hyper-Local Intelligence Map** | Interactive spatial visualization of macro vs. micro air quality. | CAAQMS feeds, IoT nodes, satellite overlays, validated citizen reports. | Spatial indexing, Mapbox/Google Maps raster/vector tile rendering, layer toggling. | Unified situational map with heatmaps, sensor pins, and hotspot clusters. | Single pane of glass for citizens and regulators. | Google Maps Platform / Earth Engine API | **MUST HAVE** |
| **2. Hidden Hotspot Detection Engine** | Automatically identifies localized anomalies missed by official stations. | CAAQMS telemetry, low-cost sensor data, citizen report clusters. | Spatial kriging/IDW background interpolation, anomaly residual scoring (Z-score >= 2.5). | Flagged hotspot bounding polygons with severity ratings. | Eliminates spatial monitoring blindspots. | Cloud Run (FastAPI engine) | **MUST HAVE** |
| **3. Multimodal Citizen Evidence Triage** | Automated validation and feature extraction from crowd reports. | Geotagged images, audio notes, text descriptions, GPS. | Visual object & plume verification, optical smoke density estimation, audio transcription. | Structured JSON: `is_valid_pollution`, `source_type`, `severity`, `rationale`. | Prevents spam, filters duplicates, verifies ground reality. | Gemini API (Gemini Flash multimodal) | **MUST HAVE** |
| **4. Multi-Source Evidence Fusion** | Combines citizen, sensor, weather, and satellite data into trusted score. | Gemini visual score, sensor Z-scores, wind vector, thermal anomaly. | Weighted Bayesian fusion algorithm, cross-signal corroboration. | Composite Confidence Score (0–100) + Primary Contributing Factors. | Prevents false alarms; builds legal/regulatory credibility. | Cloud Run, BigQuery | **MUST HAVE** |
| **5. Short-Term Corridor Forecaster** | Predicts PM2.5 spikes 1 to 6 hours ahead across urban corridors. | 6-hr pollutant lags, weather forecasts (wind, temp, boundary layer). | Tabular Gradient Boosted Regressor (LightGBM/XGBoost) with quantile loss. | Point forecast + 10th/90th percentile prediction intervals. | Enables proactive mitigation before exposure peaks. | Vertex AI / Cloud Run | **MUST HAVE** |
| **6. Authority Decision Support & Alerting** | Translates raw AI predictions into statutory, actionable field tasks. | Hotspot location, confidence score, pollutant severity, land-use zone. | Rule-based GRAP SOP mapping matrix + Gemini natural language briefing. | Actionable incident dossier with recommended equipment & inspection targets. | Saves critical response time for municipal flying squads. | Gemini API, Firebase Firestore | **MUST HAVE** |
| **7. Cross-City Interoperability Spec** | Demonstrates multi-city scalability and federated model portability. | Data schemas from 2 distinct pilot cities (Delhi & Bengaluru). | Standardized GeoJSON FeatureCollection contracts, model domain transfer logic. | Live toggle between pilot geographies using unified data contracts. | Proves solution is a scalable national platform, not a single-city toy. | BigQuery federated schemas | **MUST HAVE** |
| **8. Automated Health Advisory Dispatch** | Push localized health warnings to affected citizens downwind. | Predicted plume trajectory, residential population density. | Spatial buffer intersection, vulnerability classification. | Hyper-local citizen alerts ("High smog expected in next 3 hours - avoid jogging"). | Protects public health proactively. | Firebase Cloud Messaging | *SHOULD HAVE* |
| **9. Historical Intervention Efficacy Tracker** | Analyzes whether municipal action actually reduced local pollution. | Pre- and post-intervention IoT sensor readings. | Time-series changepoint detection. | Empirical mitigation delta report (e.g., "-42 ug/m3 within 45 mins"). | Holds civic administration accountable. | BigQuery | *SHOULD HAVE* |
| **10. Drone / Edge Camera Stream Ingestion** | Continuous automated surveillance of industrial smokestacks. | Real-time RTSP video feeds from surveillance cameras. | Computer vision frame-by-frame plume detection. | Automated trigger without human citizen involvement. | Continuous passive monitoring. | Vertex AI Vision | *FUTURE* |

---

## 8. Data Strategy

*Note: In adherence to Phase 0 requirements, all non-verified external sources are explicitly designated as **"CANDIDATE SOURCE — TO BE VERIFIED"**. No datasets are downloaded or fabricated during Phase 0.*

```
                                  DATA SOURCES ARCHITECTURE
+-------------------------------------------------------------------------------------------+
| AIR QUALITY DATA                                                                          |
|  - Central Pollution Control Board (CPCB) CAAQMS via OpenAQ API [CANDIDATE - VERIFIED]    |
|  - Low-Cost IoT Sensor Networks (PurpleAir / Atmos / Open Public Nodes) [TO BE VERIFIED] |
+-------------------------------------------------------------------------------------------+
| METEOROLOGICAL DATA                                                                       |
|  - Open-Meteo Historical & Hourly Forecast API (Wind u/v, Temp, RH, PBLH) [VERIFIED]     |
|  - India Meteorological Department (IMD) Open Data Portals [CANDIDATE - TO BE VERIFIED]  |
+-------------------------------------------------------------------------------------------+
| SATELLITE & EARTH OBSERVATION                                                             |
|  - Sentinel-5P TROPOMI (NO2 tropospheric column, Aerosol Index) via GEE [VERIFIED]        |
|  - NASA FIRMS MODIS/VIIRS Active Fire Products (Thermal Anomalies) [VERIFIED]            |
+-------------------------------------------------------------------------------------------+
| GEOSPATIAL & LAND-USE CONTEXT                                                             |
|  - OpenStreetMap (OSM) Road Network, Industrial Zones, Brick Kilns [VERIFIED]             |
|  - Survey of India / Municipal Ward Boundaries [CANDIDATE - TO BE VERIFIED]               |
+-------------------------------------------------------------------------------------------+
| CROWDSOURCED CITIZEN EVIDENCE                                                             |
|  - Geotagged imagery, optical smoke observations, voice memos, categorical tags [INTERNAL]|
+-------------------------------------------------------------------------------------------+
```

### Data Category Specifications

1. **Air Quality Data:**
   - *Fields:* `station_id`, `latitude`, `longitude`, `timestamp_utc`, `pm2_5`, `pm10`, `no2`, `so2`, `co`, `aqi`.
   - *Role:* Ground-truth baseline for macro-conditions; training targets for predictive models; baseline against which hyper-local anomalies are computed.
   - *Latency:* Hourly (CAAQMS); 5–15 minutes (IoT sensors).
   - *Sources:* CPCB / OpenAQ REST API (*Candidate Source — verified public endpoint*); Low-cost community sensors (*Candidate Source — to be verified for pilot bounding box*).

2. **Meteorological Data:**
   - *Fields:* `temperature_2m`, `relative_humidity_2m`, `wind_speed_10m`, `wind_direction_10m`, `surface_pressure`, `planetary_boundary_layer_height`, `precipitation`.
   - *Role:* Primary physical driver of atmospheric dispersion, stagnation, and plume transport. Critical input for short-term spike forecasting.
   - *Latency:* Hourly historical + 24-hour forward forecast.
   - *Sources:* Open-Meteo API (*Verified open API*); ECMWF ERA5 reanalysis via GEE (*Verified*).

3. **Satellite & Earth Observation:**
   - *Fields:* `tropospheric_NO2_column_number_density`, `absorbing_aerosol_index`, `brightness_temperature`, `fire_radiative_power_frp`, `confidence`.
   - *Role:* Macro-verification of regional stubble burning, major industrial clusters, and transboundary smog transport; validates whether a ground spike is localized or part of a regional air-mass.
   - *Latency:* Daily revisit (Sentinel-5P, MODIS/VIIRS).
   - *Sources:* Google Earth Engine catalog (`COPERNICUS/S5P/NRTI/L3_NO2`, `FIRMS`).

4. **Geographic, Industrial & Road Infrastructure Context:**
   - *Fields:* `osm_id`, `highway_type`, `industrial_zone_polygon`, `landuse_classification`, `vulnerable_poi_type` (schools, hospitals).
   - *Role:* Spatial priors: increases prior probability of pollution in designated industrial/freight zones; calculates vulnerable populations downwind.
   - *Latency:* Static vector layers.
   - *Sources:* OpenStreetMap Overpass API (*Verified*).

5. **Citizen Evidence Data:**
   - *Fields:* `report_id`, `user_hash`, `latitude`, `longitude`, `timestamp`, `image_url`, `audio_url`, `user_selected_category`, `gemini_verification_score`, `gemini_detected_type`, `gemini_reasoning`.
   - *Role:* Real-time ground sensor extension in unmonitored neighborhoods.
   - *Latency:* Real-time event-driven.
   - *Sources:* Native mobile-web PWA interface.

---

## 9. AI/ML Strategy

The AI stack adheres strictly to architectural pragmatism: **use generative AI where perception, language, and unstructured reasoning are required; use deterministic machine learning and physics where tabular forecasting, anomaly detection, and speed are required.**

```
                                      AI/ML MODULAR ARCHITECTURE
+-----------------------------------+               +-----------------------------------+
|     MULTIMODAL PERCEPTION         |               |     TABULAR PREDICTIVE ML         |
|     (Gemini 1.5/2.0 Flash)        |               |     (LightGBM / XGBoost)          |
+-----------------------------------+               +-----------------------------------+
| * Smoke plume visual confirmation |               | * PM2.5 1h, 3h, 6h forward trends |
| * Optical opacity classification  |               | * Quantile loss (P10, P50, P90)   |
| * Multilingual voice transcription|               | * Engineered meteorological lags  |
| * Anti-spam / fraud verification  |               | * Diurnal & traffic cycle factors |
+-----------------+-+---------------+               +-----------------+-+---------------+
                  |                                                   |
                  +-------------------------+-------------------------+
                                            |
                                            v
+---------------------------------------------------------------------------------------+
|                      SPATIO-TEMPORAL FUSION & REASONING LAYER                         |
|  - Spatial Anomaly Detection (Kriging Residuals + DBSCAN Report Clustering)           |
|  - Multi-Source Evidence Weighting Matrix (Bayesian confidence formulation)           |
|  - Downwind Dispersion Consequence Modeling (Gaussian plume dispersion proxy)         |
+-------------------------------------------+-------------------------------------------+
                                            |
                                            v
+-----------------------------------+               +-----------------------------------+
|     DECISION SUPPORT RULES        |               |     EXPLAINABLE GENERATION        |
|     (Deterministic GRAP Logic)    |               |     (Gemini API)                  |
+-----------------------------------+               +-----------------------------------+
| * Strict CPCB/GRAP SOP matching   |               | * Plain-language incident summary |
| * Threshold-based task assignment |               | * Causal signal breakdown         |
| * Statutory audit compliance logs |               | * Actionable field instructions   |
+-----------------------------------+               +-----------------------------------+
```

### Module Specifications

#### A. Multimodal Citizen Intelligence (Generative AI)
- **Technique:** Google Gemini Flash via the official `google-genai` Python SDK.
- **Input:** Raw citizen JPEG/PNG image, optional AAC/WAV audio memo, user metadata.
- **Processing:** Structured output enforcement using Pydantic schema:
  - Visual verification: Detects open fires, furnace smoke, dense construction dust plumes, vehicular traffic smog.
  - Optical density ranking: Categorizes haze as `Low`, `Medium`, `High`, or `Severe`.
  - Audio transcription: Multilingual parsing (Hindi, Marathi, Kannada, English) into standardized English narrative.
  - Rejection mechanism: Immediate dismissal of invalid images (indoor photos, screenshots, unrelated objects) with polite user feedback.
- **Evaluation Metric:** Precision/Recall on a benchmark validation set of 100 labeled civic pollution images (target precision >= 90%).

#### B. Short-Term Corridor Forecasting (Predictive Machine Learning)
- **Technique:** LightGBM / XGBoost Regressor with Quantile Regression objective (alpha = 0.1, 0.5, 0.9).
- **Why Tabular Boosting?** Air quality time-series at 1-hour resolution are overwhelmingly driven by tabular meteorological interactions (wind speed x boundary layer height, temperature inversion thresholds). Gradient-boosted trees train in seconds, execute inference in < 5 milliseconds, require minimal computational overhead, and deliver superior explainability via SHAP (SHapley Additive exPlanations) values compared to opaque deep recurrent networks (LSTM/Transformers).
- **Features:** Lagged PM2.5 (t-1, t-2, t-3, t-6), 24h rolling mean, 24h rolling std, wind u-component, wind v-component, boundary layer height, temperature, relative humidity, planetary boundary layer change rate, hour-of-day (sine/cosine encoded), day-of-week.
- **Output:** Predicted PM2.5 concentration (ug/m3) at t+1h, t+3h, t+6h with 80% confidence interval band [P10, P90].
- **Evaluation Metric:** Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE) against CAAQMS ground truth (provisional target: MAE < 25 ug/m3 during non-emergency periods).

#### C. Geospatial Anomaly & Hotspot Clustering
- **Technique:** 
  1. Spatial Ordinary Kriging / Inverse Distance Weighting (IDW) interpolation across sparse CAAQMS stations to generate expected regional baseline.
  2. Localized sensor/citizen deviation calculation: Residual = Local Reading - Expected Regional Baseline.
  3. Spatial clustering of verified citizen reports using **DBSCAN** (Density-Based Spatial Clustering of Applications with Noise), with epsilon = 750 meters and min_samples = 2.
- **Output:** Bounding geographic centroid of clustered anomalies marked as `POTENTIAL_HIDDEN_HOTSPOT`.

#### D. Decision Support & Recommendation Generation
- **Technique:** Hybrid Rule-Engine + Gemini Synthesis.
  - Rule-engine maps severity level and detected source to India's statutory Graded Response Action Plan (GRAP-I through GRAP-IV) standard operating procedures.
  - Gemini takes the matched SOP, local weather, and nearby sensitive receptors (schools, hospitals) to synthesize a concise, 3-bullet operational dispatch brief for the ward officer.

---

## 10. Google Technology Strategy

Every Google technology in VayuDrishti is selected strictly for its functional fit, avoiding unnecessary architectural inflation:

| Google Technology | Specific Architectural Role | Why It Is Uniquely Needed | Fit Evaluation | Priority |
| :--- | :--- | :--- | :--- | :--- |
| **Gemini API (Gemini Flash)** | Multimodal citizen evidence verification; audio transcription; explainable alert brief generation. | Fast multimodal inference (sub-2-second latency); cost-effective token processing; native Hindi/English understanding; structured JSON output schema support. | Essential perception and reasoning engine. | **MUST HAVE** |
| **Google Maps Platform** | Authority & citizen web map interface; reverse geocoding; road corridor overlays. | Unrivaled spatial base-map fidelity in Indian cities; highly accurate reverse geocoding to street-level landmarks for field enforcement. | Front-facing spatial UI. | **MUST HAVE** |
| **Google Earth Engine (GEE)** | Server-side extraction of Sentinel-5P TROPOMI NO2 and NASA FIRMS active fire datasets. | Planetary-scale geospatial catalog; allows programmatic cloud extraction of satellite rasters over pilot bounding boxes without downloading massive raw NetCDF/GeoTIFF files. | Macro-atmospheric validation. | **MUST HAVE** |
| **Cloud Run** | Serverless hosting of containerized FastAPI backend, ML inference microservices, and fusion engine. | Auto-scaling container execution; low-latency cold starts; native integration with Google Cloud ecosystem; ideal for hackathon budget & live demo reliability. | Core backend compute. | **MUST HAVE** |
| **Firebase (Firestore & Storage)** | Real-time database for active incidents, citizen reports, authority status syncing, and image blob storage. | Instant client-side reactive subscriptions (WebSockets/listeners); out-of-the-box secure photo upload URLs; rock-solid mobile-web integration. | Operational real-time data layer. | **MUST HAVE** |
| **BigQuery** | Analytical data warehouse for historical sensor time-series, model performance tracking, and cross-city analytics. | Serverless SQL at scale; native spatial GIS functions (`ST_CONTAINS`, `ST_DISTANCE`); ideal for running corridor-wide spatial aggregations across millions of data points. | Analytical backbone. | **SHOULD HAVE** *(Architected for Scale)* |
| **Vertex AI** | Managed model training and deployment for tabular forecasting models. | Experiment tracking and model registry if transitioning from local containerized LightGBM to automated cloud pipelines. | MLOps operationalization. | **SHOULD HAVE** |

---

## 11. Hyper-Local Hotspot Detection

### 11.1 Defining the "Hidden Hotspot"
A **Known Hotspot** is a location where an existing permanent CAAQMS station registers elevated pollutant levels (e.g., Anand Vihar in Delhi or Silk Board in Bengaluru). 

A **Hidden Hotspot** is a localized micro-environment (200m - 1.5km radius) experiencing acute, hazardous pollutant concentrations that:
1. Sits in a spatial blindspot between official CAAQMS stations.
2. Is triggered by episodic, transient, or unauthorized ground activities (biomass burning, illegal furnace melting, construction excavation, freight idling).
3. Produces a plume that disperses or settles before regional monitors register significant changes.

### 11.2 Detection Methodology Without Direct Sensor Coverage

```
                               HIDDEN HOTSPOT DETECTION LOGIC
+------------------------+    +------------------------+    +------------------------+
|  CITIZEN REPORTS       |    |  LOW-COST SENSORS      |    |  SATELLITE & WEATHER   |
|  - Geotagged clusters  |    |  - Downwind sensor     |    |  - Thermal fire pixel  |
|  - Gemini smoke score  |    |    elevations          |    |  - Wind vector checks  |
+-----------+------------+    +-----------+------------+    +-----------+------------+
            |                             |                             |
            +----------------------+      |      +----------------------+
                                   |      |      |
                                   v      v      v
                   +-------------------------------------------+
                   |       SPATIAL RESIDUAL CALCULATION        |
                   |  Delta = Local Signal - Kriged Baseline   |
                   +---------------------+---------------------+
                                         |
                                         v
                   +-------------------------------------------+
                   |       CROSS-VALIDATION FILTER             |
                   |  Is residual supported by >= 2 modalities |
                   |  (e.g., photo + downwind IoT sensor)?     |
                   +---------------------+---------------------+
                                         |
                                         v
                   +-------------------------------------------+
                   |    FLAG: POTENTIAL_HIDDEN_HOTSPOT         |
                   |    Confidence Score: 0 to 100             |
                   +-------------------------------------------+
```

1. **Step 1: Spatial Kriging Baseline:** Interpolate the regional PM2.5 field from all active official CAAQMS stations across the city using spatial inverse distance weighting.
2. **Step 2: Residual Anomaly Identification:** When low-cost IoT nodes or citizen observations at a location report values deviating significantly from the regional baseline (Residual > 50 ug/m3), a local spatial anomaly is declared.
3. **Step 3: Multi-Modal Corroboration:** The system tests for cross-signal validation:
   - Does a verified Gemini citizen report exist within a 1km radius and within a 90-minute window?
   - Does a VIIRS/MODIS thermal anomaly fall within a 1.5km upwind arc?
   - Do low-cost sensors along the downwind vector show corresponding temporal lag spikes?
4. **Step 4: Hotspot Declaration:** If at least **two independent observational modalities** corroborate the spatial residual, the system declares a `POTENTIAL_HIDDEN_HOTSPOT` and assigns a spatial boundary polygon.

---

## 12. Forecasting Strategy

### 12.1 Prediction Targets
- Primary: **PM2.5 concentration (ug/m3)** at t+1h, t+3h, and t+6h.
- Secondary: **Pollution Spike Probability (P(PM2.5 > 250 ug/m3))** representing the likelihood of crossing the statutory "Severe" threshold.

### 12.2 Model Selection: Gradient Boosted Trees
- **Chosen Architecture:** **LightGBM / XGBoost Regressor**.
- **Justification over Deep Learning:**
  - Deep architectures (LSTMs, GRUs, Temporal Fusion Transformers) require continuous, uncorrupted sequential data, are prone to overfitting on sparse spatial nodes, and require substantial GPU resources for training and deployment.
  - LightGBM natively handles missing sensor inputs (frequent in Indian public telemetry), executes in milliseconds on CPU-based Cloud Run instances, and explicitly quantifies feature contributions via tree SHAP values, providing the transparency demanded by public regulatory bodies.

### 12.3 Feature Matrix
1. **Autoregressive Lags:** PM2.5 at t-1, t-2, t-3, t-6, t-24 hours.
2. **Atmospheric Dispersion Factors:**
   - Planetary Boundary Layer Height (PBLH): Inversely correlates with surface pollutant concentration.
   - Wind Velocity Vector: Decomposed into zonal (u) and meridional (v) components.
   - Ventilation Index (VI = Wind Speed x PBLH): Primary physical indicator of atmospheric flushing capacity.
   - Relative Humidity and Temperature: Indicators of secondary aerosol formation and hygroscopic growth.
3. **Temporal Periodicity:** Sine and cosine transformations of `hour_of_day` (capturing morning and evening peak traffic cycles) and `day_of_week`.
4. **Spatial Land-Use Proximity:** Distance to nearest arterial freight corridor, distance to nearest designated industrial cluster.

---

## 13. Multimodal Citizen Intelligence

Citizen data is inherently noisy, variable in photographic quality, and vulnerable to accidental or intentional misreporting. VayuDrishti deploys **Gemini Multimodal** as an automated, intelligent filter.

```
                           GEMINI CITIZEN TRIAGE PIPELINE
+-------------------------+
| Citizen Photo & Audio   |
| + Device GPS + Time     |
+------------+------------+
             |
             v
+------------------------------------------------------------------------+
| GEMINI FLASH MULTIMODAL REASONING                                      |
|                                                                        |
| System Prompt:                                                         |
| "Analyze the image and audio for ambient air pollution in India.       |
| Return JSON strictly conforming to schema. Detect smoke plumes,        |
| open burning, construction dust, or industrial exhaust. Assess opacity |
| and reject non-pollution images."                                      |
+------------+-----------------------------------------------------------+
             |
             v
+------------------------------------------------------------------------+
| STRUCTURED JSON OUTPUT                                                 |
| {                                                                      |
|   "is_pollution_detected": true,                                       |
|   "primary_category": "biomass_burning",                               |
|   "optical_severity": "HIGH",                                          |
|   "visual_confidence": 0.92,                                           |
|   "detected_elements": ["black_smoke_plume", "open_flame", "waste"],   |
|   "audio_summary_en": "Citizen reports burning leaves near colony gate"|
| }                                                                      |
+------------+-----------------------------------------------------------+
             |
             +-- If is_pollution_detected == false ---> Reject & Notify User
             |
             +-- If is_pollution_detected == true  ---> Forward to Fusion Engine
```

### Anti-Abuse & Deduplication Safeguards
1. **Visual Perceptual Hashing (pHash):** Computes image perceptual fingerprints to immediately detect identical images uploaded repeatedly by single or colluding devices.
2. **Spatial-Temporal Clustering:** Multiple reports within 500 meters submitted within 60 minutes are merged into a single compound event cluster, aggregating citizen confirmations while preventing alert duplication.
3. **EXIF Metadata Validation:** Cross-checks photo creation timestamp and GPS tags against the client device submission metadata to prevent uploading historical internet imagery.

---

## 14. Multi-Source Evidence Fusion

No single data stream is treated as infallible:
- Low-cost sensors suffer from calibration drift and humidity sensitivity.
- Satellite passes occur only 1–2 times daily and are blocked by cloud cover.
- CAAQMS stations are too sparse.
- Citizen reports can be subjective.

VayuDrishti solves this through a **Multi-Source Evidence Fusion Matrix**, calculating a composite **Hotspot Confidence Score (C)** normalized from 0 to 100:

Composite Score C = min(100, Sum(w_k * S_k * gamma_k))

Where:
- S_k in [0, 1] represents the normalized evidence signal from modality k.
- w_k is the modality base weight (Sum w_k = 100).
- gamma_k is a dynamic cross-validation boost factor (1.0 to 1.3) triggered when physical signals corroborate each other.

### Modality Weight Allocation

| Modality (k) | Base Weight (w_k) | Signal Derivation (S_k) | Corroboration Trigger (gamma_k) |
| :--- | :---: | :--- | :--- |
| **Citizen Visual (Gemini)** | 25 | Gemini `visual_confidence` x severity weight. | Boosted by 1.25x if >= 2 independent citizen reports agree within 1 km. |
| **Low-Cost IoT Sensors** | 25 | Normalized Z-score of downwind micro-sensor readings (Z >= 3 -> 1.0). | Boosted by 1.2x if sensor sits directly within the downwind dispersion cone. |
| **Meteorological Alignment** | 20 | Dispersion stagnation score (low wind speed < 1.5 m/s + low PBLH < 300 m -> 1.0). | Boosted if wind vector directly links suspected source to affected sensor. |
| **Satellite Observation** | 15 | Sentinel-5P tropospheric NO2 anomaly or VIIRS thermal detection within area. | Boosted by 1.3x if active thermal fire pixel aligns with citizen fire report. |
| **Spatial / Land-Use Prior** | 15 | Proximity to known emission zone (industrial cluster, unpaved freight corridor, landfill). | Baseline static spatial prior. |

### Confidence Tiers & Operational Rules
- **Score 80–100 (HIGH CONFIDENCE — ACTION REQUIRED):** Verified multi-source event; triggers automated high-priority alert to ward flying squad and dispatches mitigation resources.
- **Score 50–79 (MODERATE CONFIDENCE — VERIFICATION QUEUE):** Plausible localized event with partial corroboration; queued for priority monitoring or civic re-verification.
- **Score < 50 (LOW CONFIDENCE / NOISE):** Insufficient corroboration; retained in analytics database as an unverified background observation; no emergency alerts generated.

---

## 15. Risk & Decision Support

### 15.1 Risk Scoring Formulation
Raw pollutant numbers do not equal human risk. An acute spike in an uninhabited industrial tract at 3:00 AM carries a different public health consequence than a moderate spike near a dense residential ward containing schools and hospitals at 8:00 AM.

Actionable Risk Score = Hazard (PM2.5 Severity) x Event Confidence x Vulnerability Factor

Where the **Vulnerability Factor** is computed dynamically from:
- Sensitive Receptor Proximity (within 1 km of schools, retirement facilities, hospitals).
- Population Density Index of the affected municipal ward.
- Diurnal Exposure Coefficient (elevated during school transit and morning/evening commute hours).

### 15.2 Statutory Decision Support Matrix (Aligned with India's GRAP)
VayuDrishti directly maps detected events to concrete municipal mitigation tasks:

| Detected Event Profile | Primary Cause | Environmental Context | Actionable Decision Support Directive | Responsible Agency |
| :--- | :--- | :--- | :--- | :--- |
| **PM2.5 Spike > 300 ug/m3 along unpaved corridor** | Construction / Fugitive Road Dust | Wind speed > 3 m/s, dry soil conditions. | Dispatch 2x Mobile Mist-Spraying Trucks; order immediate halting of mechanical excavation; enforce mandatory tarpaulin covering on freight transit. | Municipal Corporation (MCD/BBMP) Works Dept. |
| **Nocturnal Hotspot (C > 85) in Industrial Buffer** | Unauthorized Industrial Furnace Flaring | Atmospheric inversion, boundary layer < 200 m. | Dispatch Night Flying Squad to Industrial Estate Gate 4; inspect boiler fuel compliance; cross-examine continuous stack monitoring logs. | State Pollution Control Board (SPCB) Regional Office |
| **Clustered Citizen Reports of Leaf/Garbage Burning** | Municipal Solid Waste / Biomass Burning | Residential colony perimeter, low wind dispersion. | Alert Ward Sanitation Inspector; dispatch localized water tender; issue statutory spot-fine under Municipal Solid Waste bylaws. | Municipal Ward Health Officer |
| **Corridor Forecast: Severe Smog Spike in 3 Hours** | Freight Congestion + Stagnant Air | Evening rush hour, wind speed < 1 m/s. | Divert non-essential diesel transit to outer ring road; activate roadside mist cannons along bottleneck intersections. | City Traffic Police & Municipal Transport Dept. |

---

## 16. Interoperability & Multi-City Architecture

To avoid building a single-city prototype that cannot scale, VayuDrishti is designed from Day 0 as a **federated, interoperable environmental intelligence platform**.

```
                         FEDERATED MULTI-CITY ARCHITECTURE
+----------------------------------------------------------------------------------------+
|                        SHARED CORE (STATE / NATIONAL FEDERATION)                       |
|  - Standardized GeoJSON & Observation Data Contracts (OGC & SensorThings compliant)   |
|  - Global Model Weight Hub (Base tabular forecasting weights & Gemini prompt templates)|
|  - Regional Air-Shed Correlation Bus (Transboundary plume exchange between cities)    |
+-------------------^------------------------------------------------^-------------------+
                    |                                                |
         Federated Data Sync                              Federated Data Sync
                    |                                                |
+-------------------v------------------+         +-------------------v------------------+
| CITY NODE A: DELHI NCR               |         | CITY NODE B: BENGALURU               |
| - Local CAAQMS (DPCC/CPCB)           |         | - Local CAAQMS (KSPCB)               |
| - Local Low-Cost IoT Feeds           |         | - Local Low-Cost IoT Feeds           |
| - Delhi Municipal Ward Boundaries    |         | - BBMP Ward Boundaries               |
| - GRAP SOP Task Engine               |         | - Karnataka SPCB Action Templates    |
| - Localized Fine-Tuned Forecast Model|         | - Localized Fine-Tuned Forecast Model|
+--------------------------------------+         +--------------------------------------+
```

### Key Architectural Tenets for Multi-City Expansion
1. **Decoupled Data Contracts:** All spatial telemetry conforms to open, standardized schemas (GeoJSON FeatureCollections with strict `SensorObservation` interfaces). A new city onboarded simply maps its CAAQMS and municipal boundary files to this schema.
2. **Domain Adaptation for ML Forecasting:** The core LightGBM gradient-boosting tree structure is trained on baseline atmospheric dispersion physics, then fine-tuned locally for each city's unique topography:
   - *Indo-Gangetic Plain Node (Delhi):* High winter stagnation, massive seasonal biomass influence, low wind speeds.
   - *Deccan Plateau Node (Bengaluru):* Elevated terrain (920m ASL), rapid convective dispersion, localized valley-ridge microclimates.
3. **Regional Air-Shed Coordination:** Air pollution does not obey municipal borders. When an upwind district detects massive emissions, VayuDrishti's federation bus propagates an incoming transboundary plume warning to the downwind city node with estimated time of arrival.
4. **Onboarding a New City in 3 Steps:**
   - *Step 1:* Ingest municipal boundary GeoJSON and CAAQMS station coordinates.
   - *Step 2:* Connect Open-Meteo weather grid bounding box for the region.
   - *Step 3:* Deploy localized Cloud Run worker initialized with base model weights.

---

## 17. Pilot Geography

To maximize demonstration credibility while maintaining technical rigor during the hackathon, VayuDrishti selects a focused, high-impact pilot scope.

### Selected Primary Pilot: Delhi NCR (Focus Corridor: South/East Delhi & Noida-Gurugram Industrial Transit)
- **Why Delhi NCR?**
  - **Highest Ground-Truth Density:** Contains India's densest CAAQMS network (~40 stations operated by CPCB/DPCC), providing the richest empirical validation data for training models and evaluating kriging residuals.
  - **Maximum Problem Severity:** World-renowned epicenter of severe winter air pollution, where hidden micro-hotspots (waste burning, unpaved roads, Anand Vihar transit hub, Okhla/Mayapuri industrial clusters) create life-threatening public health emergencies.
  - **Mature Regulatory Framework:** Home to the statutory Graded Response Action Plan (GRAP), enabling direct mapping of AI alerts to official public policy actions.

### Secondary Interoperability Pilot: Bengaluru (Peenya Industrial Area & Whitefield Corridor)
- **Why Bengaluru as Secondary?**
  - Demonstrates that VayuDrishti is **not a single-city Delhi app**.
  - Distinct topographic, climatic, and emission profile: Peninsular plateau, moderate temperatures, rapid weather changes, pollution dominated by construction dust and vehicular bottlenecks rather than agricultural burning.
  - Validates cross-city model portability across completely different Indian environmental regimes.

---

## 18. Differentiation Strategy

Hackathon environmental projects routinely stumble into repetitive clichés. VayuDrishti explicitly differentiates across 5 architectural mechanisms:

| Common Hackathon Cliché | The Real Technical Pitfall | VayuDrishti's Differentiating Innovation | Concrete Mechanism |
| :--- | :--- | :--- | :--- |
| **Generic AQI Dashboard** | Displays existing CAAQMS data on a standard map with colored pins. Adds zero analytical value beyond existing CPCB websites. | **Hidden Hotspot Discovery Engine** | Spatial kriging residual scoring identifies acute micro-pollution where no permanent government monitors exist. |
| **Simple Image Classifier** | Uses basic ResNet/MobileNet to output "Pollution: 84%". Blind to context, easily fooled by cloud cover or dust. | **Multimodal Reasoning with Gemini Flash** | Gemini analyzes semantic scene context (flames, exhaust stacks, unpaved roads), estimates optical opacity, and transcribes citizen voice in native Indian languages into structured JSON. |
| **Black-Box Deep Learning Forecast** | Trains an opaque LSTM claiming "99% AQI accuracy". Fails under real-world weather shifts; provides zero explainability to officials. | **Physics-Guided Gradient Boosted Trees with Quantile Intervals** | LightGBM incorporates real meteorological dispersion physics (PBLH x wind); provides 80% confidence prediction intervals (P10 - P90) and SHAP feature attributions. |
| **Single-Signal Alerting** | Alerts authorities based solely on a single citizen photo or a single sensor spike, triggering massive false alarms. | **Multi-Source Evidence Fusion Matrix** | Synthesizes citizen evidence, downwind IoT nodes, weather vectors, and satellite thermal data into an auditable 0–100 Confidence Index. |
| **Passive "What Happened" Reporting** | Shows historical charts. Leaves authorities guessing what operational steps to take. | **Statutory Decision Support & GRAP Directives** | Automatically matches incident severity and land-use context to official statutory directives (anti-smog gun dispatch, construction halts, flying squad inspections). |

---

## 19. UI/UX Design Rules & Human-Centered Guidelines

### PERMANENT PROJECT UI/UX MANDATE
Every user interface built for VayuDrishti must reflect the restraint, clarity, and utilitarian elegance of a **mission-critical civic and environmental operating platform**. It must feel designed by an experienced human product designer for real municipal officers and citizens.

```
+----------------------------------------------------------------------------------------+
|                                VISUAL DESIGN LANGUAGE                                  |
+----------------------------------------------------------------------------------------+
| THEME: Light, Calm, Professional, High Information Clarity                             |
| BACKGROUND: Crisp porcelain white (#FFFFFF) with warm slate canvas (#F8FAFC)          |
| TYPOGRAPHY: Inter / Plus Jakarta Sans — clean geometric sans-serif, strict hierarchy  |
| PALETTE:                                                                               |
|  - Primary Brand / Chrome: Deep Slate Navy (#0F172A)                                   |
|  - Air Quality Good / Moderate: Subtle Sage Green (#16A34A) / Muted Amber (#D97706)   |
|  - Air Quality Poor / Severe: Terracotta Rust (#DC2626) / Deep Plum Maroon (#7F1D1D)   |
|  - Borders & Dividers: Muted Light Slate (#E2E8F0)                                     |
+----------------------------------------------------------------------------------------+
| STRICTLY FORBIDDEN:                                                                    |
|  x Neon glowing borders, cyber-cyan, or hyper-saturated gradients                      |
|  x Dark-mode "hacker/cyberpunk" aesthetics                                             |
|  x Excessive glassmorphism, blur effects, or translucent glowing panels                |
|  x Decorative floating 3D spheres, animated particles, or rotating AI icons            |
|  x Cluttered, illegible chart graveyards lacking actionable hierarchy                  |
+----------------------------------------------------------------------------------------+
```

### Core Interface Layout (Authority Console)
1. **Primary Canvas (65% width):** Interactive high-contrast map canvas displaying CAAQMS stations, IoT nodes, satellite overlays, and computed hotspot bounding polygons with clear color encoding.
2. **Right-Hand Incident Drawer (35% width):** Collapsible operational panel displaying:
   - Active priority incidents sorted by Confidence Index.
   - Expandable evidentiary audit trail: Gemini-verified citizen photos, downwind sensor charts, wind vector indicators.
   - Plain-language incident brief generated by Gemini.
   - Direct action buttons: *"Acknowledge & Dispatch Squad"*, *"Deploy Water Sprinkler"*, *"Close Resolution"*.

---

## 20. Security, Privacy & Public Trust

1. **Citizen Privacy by Design:**
   - Citizen telephone numbers and personal identity hashes are strictly decoupled from public incident reports.
   - Client-side or edge sanitization strips EXIF metadata (device serial number, personal metadata) before storing imagery in public-facing storage.
   - Public view displays randomized coordinate fuzzing (+- 150 meters) for citizen submissions to protect residential privacy.
2. **Role-Based Access Control (RBAC):**
   - *Public Role:* Access to real-time interpolated map, localized 3-hr health advisories, and report submission interface.
   - *Authority Role (Secured via Firebase Authentication):* Full access to unmasked coordinates, flying-squad dispatch controls, statutory audit logs, and internal cross-city federation channels.
3. **API & Cloud Infrastructure Security:**
   - Cloud Run endpoints protected via rate-limiting and Google Cloud Armor WAF rules.
   - API keys (Gemini API, Google Maps Platform) stored strictly in GCP Secret Manager and backend environment variables; never exposed to frontend client bundles.

---

## 21. Success Metrics

All quantitative targets reflect realistic, empirically defensible benchmarks for a civic-tech deployment:

| Dimension | Metric | Provisional Target | Validation Method |
| :--- | :--- | :--- | :--- |
| **Hotspot Detection** | Precision of Flagged Hidden Hotspots | >= 80% *[PROVISIONAL TARGET]* | Post-inspection validation by municipal flying squad logs. |
| **Hotspot Detection** | Detection Latency | < 15 minutes from event trigger | Temporal delta from sensor spike/citizen upload to alert. |
| **Forecasting** | PM2.5 3-Hour Forecast MAE | < 28 ug/m3 *[PROVISIONAL TARGET]* | Evaluated against hold-out CAAQMS ground truth. |
| **Forecasting** | Spike Event Recall (> 250 ug/m3) | >= 75% *[PROVISIONAL TARGET]* | Percentage of actual severe spikes correctly anticipated. |
| **Multimodal Triage** | Citizen Image Verification Accuracy | >= 88% *[PROVISIONAL TARGET]* | Benchmarked against 100 expert-labeled civic images. |
| **Multimodal Triage** | End-to-End Processing Latency | < 3.5 seconds per report | Full round-trip Gemini Flash image + audio inference. |
| **System Reliability** | Cloud Run API P95 Response Time | < 800 milliseconds | Load-tested under concurrent client queries. |
| **Decision Support** | Authority Action Usability Score | >= 4.2 / 5.0 *[PROVISIONAL TARGET]* | Simulated usability review with public sector workflow criteria. |

---

## 22. Risks & Mitigations

```
                                 RISK MANAGEMENT MATRIX
+--------------------------------------+--------------------------------------+
| IDENTIFIED TECHNICAL / DOMAIN RISK   | CONCRETE ENGINEERING MITIGATION      |
+--------------------------------------+--------------------------------------+
| 1. Sparse or Malfunctioning CAAQMS   | Dual-layer fallback: interpolate     |
|    Data feeds drop out or exhibit    | missing CAAQMS stations using        |
|    prolonged maintenance freezes.    | satellite AOD + historical diurnal   |
|                                      | matrix; flag low data confidence.    |
+--------------------------------------+--------------------------------------+
| 2. Satellite Cloud Cover Blindness   | Automated modality fallback: When    |
|    Monsoon or heavy winter fog       | Sentinel-5P/MODIS pixels are masked, |
|    blocks optical satellite scans.   | dynamic weight shifts to ground IoT  |
|                                      | sensors and citizen visual reports.  |
+--------------------------------------+--------------------------------------+
| 3. Citizen Report Spam & Trolling    | Gemini visual rejection filter;      |
|    Users upload memes, indoor photos,| perceptual image hashing (pHash);    |
|    or fake reports to game system.   | rate-limiting per device/IP.         |
+--------------------------------------+--------------------------------------+
| 4. Low-Cost Sensor Calibration Drift | Dynamic baseline recalibration:      |
|    Cheap PM sensors drift under high | cross-reference low-cost nodes with  |
|    humidity (>80% RH).               | nearest CAAQMS using humidity-       |
|                                      | dependent hygroscopic growth curves. |
+--------------------------------------+--------------------------------------+
| 5. Alert Fatigue for Authorities     | Strict confidence thresholding: only │
|    Too many low-severity alerts      | incidents with Confidence Score >= 80|
|    flood municipal flying squads.    | trigger emergency dispatches.        |
+--------------------------------------+--------------------------------------+
```

---

## 23. 3–5 Minute Demo Strategy

The hackathon demonstration follows a tightly scripted, cohesive incident narrative that proves working, end-to-end multi-source intelligence rather than clicking through static charts:

```
                              3-TO-5 MINUTE DEMO STORYLINE
+----------------------------------------------------------------------------------------+
| MINUTE 0:00 - 0:45: THE PROBLEM & MONITORING BLINDSPOT                                 |
| * Present live map of Delhi NCR: show 40 official CAAQMS pins showing "Moderate" air.  |
| * Highlight the 35 km2 unmonitored industrial corridor between Mayapuri and Naraina.   |
+----------------------------------------------------------------------------------------+
| MINUTE 0:45 - 1:45: CITIZEN EVIDENCE & GEMINI MULTIMODAL TRIAGE                        |
| * Live demo: Citizen submits a photo of heavy illegal scrap burning + Hindi voice memo.|
| * Show Gemini Flash processing the payload in real-time (sub-2s):                      |
|   - Validates smoke plume; estimates High optical density; transcribes Hindi audio.    |
|   - Rejects a test invalid photo (e.g., clear desk) to prove anti-spam guardrail.      |
+----------------------------------------------------------------------------------------+
| MINUTE 1:45 - 2:45: MULTI-SOURCE EVIDENCE FUSION & HIDDEN HOTSPOT FLAGGED              |
| * System correlates the report: downwind IoT sensor spikes; weather shows stagnant air.|
| * Kriging residual calculation isolates a +180 ug/m3 anomaly vs. regional CAAQMS.     |
| * Live Map instantly transitions the area into an amber/red "HIDDEN HOTSPOT" polygon. |
| * Inspect the Evidence Score: 91/100, displaying all corroborating signals.            |
+----------------------------------------------------------------------------------------+
| MINUTE 2:45 - 3:45: CORRIDOR SPIKE FORECAST & DECISION SUPPORT                         |
| * Open Forecaster: LightGBM projects plume spreading along the corridor in 3 hours.   |
| * Switch to Authority Console: Ward Officer receives high-priority incident card.      |
| * Show Gemini-synthesized GRAP dispatch recommendation (anti-smog truck + inspection). |
| * Officer clicks "Acknowledge & Dispatch" -> status synchronizes in real-time.         |
+----------------------------------------------------------------------------------------+
| MINUTE 3:45 - 4:30: INTEROPERABILITY & CONCLUSION                                      |
| * Toggle city selector from Delhi to Bengaluru (Peenya Industrial Area).               |
| * Show same standardized data contract and UI operating seamlessly on new data.       |
| * Final slide/view: "VayuDrishti turns passive AQI monitoring into active enforcement."|
+----------------------------------------------------------------------------------------+
```

---

## 24. Feature Prioritization

To guarantee that the hackathon prototype is fully functional, robust, and deployable within the allotted build time, features are strictly triaged:

### MUST HAVE (Core Hackathon Prototype — Non-Negotiable)
1. Interactive Environmental Map (Google Maps / Mapbox) with CAAQMS, low-cost sensor, and citizen report layers.
2. Multimodal Citizen Evidence Analyzer using Gemini Flash (photo verification, optical density classification, multilingual audio transcription, structured JSON output).
3. Spatial Anomaly & Hidden Hotspot Detection Engine (kriging baseline vs. localized micro-anomalies).
4. Multi-Source Evidence Fusion Matrix (combining citizen, sensor, weather, and satellite signals into a 0–100 Confidence Index).
5. Short-Term Corridor Forecasting Engine (LightGBM/XGBoost tabular model predicting PM2.5 at t+1, t+3, t+6 hours).
6. Municipal Authority Console with GRAP-aligned decision support directives and dispatch workflow.
7. Multi-City Switcher (Delhi NCR and Bengaluru) proving federated schema interoperability.

### SHOULD HAVE (Post-MVP Enhancements — Time Permitting)
1. Automated citizen push notifications via Firebase Cloud Messaging for localized downwind health alerts.
2. In-depth SHAP feature attribution waterfall plot on the authority console explaining exact meteorological drivers of forecast spikes.
3. Historical intervention efficacy tracker (calculating post-dispatch PM2.5 decline).

### FUTURE (Long-Term Production Roadmap)
1. Automated video stream ingestion from municipal traffic cameras and industrial stack CCTV.
2. Integration with autonomous municipal drone surveillance flights.
3. Edge-AI firmware deployment on solar-powered low-cost IoT sensor microcontrollers.
4. Carbon credit and statutory penalty billing integration for municipal finance departments.

---

## 25. Conceptual System Architecture

```
                                  VAYUDRISHTI SYSTEM ARCHITECTURE
                                                                                                  
  CITIZEN CLIENT (PWA)               IOT SENSOR NETWORKS             SATELLITE & WEATHER APIS      
  - Geotagged Photo Upload            - Low-Cost PM2.5 Nodes          - Sentinel-5P NO2 (GEE)      
  - Multilingual Voice Note           - CAAQMS Stations (CPCB/OpenAQ) - Open-Meteo Weather API     
  - Real-Time Exposure Alerts         - Continuous telemetry          - NASA FIRMS Active Fires    
           |                                   |                                  |                
           | HTTPS / FormData                  | MQTT / REST Poller               | Scheduled Cron 
           v                                   v                                  v                
+-------------------------------------------------------------------------------------------------+
|                           API GATEWAY & INGESTION (Cloud Run / FastAPI)                         |
|  - Request authentication & rate limiting                                                       |
|  - Schema validation & coordinate normalization                                                 |
|  - EXIF validation & perceptual image hashing (pHash)                                           |
+----------------+-----------------------------+----------------------------------+---------------+
                 |                             |                                  |                
                 v                             v                                  |                
+----------------------------------+ +----------------------------------+         |                
|   GEMINI FLASH MULTIMODAL API    | |  GEO-SPATIAL INTERPOLATION &     |         |                
|   - Visual smoke plume detection | |  SPATIAL RESIDUAL ENGINE         |         |                
|   - Optical density ranking      | |  - CAAQMS Ordinary Kriging       |         |                
|   - Voice-to-text transcription  | |  - DBSCAN Citizen Clustering     |         |                
|   - Structured JSON generation   | |  - Spatial Anomaly Calculation   |         |                
+----------------+-----------------+ +-----------------+----------------+         |                
                 |                                     |                          |                
                 +-----------------------+-------------+                          |                
                                         |                                        |                
                                         v                                        v                
+-------------------------------------------------------------------------------------------------+
|                       MULTI-SOURCE EVIDENCE FUSION & CONFIDENCE ENGINE                          |
|  - Cross-corroborates visual confidence, sensor Z-scores, wind vectors, and satellite rasters   |
|  - Generates Composite Hotspot Confidence Score (0 to 100)                                      |
|  - Declares verified POTENTIAL_HIDDEN_HOTSPOT events                                            |
+----------------------------------------+--------------------------------------------------------+
                                         |                                                         
                                         +----------------------------------------+                
                                         v                                        v                
+--------------------------------------------------+  +------------------------------------------+ 
|       SHORT-TERM CORRIDOR FORECASTER             |  |       STATUTORY DECISION SUPPORT         | 
|  - LightGBM Gradient Boosted Regressor           |  |  - CPCB/GRAP SOP Rule Matching Engine    | 
|  - Quantile loss forecasts (1h, 3h, 6h PM2.5)    |  |  - Contextual dispatch task generation   | 
|  - Boundary layer & wind dispersion modeling     |  |  - Gemini natural-language brief synth   | 
+------------------------+-------------------------+  +-------------------+----------------------+ 
                         |                                                |                        
                         +-----------------------+------------------------+                        
                                                 |                                                 
                                                 v                                                 
+-------------------------------------------------------------------------------------------------+
|                           STORAGE & REAL-TIME SYNCHRONIZATION LAYER                             |
|  - Firebase Firestore: Active hot incidents, dispatch statuses, live reactive UI subscriptions  |
|  - Firebase Storage: Verified citizen evidence photos & audio blobs                             |
|  - Google BigQuery: Historical spatial-temporal repository & cross-city federated analytics     |
+------------------------------------------------+------------------------------------------------+
                                                 |                                                 
                                                 v                                                 
+-------------------------------------------------------------------------------------------------+
|                               OPERATIONAL INTERFACES & CONSOLES                                 |
|                                                                                                 |
|   CITIZEN PWA INTERFACE (React / Vite)            MUNICIPAL & SPCB CONSOLE (React / Tailwind)   |
|   - Hyper-local air quality map                   - Real-time priority incident dispatch queue  |
|   - One-touch evidence reporting                  - Evidentiary audit trail & Gemini briefs     |
|   - 3-hour neighborhood spike alerts              - Anti-smog / flying squad task tracking     |
+-------------------------------------------------------------------------------------------------+
```

---

## 26. Future Expansion Roadmap

1. **Edge-AI Sensor Integration:** Deployment of lightweight quantized models directly on solar-powered ESP32/microcontroller sensor packages with localized optical particle counters.
2. **Automated Drone Surveillance:** Integration with municipal environmental inspection drones; automated flight plan dispatch to verified hidden hotspots for aerial thermal and gas sampling.
3. **Hyper-Local Health Impact Modeling:** Integrating synthetic cohort epidemiological exposure curves to quantify premature mortality and asthma exacerbation risks avoided per municipal intervention.
4. **National Clean Air Programme (NCAP) Reporting Integration:** Automated compilation of ward-level statutory clean air action compliance reports submitted directly to state environment ministries.

---

## 27. FINAL SCOPE LOCK

This section forms the **immutable boundary contract** for all future development phases. No features, tools, or dependencies outside this locked boundary may be added during subsequent phases.

### WHAT WE ARE BUILDING
- An end-to-end working prototype of **VayuDrishti** fusing CAAQMS feeds, low-cost sensor data, satellite observations, and crowdsourced citizen evidence.
- A functional multimodal intake pipeline leveraging **Google Gemini Flash** for citizen image verification, optical severity estimation, multilingual voice note transcription, and structured JSON generation.
- A **Spatial Anomaly & Hidden Hotspot Detection Engine** that computes kriging residuals to flag micro-hotspots unobserved by official CAAQMS monitors.
- A **Multi-Source Evidence Fusion Matrix** calculating an explainable 0–100 Confidence Index.
- A **Short-Term Corridor Forecaster** using a gradient-boosted tabular regressor (LightGBM) to forecast PM2.5 spikes at 1h, 3h, and 6h horizons.
- A **Municipal Authority Console** featuring a clean, human-designed light interface with GRAP-aligned decision support directives and dispatch tracking.
- A **Citizen Reporting Web Interface** optimized for mobile browsers with geotagged photo/voice capture.
- A **Federated Multi-City Demonstration** seamlessly toggling between Delhi NCR (primary) and Bengaluru (secondary).

### WHAT WE ARE NOT BUILDING
- NOT building a generic, passive AQI dashboard that merely re-plots CPCB monitor data.
- NOT building a generic conversational AI chatbot or floating "AI Assistant".
- NOT building a dark-mode, neon-lit, cyberpunk or glassmorphism-heavy UI.
- NOT training complex deep-learning neural networks (Transformers, 3D CNNs) where tabular models are faster and superior.
- NOT implementing custom native Android/iOS mobile applications (a responsive mobile-first PWA satisfies all mobile requirements).
- NOT building real hardware sensors or drone robotics during the hackathon.
- NOT fabricating benchmark accuracies, fake sensor numbers, or unsupported claims.

### LOCKED PILOT GEOGRAPHY
- **Primary:** Delhi NCR (Focus: South/East Delhi & Gurugram-Noida Industrial Freight Corridor).
- **Secondary (Interoperability Proof):** Bengaluru (Peenya Industrial Area & Whitefield Corridor).

### LOCKED GOOGLE TECHNOLOGIES
1. **Gemini API (Gemini Flash)** via official `google-genai` SDK.
2. **Google Maps Platform** (Maps JavaScript API / Geocoding).
3. **Google Earth Engine (GEE)** (Sentinel-5P NO2 / FIRMS active fire datasets).
4. **Cloud Run** (Containerized FastAPI backend hosting the fusion engine and ML services).
5. **Firebase (Firestore & Storage)** (Real-time operational database and secure media store).
6. **BigQuery** (Analytical warehouse for spatial-temporal data).

### LOCKED AI/ML COMPONENTS
1. **Multimodal Perception:** Gemini Flash with structured schema extraction.
2. **Predictive Modeling:** LightGBM / XGBoost Tabular Regressor with Quantile Loss.
3. **Geospatial Analytics:** Spatial Kriging / IDW Interpolation + DBSCAN Clustering.
4. **Decision Support:** Statutory GRAP Rule Matrix + Gemini Operational Brief Synthesis.

### LOCKED DATA CATEGORIES
1. **Air Quality:** CPCB CAAQMS (via OpenAQ candidate API) + Low-Cost IoT nodes.
2. **Meteorology:** Open-Meteo Hourly Historical & Forecast API.
3. **Satellite:** Sentinel-5P TROPOMI NO2 & NASA FIRMS Thermal Anomalies (via GEE).
4. **Spatial Infrastructure:** OpenStreetMap road networks, industrial polygons, and sensitive POIs.
5. **Citizen Evidence:** Geotagged images, audio notes, and categorical reports.

---
**PHASE 0 ARCHITECTURAL SIGN-OFF:** COMPLETE & PERMANENTLY LOCKED  
**NEXT PHASE:** PHASE 1 — FOUNDATIONAL SETUP & DATA ACQUISITION PIPELINE
