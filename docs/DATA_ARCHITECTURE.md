# VayuDrishti Data Architecture & Environment Contract
## Phase 1C Specification: Data Definitions, Schemas & Lifecycle
**Status:** PHASE 1C — DATA ARCHITECTURE & ENVIRONMENT CONTRACT FROZEN  
**Target API Version:** v1  
**Project:** VayuDrishti — Clean Air & Climate Resilience  
**Local Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  

---

## 1. Data Architecture Overview

VayuDrishti is an environmental decision-support system operating at the intersection of ground-level sensor telemetry, satellite Earth observation, numerical weather forecasts, and crowdsourced citizen intelligence. 

Because each data stream originates from disparate external authorities with distinct sampling rates, geographic coordinates, units, and latency characteristics, the primary objective of this data architecture is to enforce **canonical data boundaries** and **rigorous normalization contracts** before any data touches predictive models or decision engines.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              VAYUDRISHTI DATA PIPELINE FLOW                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ [External Sources] (CPCB, Open-Meteo, NASA FIRMS, Citizen Reports)                     │
│         │                                                                              │
│         ▼                                                                              │
│ [Source Adapters] (Ingestion & Schema Translation)                                     │
│         │                                                                              │
│         ▼                                                                              │
│ [Data Validation & Normalization] (Coordinate checks, SI units, Quality flags)         │
│         │                                                                              │
│         ▼                                                                              │
│ [Canonical Data Schemas] (Typed Pydantic & TypeScript Contracts)                       │
│         │                                                                              │
│         ▼                                                                              │
│ [Feature Store & Analytics] (Spatial indexing, Lags, Meteorological ventilation)       │
│         │                                                                              │
│         ▼                                                                              │
│ [AI / ML & Decision Engines] (Hotspot discovery, LightGBM forecasting, GRAP dispatch)  │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Canonical Data Domains

The VayuDrishti architecture defines **8 canonical data domains**. Each domain possesses strict identifier, temporal, spatial, and validation rules:

### Domain A: Air Quality Observations
- **Purpose:** Ingestion of continuous point-source ambient pollutant concentrations from regulatory CAAQMS and low-cost sensor nodes.
- **Canonical ID:** `aq_obs_{station_id}_{timestamp_utc}`
- **Timestamp Standard:** ISO 8601 UTC representation (`YYYY-MM-DDTHH:MM:SSZ`).
- **Location Standard:** WGS 84 point coordinates (`latitude`, `longitude`).
- **Essential Fields:** `station_id`, `timestamp`, `location`, `pollutant`, `value`, `unit`, `source`, `quality_flag`.
- **Optional Fields:** `sampling_height_m`, `humidity_correction_applied`, `raw_voltage`.
- **Source Attribution:** `CAAQMS_CPCB`, `CAAQMS_DPCC`, `CAAQMS_KSPCB`, `IOT_COMMUNITY`.
- **Primary Units:** $\mu\text{g/m}^3$ for particulate matter and aerosols; $\text{mg/m}^3$ for CO.
- **Validation Rules:** $0.0 \le \text{value} \le 1500.0\,\mu\text{g/m}^3$ for PM2.5/PM10; coordinates within city bounding box.
- **Freshness Expectations:** 15 to 60 minutes.

### Domain B: Meteorological Observations & Forecasts
- **Purpose:** Atmospheric drivers governing pollutant dispersion, transport, and stagnation.
- **Canonical ID:** `wx_obs_{grid_or_station_id}_{timestamp_utc}`
- **Timestamp Standard:** ISO 8601 UTC.
- **Location Standard:** WGS 84 point or grid centroid.
- **Essential Fields:** `timestamp`, `location`, `temperature_c`, `relative_humidity_pct`, `wind_speed_ms`, `wind_direction_deg`, `surface_pressure_hpa`, `source`.
- **Optional Fields:** `planetary_boundary_layer_height_m`, `precipitation_mm`, `ventilation_index_m2s`.
- **Source Attribution:** `OPEN_METEO_HOURLY`, `IMD_AWS`, `ERA5_REANALYSIS`.
- **Validation Rules:** Temperature $-10^\circ\text{C} \le T \le 55^\circ\text{C}$; Humidity $0\% \le RH \le 100\%$; Wind direction $0^\circ \le \theta \le 360^\circ$; Wind speed $0 \le V \le 50\,\text{m/s}$.
- **Freshness Expectations:** Hourly historical and 24-hour forward projection.

