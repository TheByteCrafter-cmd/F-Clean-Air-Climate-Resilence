# VayuDrishti — Hyper-Local Pollution Hotspot Detection Foundation
**Phase:** PHASE 1E-I  
**Status:** COMPLETED & VERIFIED  
**Date:** September 2026  
**Implementation:** `backend/ingestion/hotspot_detector.py`, `backend/api/v1/endpoints/hotspot.py`

---

## 1. Executive Summary

Phase 1E-I establishes the **Hyper-Local Pollution Hotspot Detection Foundation** for VayuDrishti. The detector transforms localized OpenAQ air quality observations, meteorology, thermal anomalies, satellite Signals, and existing `EvidenceFusionResult` artifacts into spatially contiguous candidate hotspot polygons across an analysis grid.

Crucially, a detected hotspot means:
> *"An area showing an elevated/anomalous pollution signal relative to the available local observations and supporting evidence."*

It does **NOT** mean:
- Pollution source confirmed
- Industrial facility confirmed as source
- Fire confirmed as source
- Human exposure confirmed
- Health risk confirmed
- Legal violation confirmed

The system strictly avoids causal claims, using non-causal language such as *"Potential hyper-local pollution hotspot"*.

---

## 2. Core Methodological Components

### 2.1 Approved Pilot Region of Interest (ROI)
The analysis operates on a configurable geographic bounding box covering the approved Delhi pilot domain:
- **`ROI Bounding Box`:** `[28.40, 76.85, 28.88, 77.40]` (`[lat_min, lon_min, lat_max, lon_max]`)
- **`Grid Spacing`:** `0.01°` ($\approx 1.1\text{ km}$ spacing across the pilot domain).

### 2.2 Pollutant Scope & Temporal Window
- **Primary Pollutant:** `PM2.5` (µg/m³)
- **Temporal Window:** $\pm 60\text{ minutes}$ around target analysis timestamp.

### 2.3 Station Observation Preparation
Before spatial interpolation:
1. Filter by pollutant (`PM2.5`).
2. Filter by valid timestamp within $\pm 60\text{ minutes}$.
3. Filter by physical WGS84 coordinates and non-negative value.
4. Deduplicate observations by station ID and timestamp.

---

## 3. Mathematical Formulation & Interpolation

### 3.1 Local Baseline Calculation (Robust Median)
To avoid fixed arbitrary national thresholds and outlier distortion:
$$\text{local\_baseline} = \text{median}(\{v_1, v_2, \dots, v_n\})$$
where $v_i$ are all valid spatial observations within the analysis window.

### 3.2 Anomaly Measure
- **Absolute Anomaly:**
  $$\text{anomaly\_value} = \text{interpolated\_value} - \text{local\_baseline}$$
- **Relative Anomaly:**
  $$\text{relative\_anomaly} = \frac{\text{interpolated\_value} - \text{local\_baseline}}{\max(|\text{local\_baseline}|, 1.0)}$$

### 3.3 Minimum Station Density Rule (Sparse-Data Safety)
- **`min_stations_for_idw`:** $3$ stations within `max_idw_radius_km` ($10.0\text{ km}$).
- If fewer than 3 independent stations exist within radius, the grid cell is marked `INSUFFICIENT_LOCAL_COVERAGE` and excluded from candidate hotspot generation.

### 3.4 Inverse Distance Weighting (IDW)
- **Distance Metric:** Haversine spherical-distance approximation using WGS84 coordinates:
  $$d = 2R \cdot \text{atan2}\left(\sqrt{a}, \sqrt{1-a}\right)$$
- **Power Exponent:** $p = 2.0$ (`IDW_POWER = 2.0`).
- **Zero-Distance Handling:** If $d < 10^{-5}\text{ km}$, station observed value is assigned directly.
- **Interpolation Equation:**
  $$Z(x) = \frac{\sum w_i \cdot z_i}{\sum w_i}, \quad w_i = \frac{1}{d_i^p}$$

---

## 4. Contiguous Region Aggregation & Geometry Generation

1. **Qualifying Grid Cells:**
   - Spatial sufficiency: $\ge 3$ stations within $10\text{ km}$.
   - Absolute anomaly: $\ge 30.0\text{ }\mu\text{g/m}^3$ above local median.
   - Relative anomaly: $\ge 0.25$ ($25\%$ elevation).
2. **Contiguous Neighbor Aggregation:**
   Adjacent qualifying grid cells sharing 4-neighbor boundary adjacency are aggregated into candidate regions without requiring DBSCAN or ML models.
3. **Geometry Generation:**
   Constructs GeoJSON `Polygon` or `MultiPolygon` geometries representing grid cell boundary boxes: *"Derived analysis polygon based on interpolated grid cells."*

