# VayuDrishti Data Sources Registry & Access Contract
## Phase 1C Specification: Candidate Sources, Verification & Licensing
**Status:** PHASE 1C — DATA SOURCES CONTRACT FROZEN  
**Project:** VayuDrishti — Clean Air & Climate Resilience  
**Local Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  

> **CRITICAL SCIENTIFIC INTEGRITY & ACCESS NOTICE:**  
> In compliance with Phase 1C requirements, **NO EXTERNAL DATASETS OR APIS ARE ACCESSED, DOWNLOADED, OR SCRAPED DURING THIS PHASE.**  
> All listed external sources represent candidate data integrations evaluated for downstream implementation in Phase 2. Sources are classified as either **VERIFIED** (open public documentation and schema confirmed) or **CANDIDATE SOURCE — TO BE VERIFIED**.

---

## 1. Candidate Source Master Registry

| Source Name | Data Domain | Data Format | Update Frequency | Geographic Scope | Access Protocol | Verification Status | Licensing & Terms | MVP Role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **OpenAQ API** | Air Quality (CAAQMS) | JSON (REST API) | Hourly / Real-time | Global (India nodes: Delhi, Bengaluru, Mumbai) | HTTP GET / API Key (free tier) | **VERIFIED** | Open Data (CC-BY 4.0) | **REQUIRED** |
| **CPCB Central Data Portal** | Air Quality (Official) | HTML / PDF / Scraping | Hourly / Daily | National (All Indian States) | Web Portal / Captcha-protected | **REJECTED (Use OpenAQ)** | Government Open Data / Proprietary terms | **EXCLUDED** |
| **Community IoT Networks** *(PurpleAir / Atmos)* | Air Quality (Micro-sensors) | JSON / CSV | 2–10 Minutes | Select Indian Urban Clusters | REST API / Public Community Feeds | **CANDIDATE — TO BE VERIFIED** | Community / Commercial Terms | **OPTIONAL** |
| **Open-Meteo API** | Weather & Dispersion | JSON (REST API) | Hourly + 7-Day Forecast | Global ($1\text{km} - 11\text{km}$ grid resolution) | HTTP GET (No API key required for non-commercial) | **VERIFIED** | Open Data (CC-BY 4.0) | **REQUIRED** |
| **India Meteorological Dept (IMD)** | Weather & Weather Warnings | Gridded NetCDF / XML | 3–6 Hours | National (India) | Government FTP / Open Data Portals | **CANDIDATE — TO BE VERIFIED** | National Government Open Data | **OPTIONAL** |
| **Copernicus Sentinel-5P TROPOMI** | Satellite (NO2, Aerosol) | GeoTIFF / Raster | Daily overpass ($\approx 13:30$ local solar time) | Global ($3.5 \times 5.5\,\text{km}$ pixel resolution) | Google Earth Engine (GEE) Python API | **VERIFIED** | Copernicus Open Access / Free for research | **REQUIRED (Cached)** |
| **NASA FIRMS (MODIS / VIIRS)** | Active Fire & Thermal Anomalies | CSV / GeoJSON (REST) | 3–6 Hours | Global ($375\text{m}$ VIIRS / $1\text{km}$ MODIS) | Open South Asia NRT Stream / Map Key API | **VERIFIED** | NASA Open Data Policy (Public Domain) | **REQUIRED** |
| **OpenStreetMap (OSM)** | Geographic & Land-Use | GeoJSON / Vector XML | Static / Live Overpass | Global (Complete Indian cities) | Overpass QL / Geofabrik Extracts | **VERIFIED** | Open Database License (ODbL) | **REQUIRED** |
| **Municipal Ward Boundaries** *(DataMeet)* | Administrative Boundaries | GeoJSON / Shapefile | Static (Census / ULB revisions) | Delhi MCD, Bengaluru BBMP wards | GitHub Open Data Repository | **VERIFIED** | Open Community Data (CC-BY-SA) | **REQUIRED** |
| **VayuDrishti Citizen PWA** | Crowdsourced Ground Evidence | Multipart Form / JSON | Event-driven (Real-time) | Pilot corridors (Delhi, Bengaluru) | Native HTTPS API (`/api/v1/evidence/upload`) | **VERIFIED (Internal)** | User Content Agreement / Privacy Consent | **REQUIRED** |

---

## 2. Air Quality Sources Analysis

### 2.1 Primary Candidate: OpenAQ REST API
- **Why Selected:** OpenAQ aggregates official Indian regulatory stations (including CPCB and State Pollution Control Boards like DPCC and KSPCB) into a standardized, machine-readable JSON schema with standardized station coordinates and physical units ($\mu\text{g/m}^3$).
- **API Endpoint Structure:** `https://api.openaq.org/v3/locations?country=IN&city=Delhi`
- **Fields Captured:** `parameter` (PM2.5, PM10, NO2), `value`, `unit`, `datetime`, `coordinates` (`latitude`, `longitude`).
- **Rate Limits & Reliability:** Free tier provides 60 requests/minute. Station dropout rate in India typically ranges from 5% to 15% during sensor maintenance cycles.
- **Handling Strategy:** The `AirQualityAdapter` caches recent station readings locally in `data/raw/` to ensure offline demo resilience if the live upstream provider experiences brief latency.

