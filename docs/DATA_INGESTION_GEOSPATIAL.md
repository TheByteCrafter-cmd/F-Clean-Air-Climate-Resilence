# Data Ingestion: Geospatial Context & Municipal Administrative Boundaries

## 1. Domain Overview & Scope

The Geospatial Context domain establishes static and semi-static spatial priors that ground environmental measurements and citizen reports into physical infrastructure and jurisdictional boundaries. In VayuDrishti, this domain comprises two distinct, complementary source families:

1. **OpenStreetMap (OSM) via Overpass API:** Major arterial freight corridors, industrial land-use zones, and sensitive community receptors (hospitals, schools, clinics).
2. **Municipal Administrative Boundaries via DataMeet:** Standardized ward polygons for Delhi Municipal Corporation (MCD) and Bengaluru Bruhat Bengaluru Mahanagara Palike (BBMP).

```
OpenStreetMap / Overpass API              DataMeet Open Spatial Data
            ?                                         ?
   Controlled Bounded QL                      Raw GeoJSON from CDN
            ?                                         ?
    Raw Response (JSON)                       Raw Response (GeoJSON)
            ?                                         ?
  OSMNormalizer (Tag Whitelist)             BoundaryNormalizer (City Mapping)
            ?                                         ?
    GeospatialValidator                       GeospatialValidator
 (WGS84 EPSG:4326, Deduplication)          (WGS84 EPSG:4326, Deduplication)
            ?                                         ?
   delhi_roads.geojson                       delhi_wards.geojson
   delhi_industrial_areas.geojson            bengaluru_wards.geojson
   delhi_sensitive_pois.geojson
            ?                                         ?
     osm_delhi_quality_report                 wards_quality_report
```

### Scientific Integrity & Strict Scope Boundary
- **Pure Contextual Layer:** This phase only ingests and validates clean vector geometries.
- **NO Spatial Interpolation:** Inverse Distance Weighting (IDW), Kriging, and spline modeling are strictly prohibited in this phase.
- **NO Hotspot Detection or Risk Scoring:** Hotspot clustering (DBSCAN), corridor proximity weights, and multi-source evidence fusion are deferred to subsequent analytics phases.
- **NO Frontend Maps:** Google Maps SDK, Leaflet, Mapbox, and visual dashboard renderers are not implemented in this phase.

---

## 2. OpenStreetMap / Overpass Ingestion Specification

### 2.1 Endpoint & Protocol
- **Endpoint:** `POST` / `GET` `https://overpass-api.de/api/interpreter`
- **User-Agent:** `VayuDrishti-Research/1.0` *(mandatory; Overpass rejects requests without custom User-Agent with HTTP 406)*
- **Data Format:** Overpass JSON with embedded geometries (`out geom;`)
- **Licensing:** Open Database License (ODbL) ? Mandatory attribution: `? OpenStreetMap contributors`

### 2.2 Controlled Pilot Geography & Bounding Box
To prevent overloading the shared public Overpass infrastructure, queries are strictly constrained to the approved Delhi pilot corridor:

$$	ext{Latitude: } 28.6000^\circ	ext{N to } 28.7200^\circ	ext{N}, \quad 	ext{Longitude: } 77.0800^\circ	ext{E to } 77.2200^\circ	ext{E}$$

This box encapsulates the Mayapuri Industrial Cluster, Wazirpur Metal Rolling Cluster, Rohtak Road (NH-9), Najafgarh Road, and the Western Ring Road.

### 2.3 Query Architecture & Multi-Stage Balancing
Overpass default sorting emits `node` primitives before `way` primitives. To prevent ubiquitous sensitive POIs (hundreds of clinics and schools) from exhausting the query result limit before road vectors are emitted, the query utilizes multi-stage output blocks:

```overpass
[out:json][timeout:25];
(
  way["highway"="trunk"](28.60,77.08,28.72,77.22);
  way["highway"="primary"](28.60,77.08,28.72,77.22);
  way["highway"="secondary"](28.60,77.08,28.72,77.22);
);
out geom 50;
(
  way["landuse"="industrial"](28.60,77.08,28.72,77.22);
  relation["landuse"="industrial"](28.60,77.08,28.72,77.22);
);
out geom 25;
(
  node["amenity"="hospital"](28.60,77.08,28.72,77.22);
  node["amenity"="school"](28.60,77.08,28.72,77.22);
  node["amenity"="clinic"](28.60,77.08,28.72,77.22);
);
out 50;
```

### 2.4 Tag Interpretation & Normalization Whitelist

