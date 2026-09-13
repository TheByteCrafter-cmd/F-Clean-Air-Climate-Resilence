# Sentinel-5P TROPOMI Tropospheric NO2 Ingestion Quality Report

**Dataset ID:** `COPERNICUS/S5P/NRTI/L3_NO2`  
**Primary Band:** `tropospheric_NO2_column_number_density`  
**Unit:** `mol/m?`  
**Retrieval Mode:** `OFFLINE_FIXTURE`  
**GEE Authentication:** `GEE RUNTIME ACCESS NOT CONFIGURED`  
**Retrieval Time:** 2026-09-13 18:38:15 UTC  
**Region of Interest (ROI):** Lat [28.4, 28.85], Lon [76.9, 77.35]  

## Summary Statistics

| Metric | Value |
| :--- | :--- |
| **Total Samples Received** | 11 |
| **Samples Retained (Valid & Clear)** | 6 |
| **Samples Rejected** | 5 |
| **Duplicates Filtered** | 1 |
| **Out-of-ROI Filtered** | 1 |
| **Cloud Obscured (Rejected)** | 1 |
| **Negative Values Preserved (Noise)** | 1 |
| **Validity Rate** | 54.5% |

## Spatio-Temporal Window

* **Geographic Extent:** Lat [28.5284, 28.7800], Lon [77.0200, 77.3152]
* **Acquisition Time Window:** 2026-09-12T08:00:00+00:00 to 2026-09-12T08:00:00+00:00

## Atmospheric Column Density (mol/m?)

* **Tropospheric NO2:** Min: -0.000015 mol/m? (-15.00 ?mol/m?), Max: 0.000285 mol/m? (285.00 ?mol/m?), Mean: 0.000157 mol/m? (157.00 ?mol/m?)
* **Cloud Fraction:** Min: 0.10, Max: 0.35, Mean: 0.21

## Quality Level Distribution
- **HIGH:** 5 samples
- **NOMINAL:** 1 samples

## Rejection Breakdown

- `Cloud fraction 0.72 exceeds threshold 0.5`: 1
- `Duplicate signal identity`: 1
- `Outside target Region of Interest (ROI)`: 1
- `Unphysical negative tropospheric NO2 anomaly (-0.000500 mol/m? < -0.0001)`: 1
- `Missing latitude or longitude coordinate`: 1

## Scientific Integrity Note

1. **Vertical Column != Ground Level:** Sentinel-5P measures total integrated moles of NO2 per square meter across the tropospheric column. It does NOT measure breathing-zone concentration (?g/m?) or PM2.5.
2. **Negative Value Preservation:** DOAS spectral fitting noise yields small negative values over clean air. Clamping these to zero causes systematic positive bias; they are retained for spatial averaging.
3. **Overpass Frequency:** Single daily overpass (~13:30 local time); does not capture rush-hour or nocturnal peaks.

---
*Report generated deterministically by VayuDrishti Sentinel-5P Ingestion Engine.*