### Domain C: Geospatial Context & Land Use
- **Purpose:** Spatial priors indicating industrial zones, freight corridors, sensitive receptors (schools, hospitals), and municipal boundaries.
- **Canonical ID:** `geo_{feature_type}_{osm_or_ward_id}`
- **Timestamp Standard:** Static with version date (`valid_from`, `valid_to`).
- **Location Standard:** WGS 84 GeoJSON geometry (Point, LineString, Polygon, MultiPolygon).
- **Essential Fields:** `feature_id`, `feature_type`, `geometry`, `name`, `city_code`.
- **Optional Fields:** `traffic_density_rank`, `sensitive_receptor_category`, `population_density_sqkm`.
- **Source Attribution:** `OPENSTREETMAP_OVERPASS`, `MUNICIPAL_WARD_SURVEY`.
- **Validation Rules:** Valid simple polygons without self-intersections; coordinates within state boundaries.
- **Freshness Expectations:** Updated quarterly or annually.

### Domain D: Satellite / Earth Observation Signals
- **Purpose:** Macro-level atmospheric column data and thermal anomaly points providing supporting evidence.
- **Canonical ID:** `sat_{satellite}_{product}_{timestamp_utc}_{pixel_or_event_id}`
- **Timestamp Standard:** ISO 8601 UTC satellite overpass time.
- **Location Standard:** WGS 84 point (thermal anomaly) or bounding box / GeoTIFF tile.
- **Essential Fields:** `satellite_name`, `product_id`, `acquisition_time`, `geometry`, `signal_type`, `value`, `unit`, `confidence_indicator`.
- **Optional Fields:** `brightness_temperature_k`, `fire_radiative_power_mw`, `cloud_fraction`.
- **Source Attribution:** `SENTINEL_5P_TROPOMI`, `NASA_FIRMS_VIIRS`, `NASA_FIRMS_MODIS`.
- **Validation Rules:** Cloud fraction $\le 0.4$ for valid tropospheric NO2 column values.
- **Freshness Expectations:** 12 to 24 hours (governed by orbital revisit schedules).

### Domain E: Citizen Evidence
- **Purpose:** Crowdsourced visual, auditory, and descriptive ground truth regarding localized, episodic pollution events.
- **Canonical ID:** `ev_{uuid4_hex}` (e.g. `ev_a1b2c3d4e5f67890a1b2c3d4e5f67890`)
- **Timestamp Standard:** ISO 8601 UTC submission time (`received_at`).
- **Location Standard:** WGS 84 client GPS coordinates with accuracy radius (`accuracy_m`), or manual corridor preset.
- **Essential Fields:** `evidence_id`, `received_at`, `consent`, `category`, `media_files`, `status`.
- **Optional Fields:** `description`, `location`, `client_metadata`.
- **Storage Paths:**
  - Raw Media: `data/raw/citizen_evidence/<evidence_id>/`
  - Manifest JSON: `data/processed/citizen_evidence/manifests/<evidence_id>.json`
- **Source Attribution:** `CITIZEN_PWA_SUBMISSION`.
- **Validation Rules:**
  - Mandatory voluntary consent checkbox.
  - At least one modality present (photo, voice, or text).
  - Photo payload $\le 10\,\text{MB}$ (`image/jpeg`, `image/png`, `image/webp`).
  - Voice memo duration $\le 60\,\text{s}$, size $\le 10\,\text{MB}$ (`audio/webm`, `audio/ogg`, `audio/wav`, `audio/mp4`, `audio/mpeg`, `audio/x-m4a`).
  - Text remarks $\le 1000\,\text{characters}$.
  - Location coordinates bounded WGS84 (Lat: $-90.0$ to $+90.0$, Lon: $-180.0$ to $+180.0$, `accuracy_m` $\ge 0.0$).