| Domain | Tag Filter | Normalized Classification | Geometry Type |
|---|---|---|---|
| **Road Corridors** | `highway=motorway`, `highway=trunk` | `freight_corridor` (Rank 5) | `LineString` |
| **Road Corridors** | `highway=primary` | `arterial_road` (Rank 4) | `LineString` |
| **Road Corridors** | `highway=secondary` | `secondary_collector` (Rank 3) | `LineString` |
| **Industrial Zones** | `landuse=industrial` | `manufacturing_zone` | `Polygon` |
| **Sensitive POIs** | `amenity=hospital`, `amenity=clinic` | `HEALTHCARE` | `Point` |
| **Sensitive POIs** | `amenity=school` | `EDUCATION` | `Point` |

**Rule:** Features are classified strictly by verified OSM tags. An entity is never designated "industrial" solely because its name contains the string "industrial".

---

## 3. Municipal Administrative Boundary Ingestion Specification

### 3.1 Sources & Endpoints
- **Provider:** DataMeet Open Spatial Data repository (CC-BY-SA 4.0)
- **Delhi Wards:** `https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Delhi/Delhi_Wards.geojson`
- **Bengaluru BBMP:** `https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Bangalore/BBMP.geojson`

### 3.2 Property Normalization Matrix

| City | Upstream Property | Canonical Standard Property | Description |
|---|---|---|---|
| **Delhi** | `Ward_Name` | `ward_name` | Official MCD ward name (e.g. "MAYAPURI") |
| **Delhi** | `Ward_No` | `ward_no` | Official MCD ward number (e.g. "101") |
| **Delhi** | *Constructed* | `feature_id` | Canonical ID: `geo_ward_delhi_{ward_no}` |
| **Bengaluru** | `KGISWardName` | `ward_name` | Official BBMP ward name (e.g. "Kempegowda Ward") |
| **Bengaluru** | `KGISWardNo` | `ward_no` | Official BBMP ward number (e.g. "1") |
| **Bengaluru** | `KGISWardID` | `source_ward_id` | State GIS numeric ID (e.g. 4878) |
| **Bengaluru** | *Constructed* | `feature_id` | Canonical ID: `geo_ward_bengaluru_{ward_no}` |

All original source properties (e.g. `KGISTownCode`, `KGISWardCode`, `LGD_WardCode`) are preserved verbatim in `source_properties` for full administrative auditability.

---

## 4. Geometric & Spatial Validation Standards

1. **WGS84 Coordinate Reference System (EPSG:4326):** All longitudes must fall in $[-180, 180]$, all latitudes in $[-90, 90]$. Standard coordinate order is strictly `[longitude, latitude]`.
2. **Topological Rules:**
   - `Point`: Array of exactly 2 float coordinates `[lon, lat]`.
   - `LineString`: Array of $\ge 2$ coordinate pairs.
   - `Polygon`: Linear ring of $\ge 4$ coordinate pairs where $	ext{coord}_0 \equiv 	ext{coord}_{-1}$ (closed ring).
3. **Identifier Deduplication:** Features are deduplicated by canonical feature identifier (`geo_{feature_type}_{id}`). Duplicates are detected, rejected from output, and tracked in quality reports.
4. **Defensive Rejection:** Corrupted geometries or features with missing identifiers are rejected with recorded reasons, never silently distorted.

---

## 5. Live Ingestion Verification Results

### 5.1 OpenStreetMap Overpass (Delhi Pilot)
- **Retrieval Mode:** **LIVE VERIFIED** (HTTP 200 OK via `https://overpass-api.de/api/interpreter`)
- **Query Latency:** 29,238 ms (including automatic backoff retry)
- **Raw Elements Returned:** 125
- **Valid Normalized Features:** 125 (100% valid)
  - **Road Corridors:** 50 `LineString` features (arterial and freight roads)
  - **Industrial Zones:** 25 `Polygon` features (manufacturing and scrap clusters)
  - **Sensitive POIs:** 50 `Point` features (hospitals, schools, clinics)
- **Rejected Elements:** 0
- **Computed Bounding Box:** $[28.5967^\circ	ext{N}, 77.0776^\circ	ext{E}]$ to $[28.7176^\circ	ext{N}, 77.2247^\circ	ext{E}]$
- **Attribution:** `? OpenStreetMap contributors (ODbL)`

### 5.2 Delhi Municipal Wards (DataMeet)
- **Retrieval Mode:** **LIVE VERIFIED** (HTTP 200 OK via DataMeet GitHub Raw CDN)
- **Raw Features Ingested:** 290
- **Valid Features:** 289
- **Rejected Features:** 1 (`missing_delhi_ward_identifiers` ? upstream record missing both ward name and number)
- **Geometry Type:** 289 `Polygon` features
- **Computed Bounding Box:** $[28.4043^\circ	ext{N}, 76.8388^\circ	ext{E}]$ to $[28.8835^\circ	ext{N}, 77.3475^\circ	ext{E}]$
- **Attribution:** `DataMeet Municipal Spatial Data (CC-BY-SA 4.0)`