### 2.2 Secondary Candidate: Direct CPCB / SPCB Portals
- **Current Status:** *CANDIDATE SOURCE — TO BE VERIFIED*.
- **Challenges:** Official portals frequently deploy session tokens, dynamic JavaScript renderers, or anti-scraping Captcha gates that introduce fragility into autonomous hackathon pipelines.
- **Decision:** Use OpenAQ as the primary standardized pipeline for CPCB data; direct CPCB scraping is retained only as an optional secondary research vector.

### 2.3 Micro-Sensor Networks (Low-Cost IoT Community Nodes)
- **Current Status:** *CANDIDATE SOURCE — TO BE VERIFIED*.
- **Candidate Networks:** PurpleAir, OpenSenseMap, Atmos community sensors.
- **Role in MVP:** If verified active public nodes exist within the Mayapuri (Delhi) or Peenya (Bengaluru) pilot corridors during Phase 2, they will be ingested via the `AirQualityAdapter`. If live nodes are unavailable, synthetic test sensor nodes will be generated following the identical schema to prove multi-tier sensor fusion.

---

## 3. Meteorological Data Sources Analysis

### 3.1 Primary Candidate: Open-Meteo Hourly Forecast API
- **Why Selected:** Fully verified, open-access, zero-credential REST API providing high-resolution hourly meteorological reanalysis and forward forecasting for any coordinate worldwide.
- **API Endpoint Structure:**
  `https://api.open-meteo.com/v1/forecast?latitude=28.61&longitude=77.20&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,surface_pressure,boundary_layer_height`
- **Critical Atmospheric Variables:**
  - `wind_speed_10m` ($\text{m/s}$) & `wind_direction_10m` ($^\circ$): Governs plume dispersion speed and trajectory.
  - `boundary_layer_height` ($\text{meters}$): Identifies nocturnal and winter temperature inversions that trap pollutants close to street level.
  - `relative_humidity_2m` ($\%$): Controls secondary aerosol formation and optical hygroscopic scattering.
- **License:** Non-commercial open access under CC-BY 4.0. Completely reliable for hackathon prototyping and evaluation.
- **Implementation Status:** Phase 1E-B Meteorological Ingestion Pipeline implemented and verified (see `docs/DATA_INGESTION_OPENMETEO.md`).

---

## 4. Satellite & Earth Observation Sources Analysis

### 4.1 Sentinel-5P TROPOMI (Tropospheric NO2 & Aerosols)
- **Data Provider:** European Space Agency (ESA) Copernicus Programme / Google Earth Engine (GEE).
- **GEE ImageCollection:** `COPERNICUS/S5P/NRTI/L3_NO2` (Near Real-Time Level 3 product).
- **Spatial Resolution:** $3.5 \times 5.5\,\text{km}$ at nadir.
- **Physical Parameter:** `tropospheric_NO2_column_number_density` ($\text{mol/m}^2$).
- **Scientific Role:** Validates whether elevated ground NO2 readings represent localized industrial/vehicular point-sources or wide-area transboundary regional smog.
- **Implementation Strategy for MVP:** Live on-the-fly planetary raster queries introduce substantial network latency during live judging demonstrations. In Phase 2/3, representative Sentinel-5P raster extracts for the Delhi and Bengaluru pilot boxes will be extracted via GEE Python API, converted to optimized WebP/PNG raster tile layers, and served via Cloud Storage/local static cache for instantaneous map rendering.

### 4.2 NASA FIRMS (Fire Information for Resource Management System)
- **Data Provider:** NASA Earth Observing System Data and Information System (EOSDIS).
- **Sensors:** VIIRS ($375\,\text{m}$ spatial resolution on Suomi-NPP / NOAA-20) and MODIS ($1\,\text{km}$ spatial resolution on Terra / Aqua).
- **Endpoint Structure:** `https://firms.modaps.eosdis.nasa.gov/api/area/csv/[MAP_KEY]/VIIRS_SNPP_NRT/[BBOX]/1`
- **Fields Captured:** `latitude`, `longitude`, `brightness`, `scan`, `track`, `acq_date`, `acq_time`, `satellite`, `confidence`, `frp` (Fire Radiative Power, in $\text{MW}$).
- **Scientific Role:** Direct physical indicator of high-temperature thermal emissions (agricultural residue/stubble burning, industrial flaring, uncontrolled open municipal solid waste burning).
- **License:** Public domain (NASA Open Data Policy).

---

## 5. Geographic & Infrastructure Data Sources Analysis