- **Freshness Expectations:** Real-time event-driven intake.

### Domain F: Pollution Events & Hotspots
- **Purpose:** Computed spatial-temporal clusters where air pollution significantly deviates from the regional baseline.
- **Canonical ID:** `hotspot_{city_code}_{date}_{sequence_id}`
- **Timestamp Standard:** ISO 8601 UTC detection timestamp.
- **Location Standard:** Centroid coordinate + estimated impact polygon / radius.
- **Essential Fields:** `hotspot_id`, `centroid`, `detected_at`, `severity_tier`, `confidence_score`, `contributing_evidence_ids`, `status`.
- **Optional Fields:** `estimated_radius_m`, `primary_suspected_source`, `dispersion_corridor_polygon`.
- **Source Attribution:** `VAYUDRISHTI_FUSION_ENGINE`.
- **Validation Rules:** Confidence score bounded strictly $0.0 \le C \le 100.0$.
- **Freshness Expectations:** Recomputed every 15 minutes.

### Domain G: Forecast Results
- **Purpose:** Forward-looking concentration projections along critical economic transport and industrial corridors.
- **Canonical ID:** `fc_{location_id}_{created_at}_{horizon}`
- **Timestamp Standard:** Forecast generation timestamp + target validity timestamp.
- **Location Standard:** Corridor point or line segment centroid.
- **Essential Fields:** `forecast_id`, `target_location`, `pollutant`, `generated_at`, `target_time`, `horizon_hours`, `predicted_value`, `unit`, `model_version`.
- **Optional Fields:** `lower_bound_p10`, `upper_bound_p90`, `feature_importance_snapshot`.
- **Source Attribution:** `LIGHTGBM_CORRIDOR_V1`.
- **Validation Rules:** Target time must be strictly greater than generated time; predicted value $\ge 0.0$.
- **Freshness Expectations:** Recomputed hourly.

### Domain H: Risk Assessment & Decision Support Directives
- **Purpose:** Derived public health exposure consequence mapped to statutory mitigation actions.
- **Canonical ID:** `risk_{hotspot_id}_{timestamp_utc}`
- **Timestamp Standard:** ISO 8601 UTC.
- **Essential Fields:** `risk_id`, `linked_hotspot_id`, `risk_level`, `confidence`, `statutory_grap_stage`, `recommended_actions`, `status`.
- **Optional Fields:** `estimated_population_exposed`, `sensitive_receptors_count`.
- **Source Attribution:** `VAYUDRISHTI_DECISION_ENGINE`.
- **Validation Rules:** Mapped to statutory stages: `GRAP-I`, `GRAP-II`, `GRAP-III`, `GRAP-IV`.
- **Freshness Expectations:** Generated upon hotspot confirmation.

---

## 3. Canonical Schema Design (Specification)

Below are the canonical Pydantic/JSON schemas governing internal pipelines:

### 3.1 `EnvironmentalObservation`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "EnvironmentalObservation",
  "type": "object",
  "properties": {
    "observation_id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "location": {
      "type": "object",
      "properties": {
        "latitude": { "type": "number", "minimum": -90.0, "maximum": 90.0 },
        "longitude": { "type": "number", "minimum": -180.0, "maximum": 180.0 },
        "address": { "type": ["string", "null"] }
      },
      "required": ["latitude", "longitude"]
    },
    "pollutant": { "type": "string", "enum": ["PM2.5", "PM10", "NO2", "SO2", "CO", "O3", "AQI"] },
    "value": { "type": "number", "minimum": 0.0 },
    "unit": { "type": "string", "enum": ["µg/m³", "mg/m³", "AQI_INDEX", "ppm"] },
    "source": { "type": "string" },
    "station_id": { "type": ["string", "null"] },
    "quality_flag": { "type": "string", "enum": ["VALID", "SUSPECT", "INVALID", "CALIBRATING"] }
  },
  "required": ["observation_id", "timestamp", "location", "pollutant", "value", "unit", "source", "quality_flag"]
}
```

### 3.2 `WeatherObservation`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "WeatherObservation",
  "type": "object",
  "properties": {
    "weather_id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "location": {
      "type": "object",
      "properties": {
        "latitude": { "type": "number", "minimum": -90.0, "maximum": 90.0 },
        "longitude": { "type": "number", "minimum": -180.0, "maximum": 180.0 }
      },
      "required": ["latitude", "longitude"]
    },
    "temperature_c": { "type": "number" },
    "relative_humidity_pct": { "type": "number", "minimum": 0.0, "maximum": 100.0 },
    "wind_speed_ms": { "type": "number", "minimum": 0.0 },
    "wind_direction_deg": { "type": "number", "minimum": 0.0, "maximum": 360.0 },
    "wind_u_ms": { "type": "number" },
    "wind_v_ms": { "type": "number" },
    "surface_pressure_hpa": { "type": "number", "minimum": 800.0, "maximum": 1100.0 },
    "boundary_layer_height_m": { "type": ["number", "null"], "minimum": 0.0 },
    "source": { "type": "string" }
  },
  "required": ["weather_id", "timestamp", "location", "temperature_c", "relative_humidity_pct", "wind_speed_ms", "wind_direction_deg", "surface_pressure_hpa", "source"]
}
```

### 3.3 `SatelliteSignal`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "SatelliteSignal",
  "type": "object",
  "properties": {
    "signal_id": { "type": "string" },
    "acquisition_time": { "type": "string", "format": "date-time" },
    "satellite": { "type": "string", "enum": ["Sentinel-5P", "VIIRS", "MODIS"] },
    "instrument": { "type": "string", "enum": ["TROPOMI", "VIIRS", "MODIS"] },
    "signal_type": { "type": "string", "enum": ["TROPOSPHERIC_NO2_COLUMN", "AEROSOL_INDEX", "THERMAL_FIRE_PIXEL"] },
    "geometry": { "type": "object", "description": "GeoJSON Point or Polygon" },
    "value": { "type": "number" },
    "unit": { "type": "string" },
    "quality_indicator": { "type": "string", "enum": ["HIGH", "NOMINAL", "LOW"] },
    "processing_level": { "type": "string", "enum": ["L2", "L3", "NRT"] }
  },
  "required": ["signal_id", "acquisition_time", "satellite", "signal_type", "geometry", "value", "unit", "quality_indicator"]
}
```

### 3.4 `CitizenEvidence`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CitizenEvidence",
  "type": "object",
  "properties": {
    "evidence_id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "location": {
      "type": "object",
      "properties": {
        "latitude": { "type": "number", "minimum": -90.0, "maximum": 90.0 },
        "longitude": { "type": "number", "minimum": -180.0, "maximum": 180.0 },
        "accuracy_m": { "type": ["number", "null"] }
      },
      "required": ["latitude", "longitude"]
    },
    "media_type": { "type": "string", "enum": ["image/jpeg", "image/png", "audio/wav", "audio/m4a"] },
    "storage_reference": { "type": "string" },
    "user_category": { "type": "string", "enum": ["biomass_burning", "construction_dust", "industrial_smoke", "vehicular_exhaust", "other"] },
    "description": { "type": ["string", "null"] },
    "ai_triage": {
      "type": ["object", "null"],
      "properties": {
        "verified_pollution": { "type": "boolean" },
        "detected_category": { "type": "string" },
        "optical_severity": { "type": "string", "enum": ["LOW", "MODERATE", "HIGH", "SEVERE"] },
        "visual_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
        "audio_transcript_en": { "type": ["string", "null"] },
        "rationale": { "type": "string" }
      }
    },
    "processing_status": { "type": "string", "enum": ["PENDING_TRIAGE", "VERIFIED", "REJECTED_SPAM", "DUPLICATE"] }
  },
  "required": ["evidence_id", "timestamp", "location", "media_type", "storage_reference", "user_category", "processing_status"]
}
```

---

## 4. Observation vs. Derived-Data Distinction & Scientific Integrity