### 5.3 Bengaluru BBMP Wards (DataMeet)
- **Retrieval Mode:** **LIVE VERIFIED** (HTTP 200 OK via DataMeet GitHub Raw CDN)
- **Raw Features Ingested:** 243
- **Valid Features:** 243 (100% valid)
- **Rejected Features:** 0
- **Geometry Type:** 243 `Polygon` features
- **Computed Bounding Box:** $[12.8335^\circ	ext{N}, 77.4599^\circ	ext{E}]$ to $[13.1426^\circ	ext{N}, 77.7844^\circ	ext{E}]$
- **Attribution:** `DataMeet Municipal Spatial Data (CC-BY-SA 4.0)`

---

## 6. Generated Artifacts & File Structure

```
data/
??? raw/
?   ??? osm_delhi_context_20260913_185837.json
?   ??? delhi_wards_raw_20260913_185643.geojson
?   ??? bengaluru_wards_raw_20260913_185644.geojson
??? processed/
    ??? geospatial/
        ??? delhi_roads.geojson                 (50 freight & arterial corridors)
        ??? delhi_industrial_areas.geojson     (25 industrial manufacturing polygons)
        ??? delhi_sensitive_pois.geojson        (50 hospitals, clinics, schools)
        ??? delhi_geospatial_context.geojson    (125 combined context features)
        ??? delhi_wards.geojson                 (289 canonical MCD municipal wards)
        ??? bengaluru_wards.geojson             (243 canonical BBMP municipal wards)
        ??? osm_delhi_quality_report.json
        ??? osm_delhi_quality_report.md
        ??? delhi_wards_quality_report.json
        ??? delhi_wards_quality_report.md
        ??? bengaluru_wards_quality_report.json
        ??? bengaluru_wards_quality_report.md
```

---

## 7. Automated Test Suite

All unit tests execute against offline fixtures in `tests/fixtures/` to guarantee repeatable test execution without network dependency:

| Test Name | Verification Focus | Result |
|---|---|---|
| `test_geojson_schema_and_models` | Pydantic model serialization & canonical fields | **PASSED** |
| `test_coordinate_validation_wgs84` | WGS84 range limits & polygon ring closure | **PASSED** |
| `test_osm_normalizer_supported_tag_filtering` | Whitelist filtering for road, industrial, POI | **PASSED** |
| `test_osm_normalizer_rejections` | Defensive rejection of unsupported tags & missing geoms | **PASSED** |
| `test_delhi_ward_boundary_normalization` | Mapping of Ward_Name/Ward_No & property preservation | **PASSED** |
| `test_bengaluru_ward_boundary_normalization` | Mapping of KGIS fields & source ID preservation | **PASSED** |
| `test_validator_deduplication` | Detection & rejection of duplicate feature IDs | **PASSED** |
| `test_validator_spatial_bounding_box` | Spatial bounding box calculation & filtering | **PASSED** |
| `test_overpass_client_bounded_error_handling` | HTTP 429, 406, and timeout exception handling | **PASSED** |
| `test_boundary_client_error_handling` | Unsupported cities & HTTP 500 handling | **PASSED** |
| `test_geospatial_pipeline_osm_fixture_execution` | Full OSM pipeline run from sanitized fixture | **PASSED** |
| `test_geospatial_pipeline_wards_fixture_execution` | Full wards pipeline run from sanitized fixture | **PASSED** |
| `test_malformed_geojson_rejected` | Malformed GeoJSON and empty geometry rejection | **PASSED** |
| `test_source_attribution_and_metadata_preservation` | RFC 7946 metadata & licensing attribution | **PASSED** |

---

## 8. Limitations & Downstream Consumer Directives

1. **Public Overpass Rate Limits:** Overpass public instances enforce concurrency limits (2 slots per IP). Real-time runtime queries during UI operation are strictly prohibited; runtime modules must consume pre-extracted local GeoJSON artifacts (`data/processed/geospatial/`).
2. **Ward Boundary Granularity:** Municipal wards reflect administrative voting boundaries; they do not correlate 1:1 with micro-climatic atmospheric airsheds.
3. **Downstream Integration:** In Phase 2, these layers will be joined with air quality observations (`EnvironmentalObservation`) and satellite signals (`SatelliteSignal`) via spatial point-in-polygon assignment.