### 5.1 OpenStreetMap (OSM) Road & Industrial Vectors
- **Data Extractor:** Overpass QL API / Geofabrik regional OSM extracts.
- **Features Extracted:**
  - Highway hierarchy: `motorway`, `trunk`, `primary`, `secondary` (identifies high-emission diesel freight bottlenecks).
  - Land-use classifications: `industrial`, `quarry`, `landfill`, `commercial`.
  - Sensitive points of interest: `school`, `kindergarten`, `hospital`, `clinic`, `nursing_home`.
- **License:** Open Database License (ODbL). Attribution required on map canvas.

### 5.2 Municipal Administrative Ward Boundaries
- **Source:** DataMeet Open Spatial Data Repository for Indian Municipalities.
- **Coverage:** Municipal Corporation of Delhi (MCD) 250 wards (Delhi_Wards.geojson); Bruhat Bengaluru Mahanagara Palike (BBMP) 198 wards (BBMP.geojson).
- **Data Format:** Standard GeoJSON polygons.
- **Role:** Maps detected hotspot bounding centroids to specific municipal ward offices and responsible flying squad inspection units.

---

## 6. Citizen Evidence Channel (Internal Platform Source)

### 6.1 Native Mobile-Web Progressive Web Application (PWA)
- **Channel Identity:** `VayuDrishti Client Web Intake`.
- **Supported Media:**
  - Photography: Standard compressed JPEG/PNG captured live via device camera API.
  - Audio Voice Memos: AAC / WebM / WAV recordings captured via MediaStream Recording API (max duration: 30 seconds).
  - Geolocation: HTML5 Geolocation API (`navigator.geolocation.getCurrentPosition`) capturing latitude, longitude, and accuracy radius ($\pm\text{m}$).
- **Categorical Tags:** `biomass_burning` (garbage/leaves), `construction_dust`, `industrial_smoke`, `vehicular_exhaust`, `other`.
- **Consent Contract:** Explicit user confirmation notice: *"By submitting, you consent to public reporting of this localized pollution event. Your personal device identifier and location coordinates are anonymized and fuzzed on public maps."*

---

## 7. Master Source Classification for Hackathon Implementation

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               MASTER SOURCE CLASSIFICATION                             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 🟢 REQUIRED FOR HACKATHON MVP (Core Prototype)                                         │
│   1. OpenAQ API (Delhi NCR & Bengaluru CAAQMS stations)                                │
│   2. Open-Meteo Hourly Forecast API (Temperature, RH, Wind Speed/Direction, PBLH)     │
│   3. NASA FIRMS Active Fire Points (VIIRS 375m thermal anomaly coordinates)            │
│   4. Pre-rendered Sentinel-5P NO2 Tile Overlays (GEE cached spatial layers)            │
│   5. OpenStreetMap Freight Corridors & Industrial Estate Polygons                      │
│   6. Municipal Ward Boundary GeoJSON (Delhi MCD & Bengaluru BBMP)                      │
│   7. VayuDrishti Citizen PWA Evidence Intake (Live camera & audio memo submission)     │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 🟡 OPTIONAL (Integrate in Phase 8 if time and API keys permit)                         │
│   1. PurpleAir / Atmos public community sensor nodes in Delhi NCR                      │
│   2. Live dynamic Google Earth Engine raster streaming directly from cloud             │
│   3. India Meteorological Department (IMD) warning alerts RSS feeds                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ ⚪ FUTURE (Post-Hackathon Production Roadmap)                                          │
│   1. Real-time CPCB SCADA industrial stack emissions (Continuous Emission Monitoring)  │
│   2. Delhi Traffic Police real-time speed/congestion feeds                             │
│   3. Municipal automated drone aerial gas sampling payloads                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Scientific Integrity & Cautious Language Mandate

In environmental systems, over-promising AI capabilities destroys credibility with regulators and public-sector judges. The platform code, logs, tooltips, and documentation must **strictly observe scientific humility**:

### Prohibited vs. Required Terminology

| ❌ Scientifically Inaccurate / Overstated Claim | ✅ Scientifically Grounded / Cautious Terminology |
| :--- | :--- |
| *"Satellite proves illegal factory pollution."* | *"Satellite thermal anomaly indicates an intense surface heat source consistent with combustion activity."* |
| *"Citizen photo confirms hazardous toxic air."* | *"Multimodal visual analysis detects a dense, dark smoke plume with estimated high optical opacity."* |
| *"AI predicts exact PM2.5 of 342.8 µg/m³."* | *"Model projects elevated PM2.5 concentrations (median 340 µg/m³, 80% interval: 290–390 µg/m³)."* |
| *"This hotspot is 100% caused by scrap melting."* | *"Multi-source evidence fusion assigns a confidence score of 91/100, attributing probable cause to scrap burning based on thermal and visual alignment."* |
| *"The air is guaranteed safe today."* | *"Measured and forecasted indicators remain within statutory National Ambient Air Quality Standards (NAAQS)."* |

---
**PHASE 1C DATA SOURCES SIGN-OFF:** COMPLETED & FROZEN  
**NEXT ACTION:** AWAIT USER INSTRUCTION FOR PHASE 2 PLANNING
