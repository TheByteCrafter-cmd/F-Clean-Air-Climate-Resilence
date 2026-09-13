# Geospatial Ingestion Quality Report: OPENSTREETMAP_OVERPASS

**Generated At (UTC):** 2026-09-13T18:58:37.021968+00:00  
**Source Endpoint:** `https://overpass-api.de/api/interpreter`  
**Response Latency:** 29238 ms  
**Coordinate Reference System:** EPSG:4326 (WGS84)  
**Licensing & Attribution:** ODbL ? *? OpenStreetMap contributors*  

---

## 1. Feature Ingestion Summary

| Metric | Value |
|---|---|
| **Raw Objects Ingested** | 125 |
| **Valid Canonical Features** | 125 |
| **Rejected Objects** | 0 |
| **Duplicate Identifiers** | 0 |
| **Computed Bounding Box (WGS84)** | [28.5967, 77.0776] to [28.7176, 77.2247] |

---

## 2. Geometry & Category Distribution

* **Geometry Types:** LineString: 50, Polygon: 25, Point: 50
* **Feature Categories:** road: 50, industrial: 25, sensitive_receptor: 50
* **Rejection Breakdown:** None

---

## 3. Provenance & Compliance

- **Storage Format:** Valid GeoJSON RFC 7946 FeatureCollection
- **Geodetic Standard:** WGS84 (EPSG:4326)
- **Scientific Boundary:** Pure geospatial context; NO spatial inference, hotspot modeling, or pollution interpolation applied.