A core vulnerability in hackathon environmental projects is the casual conflation of raw observational truth with algorithm outputs. VayuDrishti enforces an immutable architectural boundary:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              THE 5-TIER SCIENTIFIC ONTOLOGY                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 1: PHYSICAL OBSERVATION                                                           │
│  - Ground-truth in-situ physical sensor reading (e.g. CPCB Beta Attenuation Monitor)   │
│  - Measured in physical units: µg/m³. Immutable historical ground truth.               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 2: SATELLITE-DERIVED SIGNAL                                                       │
│  - Remote sensing column measurement (mol/m²) or brightness temperature (Kelvin).       │
│  - NOT equivalent to ground-level PM2.5. Acts only as supporting contextual evidence.  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 3: MODEL-DERIVED ANOMALY & INFERENCE                                              │
│  - Mathematical residual: Δ(x, y) = Local Sensor - Regional Kriging/IDW Baseline.      │
│  - Confidence (0–100) is an algorithmic score, NOT a physical probability of truth.    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 4: SHORT-TERM PREDICTION / FORECAST                                               │
│  - Statistical estimate generated by LightGBM using past lags and weather forecasts.   │
│  - Inherently uncertain; must always include confidence bands (P10–P90).               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 5: RISK & DECISION DIRECTIVE                                                      │
│  - Contextual policy directive combining hazard, vulnerability, and statutory SOPs.    │
│  - Not a physical measurement; an operational public-sector task.                     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Raw Pollutant Concentration vs. Derived AQI
- **Raw Pollutant Concentration:** The physical mass of particulate or gas per unit volume of air ($\mu\text{g/m}^3$ or $\text{mg/m}^3$). This is the only acceptable input for physical dispersion modeling and mathematical machine learning.
- **Air Quality Index (AQI):** A dimensionless, country-specific piecewise linear transformation used for public health communication. In India, the CPCB National Air Quality Index (IND-AQI) calculates sub-indices for 8 pollutants, with the maximum sub-index determining the composite AQI.
- **Rule:** AQI must **NEVER** be used as a training target or input feature for dispersion physics. Models must predict raw physical concentrations ($\mu\text{g/m}^3$ PM2.5) first, with AQI computed downstream as a presentation-layer transform.

---

## 5. Timestamp & Spatial Standards

### 5.1 Temporal Standardization
1. **Timezone Rule:** All internal storage, model inputs, and API serialization must use **UTC** with explicit ISO 8601 representation:
   $$\text{YYYY-MM-DDTHH:mm:ss.sssZ}$$
2. **Local Display Rule:** Conversion to Indian Standard Time (**IST, UTC+5:30**) occurs strictly at the client UI layer.
3. **Sampling Resolution:**
   - Real-time IoT: 5-minute to 15-minute intervals.
   - CAAQMS: 15-minute or 1-hour rolling intervals.
   - Meteorology: 1-hour discrete intervals.

### 5.2 Geospatial Coordinate Standardization
1. **Datum & CRS:** Universal coordinate reference system: **WGS 84 (`EPSG:4326`)**.
2. **Precision Standard:** Decimal degrees rounded to **6 decimal places** (providing spatial precision of $\approx 0.11\,\text{meters}$, avoiding truncation jitter while eliminating meaningless excess precision).
3. **Pilot Bounding Box Restrictions:**
   - **Delhi NCR Bounding Envelope:**
     - Min Latitude: $28.20^\circ\text{N}$, Max Latitude: $28.95^\circ\text{N}$
     - Min Longitude: $76.80^\circ\text{E}$, Max Longitude: $77.45^\circ\text{E}$
   - **Bengaluru Bounding Envelope:**
     - Min Latitude: $12.80^\circ\text{N}$, Max Latitude: $13.20^\circ\text{N}$
     - Min Longitude: $77.40^\circ\text{E}$, Max Longitude: $77.80^\circ\text{E}$

---

## 6. Unit Standards & Physical Wind Representation

### 6.1 Unit Standardization Table
To prevent catastrophic unit mismatches during feature engineering, all values are normalized to SI standards upon adapter ingestion:

