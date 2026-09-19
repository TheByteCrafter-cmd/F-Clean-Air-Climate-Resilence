# VayuDrishti — Hyper-Local Hotspot & Spatial Context Visualization Specification

**Phase**: 1E-J2E.4.7  
**Component**: `frontend/src/components/HyperLocalEvidenceMap.tsx`  
**Data Artifact**: `frontend/src/data/delhi_geospatial_context.json`  
**Status**: OPERATIONAL  

---

## 1. Executive Summary & Rendering Architecture

The Hyper-Local Hotspot & Spatial Context Visualization (`HyperLocalEvidenceMap.tsx`) provides an offline-first, read-only SVG vector map interface for presenting multi-layer geospatial evidence in a clean, calm, civic environmental format.

```
                           ┌────────────────────────────────────────┐
                           │      DecisionIntelligenceView.tsx      │
                           └───────────────────┬────────────────────┘
                                               │
                                               ▼
                           ┌────────────────────────────────────────┐
                           │      HyperLocalEvidenceMap.tsx         │
                           └───────────────────┬────────────────────┘
                                               │
                                 SVG Projection Engine (WGS84)
                                               │
                                               ▼
         ┌──────────────────────────────────────────────────────────────────────────┐
         │ 1. Pilot Ground Station Marker (Anand Vihar 8118)                        │
         │ 2. Audited Hotspot Region Polygon & Centroid Marker                      │
         │ 3. Industrial Context Polygon / Point Layer                             │
         │ 4. Major Road Corridor Line Layer                                        │
         │ 5. Sensitive Receptor (School / Healthcare Facility) Pin Layer           │
         │ 6. Read-Only Feature Inspection & Evidence Trace Audit Linkage           │
         └──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Spatial Data Sources & Artifact Paths

- **Authoritative GeoJSON Context Source**: `data/processed/geospatial/delhi_geospatial_context.geojson`
- **Frontend Local Asset Path**: `frontend/src/data/delhi_geospatial_context.json`
- **Feature Breakdown**:
  - `road` (50 features): Arterial transport corridors, highways, and major avenues.
  - `industrial` (25 features): Designated industrial parks, stack zones, and manufacturing clusters.
  - `sensitive_receptor` (50 features): Schools, hospitals, clinics, and eldercare facilities.

---

## 3. Projection & Local Vector Canvas Standard

The map projection engine uses a linear coordinate transformation mapping WGS84 longitude/latitude coordinates onto a 720×420 SVG vector canvas:

```ts
// WGS84 Projection Bounds
MIN_LON = 77.05, MAX_LON = 77.35
MIN_LAT = 28.55, MAX_LAT = 28.75

project(lon, lat):
  x = PADDING + ((lon - MIN_LON) / (MAX_LON - MIN_LON)) * (WIDTH - 2 * PADDING)
  y = HEIGHT - PADDING - ((lat - MIN_LAT) / (MAX_LAT - MIN_LAT)) * (HEIGHT - 2 * PADDING)
```

---

## 4. Hotspot & Context Layer Capabilities

1. **Pilot Ground Station**:
   - Location: `Anand Vihar 8118` (`28.6476° N, 77.3158° E`).
   - Distinct navy station badge with white core symbol and label.

2. **Audited Hotspot Overlay**:
   - Visualizes audited hotspot geometry and centroid marker when present in decision payload.
   - Highlights support score (`85.0/100`), confidence tier (`HIGH_SUPPORT`), spatial extent (`4.5 km`), and corroborating source families (`INDUSTRIAL_STACK, TRAFFIC_CORRIDOR`).
   - If hotspot data is missing/null, renders explicit notice: `"No hotspot evidence is available for this decision."`

3. **Spatial Context Layers**:
   - **Industrial Context**: Rendered in amber fill/stroke (`Industrial context present`).
   - **Major Roads**: Rendered in slate line corridors (`Major-road context present`).
   - **Sensitive Receptors**: Rendered in purple pin markers (`Sensitive-receptor context present`).

4. **Non-Causal Safeguards**:
   - All tooltips, labels, and inspector cards use non-causal context wording.
   - Explicitly refrains from making claims of pollution causality or source liability.

5. **Data Quality Awareness**:
   - `READY`: Full operational vector visualization rendered with layer toggles.
   - `PARTIAL`: Renders available spatial layers alongside warning box listing missing factors.
   - `BLOCKED`: Displays prominent notice that spatial intelligence is blocked for operational decision support.

---

## 5. Offline-First Verification

- **Zero External Network Dependencies**: Operates completely offline without tile requests to Google Maps, Mapbox, OpenStreetMap, OpenAQ, Overpass, FIRMS, or Google Earth Engine.
- **Zero Polling / SSE**: Pure read-only interaction with local vector data.

---

## 6. Build & Verification Standard

- **Frontend Build**: `npm --prefix frontend run build` (Exit Code 0).
- **Backend Regression**: `.venv\Scripts\pytest.exe -v` (374 passed, 1 skipped).
- **Model SHA256 Hashes**: `lightgbm_pm25_{1h,3h,6h}.txt` verified intact.