---

## 5. Hotspot Support Score & Confidence Tiers

The **Hotspot Support Score (0.0 – 100.0)** is calculated deterministically across 4 components:
1. **Anomaly Magnitude:** Up to $40.0$ pts (scaled by $\text{anomaly\_value}$).
2. **Spatial Extent:** Up to $20.0$ pts (scaled by contiguous cell count).
3. **Station Density:** Up to $15.0$ pts (scaled by station count within radius).
4. **Corroborating Evidence Linkage:** Up to $25.0$ pts from existing `EvidenceFusionResult` artifacts, FIRMS thermal signals, weather stagnation ($\le 3.0\text{ m/s}$), Sentinel-5P NO2, and OSM industrial context.

### Confidence Tiers:
- **`HIGH_SUPPORT` ($\ge 70.0$ pts):** Strong spatial anomaly with multi-source evidence corroboration.
- **`MODERATE_SUPPORT` ($40.0 - 69.9$ pts):** Clear spatial anomaly with partial corroboration.
- **`LOW_SUPPORT` ($< 40.0$ pts):** Elevated local observation with limited spatial coverage or corroboration.

---

## 6. Artifact Storage & Provenance

Hotspot detection results are stored under:
`data/processed/hotspots/<hotspot_id>.json` (`hs_<uuid_hex>`)

A lightweight GeoJSON FeatureCollection is maintained at:
`data/processed/hotspots/delhi_hotspots.geojson`

---

## 7. REST API Endpoints

- **`POST /api/v1/hotspots/detect`**: Triggers spatial IDW interpolation and returns `List[HotspotDetectionResult]`.
- **`GET /api/v1/hotspots/{hotspot_id}`**: Fetches full `HotspotDetectionResult` detail by hotspot ID.
- **`GET /api/v1/hotspots`**: Returns `HotspotCollectionResponse` containing `HotspotSummary` items.

---

## 8. Verification & Testing

Full test suite in `tests/test_hotspot_detection.py` verifies:
- Haversine distance and median baseline calculation.
- IDW interpolation and zero-distance exact matching.
- Enforced minimum station density rule ($<3$ stations -> insufficient data).
- Contiguous cell grouping and GeoJSON polygon construction.
- Idempotent filesystem persistence (`hs_<uuid>.json` and `delhi_hotspots.geojson`).
- REST API endpoints (`POST detect`, `GET detail`, `GET collection`).
- Scenarios A through H.
- Score invariance across direct source artifacts vs. `EvidenceFusionResult` summaries.
- 123 passing unit/integration tests across codebase.

---

## 9. Scoring Integrity & Evidence Double-Counting Prevention

To prevent the exact same underlying physical evidence from being credited multiple times when present through both direct source artifacts and linked `EvidenceFusionResult` summaries, the hotspot engine enforces strict set-based evidence deduplication rules:

### Core Scoring Principles
1. **Primary Anomaly Signal:** Spatial PM pollution interpolation ($IDW, p=2.0$) and local baseline deviation drive up to $75.0$ points ($40.0$ pts anomaly magnitude, $20.0$ pts spatial extent, $15.0$ pts station coverage).
2. **Non-Duplicated Corroboration:** Up to $25.0$ points awarded for independent corroborating evidence families ($6.25$ pts per unique non-OpenAQ family).
3. **OpenAQ Exclusion from Corroboration:** OpenAQ telemetry drives the primary spatial anomaly calculation and is explicitly excluded from receiving an additional independent corroboration bonus.
4. **Fusion Result as Corroboration Summary:** A linked `EvidenceFusionResult` artifact provides corroborating evidence for `"CITIZEN_GEMINI"` (anchor) and any represented source families (`"THERMAL_ANOMALY"`, `"SATELLITE_NO2"`, `"GEOSPATIAL_CONTEXT"`, `"WEATHER"`).
5. **Set-Based Source Family Deduplication:** Non-AirQuality source families are tracked in a set (`scored_families`). Each unique source family can contribute to the corroboration score at most **ONCE**, regardless of whether it appears via an `EvidenceFusionResult`, a direct source artifact (FIRMS, Sentinel-5P, OSM, Weather), or both.
6. **Score Invariance Guarantee:** Providing direct source records alongside an `EvidenceFusionResult` referencing the exact same source families produces an **identical** support score, eliminating duplicate counting.
7. **Score Semantics & Disclaimers:** Hotspot Support Score $\neq$ probability of pollution, probability of causation, or health risk. It represents an engineering evidence-support score reflecting spatial anomaly strength and multi-source corroboration.