| Dimension | Canonical Unit | Alternate External Unit | Conversion Formula |
| :--- | :--- | :--- | :--- |
| **Particulate Matter (PM2.5, PM10)** | $\mu\text{g/m}^3$ | $\text{mg/m}^3$ | $\mu\text{g/m}^3 = \text{mg/m}^3 \times 1000$ |
| **Gaseous Pollutant (NO2, SO2, O3)** | $\mu\text{g/m}^3$ | $\text{ppb}$ | $\mu\text{g/m}^3 = \text{ppb} \times \frac{M}{24.45}$ *(at STP)* |
| **Carbon Monoxide (CO)** | $\text{mg/m}^3$ | $\text{ppm}$ | $\text{mg/m}^3 = \text{ppm} \times 1.145$ |
| **Temperature** | $^\circ\text{C}$ (Celsius) | $^\circ\text{F}$ | $^\circ\text{C} = (^\circ\text{F} - 32) \times \frac{5}{9}$ |
| **Wind Speed** | $\text{m/s}$ | $\text{km/h}$ or $\text{knots}$ | $\text{m/s} = \text{km/h} / 3.6$ |
| **Surface Pressure** | $\text{hPa}$ (or $\text{mbar}$) | $\text{mmHg}$ or $\text{atm}$ | $\text{hPa} = \text{mmHg} \times 1.33322$ |
| **Boundary Layer Height** | $\text{meters (m)}$ | $\text{feet}$ | $\text{m} = \text{ft} \times 0.3048$ |

### 6.2 Meteorological Wind Representation
Wind direction in meteorology is defined as **the direction the wind is blowing FROM**, measured clockwise in degrees from True North ($0^\circ–360^\circ$):
- $0^\circ / 360^\circ = \text{North}$ (wind blowing from North towards South)
- $90^\circ = \text{East}$ (wind blowing from East towards West)
- $180^\circ = \text{South}$ (wind blowing from South towards North)
- $270^\circ = \text{West}$ (wind blowing from West towards East)

#### Vector Decomposition ($u$ and $v$ Components)
Linear models and tree models struggle with circular discontinuity (where $359^\circ$ is adjacent to $1^\circ$). The adapter engine automatically decomposes scalar wind speed $V$ ($\text{m/s}$) and direction $\theta$ ($^\circ$) into orthogonal Cartesian components:
$$u = -V \cdot \sin\left(\frac{\theta \cdot \pi}{180}\right) \quad (\text{Zonal Velocity: positive Eastward})$$
$$v = -V \cdot \cos\left(\frac{\theta \cdot \pi}{180}\right) \quad (\text{Meridional Velocity: positive Northward})$$
These $u$ and $v$ vector coordinates are stored directly in `WeatherObservation` and provide clean inputs for dispersion cone calculations and ML models.

---

## 7. Data Quality Principles & Validation Rules

Before raw inputs are admitted into the canonical store, the validation engine enforces 10 strict data quality filters:

1. **Bounding Box Validation:** Any record with geographic coordinates outside the approved pilot bounding box is rejected immediately with an `OUT_OF_BOUNDS` flag.
2. **Physical Boundary Checks:**
   - $\text{PM2.5} \in [0.0, 1500.0]\,\mu\text{g/m}^3$ (values $> 1500$ are flagged as sensor malfunction or direct fire contact).
   - $\text{PM10} \in [0.0, 3000.0]\,\mu\text{g/m}^3$ (and must satisfy $\text{PM10} \ge \text{PM2.5}$ within a 10% measurement error margin).
   - $\text{Relative Humidity} \in [0.0, 100.0]\%$.
   - $\text{Surface Pressure} \in [850.0, 1080.0]\,\text{hPa}$.
3. **Quality Flags:** Every observation is tagged with an explicit data quality enum:
   - `VALID`: Passed all coordinate, range, and temporal validation checks.
   - `SUSPECT`: Extreme spike exceeding $4\sigma$ from recent 6-hour moving average; held for secondary cross-validation.
   - `INVALID`: Unphysical value (negative concentration, timestamp in future); excluded from ML training.
   - `CALIBRATING`: Monitor reporting known warm-up or routine zero-drift calibration codes.
4. **Missing Value Representation:** Missing telemetry must be explicitly stored as `null` (None in Python). Imputing `0.0`, `-999`, or `-1` is strictly prohibited.
5. **Deduplication:** Composite primary key check across:
   $$\text{Composite Key} = (\text{source}, \text{station\_id}, \text{timestamp\_utc}, \text{pollutant})$$
6. **Temporal Monotonicity:** Within any single station stream, timestamps must be strictly monotonic ($t_{k} > t_{k-1}$). Out-of-order packets are re-sorted before batch feature creation.
7. **Stale Sensor Detection:** If a static sensor reports identical floating-point values for 4 consecutive hours, it is flagged as `SUSPECT_FROZEN` and discounted in spatial interpolation.

---

## 8. Source Adapter Architecture

External telemetry providers exhibit varying protocols, schemas, and payload formats. VayuDrishti isolates external changes by placing a formal **Adapter Boundary** in front of every source:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               SOURCE ADAPTER INTERFACE                                 │
├────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                        │
│   abstract class BaseSourceAdapter:                                                    │
│       def fetch_raw(self, time_range: TimeRange, bbox: BoundingBox) -> RawPayload:     │
│           """Fetches unparsed raw payload from external API or file source."""         │
│                                                                                        │
│       def parse(self, payload: RawPayload) -> List[UnvalidatedRecord]:                 │
│           """Extracts tabular records from vendor JSON/CSV/XML."""                     │
│                                                                                        │
│       def normalize(self, record: UnvalidatedRecord) -> CanonicalRecord:               │
│           """Converts vendor field names and units into canonical SI schema."""        │
│                                                                                        │
│       def validate(self, record: CanonicalRecord) -> ValidatedRecord:                  │
│           """Applies bounding box, physical limits, and quality flag rules."""         │
│                                                                                        │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Planned Source Adapters
1. **`AirQualityAdapter`:** Ingests CAAQMS stations via OpenAQ or direct CPCB endpoints; normalizes pollutant names and units; assigns `CAAQMS` source attribution.
2. **`WeatherAdapter`:** Ingests hourly meteorological grids from Open-Meteo; computes $u, v$ wind vector components and ventilation index.
3. **`SatelliteAdapter`:** Ingests NASA FIRMS active fire CSV/JSON points; normalizes fire radiative power and confidence.
4. **`CitizenEvidenceAdapter`:** Ingests mobile PWA multipart form-data (image + audio + metadata); forwards to Gemini Flash for structured triage; stores references in canonical schema.

---

## 9. Data Lifecycle & Directory Mapping

The file and storage system reflects an immutable data lineage pipeline, mapping directly to the project directory structure established in Phase 0:

```
                               DATA DIRECTORY MAPPING
┌──────────────────────┐
│ data/raw/            │ Immutable, read-only cache of vendor responses (raw JSON, CSV).
│                      │ Never edited in-place. Allows full offline pipeline reproduction.
└──────────┬───────────┘
           │
           ▼ Ingestion & Normalization
┌──────────────────────┐
│ data/processed/      │ Validated, cleaned, canonical time-series stored in Parquet/JSON.
│                      │ Used as ground-truth for feature engineering and spatial models.
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ data/external/       │ Static spatial reference layers: municipal ward polygons,
│                      │ OpenStreetMap road vectors, industrial zone boundaries.
└──────────────────────┘
```

### The 7-Stage Data Progression
$$\text{RAW} \longrightarrow \text{VALIDATED} \longrightarrow \text{NORMALIZED} \longrightarrow \text{FEATURE-READY} \longrightarrow \text{MODEL INPUT} \longrightarrow \text{MODEL OUTPUT} \longrightarrow \text{DECISION SUPPORT}$$

1. **RAW:** As-received bytes from OpenAQ, Open-Meteo, or citizen uploads.
2. **VALIDATED:** Checked for coordinates, missing fields, and timestamp validity.
3. **NORMALIZED:** Converted to canonical SI units and WGS 84 spatial coordinates.
4. **FEATURE-READY:** Joined with meteorological features, spatial lags ($t-1, t-3, t-6$), and wind vector components.
5. **MODEL INPUT:** Clean tabular feature matrix consumed by LightGBM regressor and kriging baseline.
6. **MODEL OUTPUT:** Predicted concentrations ($\mu\text{g/m}^3$) with confidence intervals ($P_{10}, P_{50}, P_{90}$).
7. **DECISION SUPPORT:** High-confidence hotspot alerts matched with statutory GRAP operating directives.

---

## 10. Privacy Principles & Citizen Data Governance

Because crowdsourced citizen evidence involves smartphones, cameras, and microphones, VayuDrishti implements **strict privacy-by-design principles**:

1. **Zero Unnecessary PII:** The platform does **not** collect citizen names, phone numbers, home addresses, or national identity numbers (Aadhaar).
2. **Ephemeral Identity Hashing:** Citizen submissions are tagged with a salted, client-side rotating hash (`sha256(device_id + salt)`). This prevents tracking a user's movements across the city while still allowing anti-spam rate limiting.
3. **EXIF Metadata Scrubbing:** Before storing or displaying uploaded images, all EXIF metadata (camera serial numbers, exposure metadata, personal camera device tags) is stripped.
4. **Spatial Coordinate Fuzzing on Public Maps:**
   - In the **Public View**, citizen report markers are programmatically fuzzed by $\pm 150\,\text{meters}$ to prevent exposing an individual's private residence or balcony location.
   - In the **Authority Console**, exact coordinates are accessible only to authenticated municipal officers executing statutory enforcement.
5. **Voice Note Privacy:** Citizen voice notes are transcribed to English text via Gemini Audio and immediately converted to text-only incident descriptions. Raw voice binaries are deleted after 7 days.

---

## 11. Storage & Persistence Architecture

For the hackathon MVP, VayuDrishti balances operational simplicity with scalability:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                STORAGE TIER ARCHITECTURE                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 1: HOT / OPERATIONAL STATE (Low Latency, Real-Time Subscriptions)                 │
│  - Local Dev / MVP: SQLite with WAL (Write-Ahead Logging) or Firebase Firestore.       │
│  - Contents: Active hotspot polygons, citizen reports under triage, authority dispatch│
│    workflow states (PENDING -> DISPATCHED -> RESOLVED).                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 2: BLOB MEDIA STORE (Object Storage)                                              │
│  - Local Dev / MVP: Local structured file cache (`data/raw/uploads/`) or Firebase      │
│    Cloud Storage bucket.                                                               │
│  - Contents: Uploaded citizen photos and pre-rendered Sentinel-5P satellite rasters.   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TIER 3: COLD / ANALYTICAL TIME-SERIES (High Throughput, Analytical Queries)            │
│  - Local Dev / MVP: DuckDB / Parquet files in `data/processed/`.                       │
│  - Cloud Target (Production): Google BigQuery partitioned by `timestamp_utc(DAY)`.     │
│  - Contents: Historical hourly CAAQMS telemetry, weather grids, and forecast audits.   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. Data Lineage & Provenance Principles

Every analytical alert, hotspot polygon, and prediction must be **auditable**:
1. **Provenance Tracking:** Every generated `HotspotSummary` and `ForecastSummary` record carries an explicit `provenance` metadata block listing:
   - Identifiers of all underlying sensor observations used.
   - Identifiers of all citizen evidence items included.
   - Version tag of the LightGBM model (`model_version`).
   - Version of the GRAP decision rule matrix (`rule_engine_version`).
2. **Reproducibility:** A judge or regulatory official can trace any priority alert back to:
   - Exactly which citizen photo triggered the triage.
   - The exact meteorological wind vector that established the downwind dispersion cone.
   - The exact CAAQMS regional baseline against which the spatial residual was calculated.

---
**PHASE 1C DATA ARCHITECTURE SIGN-OFF:** COMPLETED & FROZEN  
**NEXT DOCUMENT:** `docs/DATA_SOURCES.md`
