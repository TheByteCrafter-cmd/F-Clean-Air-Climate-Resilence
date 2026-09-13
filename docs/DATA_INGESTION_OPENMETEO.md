# VayuDrishti Meteorological Ingestion Architecture ? Open-Meteo
## Phase 1E-B Specification: Atmospheric Pipeline, Boundary Layer Inversion, Wind Vectoring & Quality Contracts

**Status:** PHASE 1E-B COMPLETE  
**Project:** VayuDrishti ? Clean Air & Climate Resilience  
**Local Project Root:** `F:\CLEAN AIR & CLIMATE RESILIENCE`  
**Remote Repository:** `https://github.com/TheByteCrafter-cmd/F-Clean-Air-Climate-Resilence.git`  
**Pipeline Version:** `1.0`  
**Pilot Target Reference:** Delhi NCR Pilot Coordinate (`28.6139?N, 77.2090?E`)  

---

## 1. Role of Open-Meteo in VayuDrishti

Meteorological conditions govern pollutant dispersion, dilution, and accumulation across urban terrain. While fixed CAAQMS stations measure surface concentration, they do not explain *why* pollution is trapped or *where* it is transported. Open-Meteo provides the high-resolution, unauthenticated atmospheric data required by VayuDrishti's physical modeling engines.

### Key Atmospheric Phenomena Captured:
1. **Planetary Boundary Layer Height (PBLH / `boundary_layer_height`):**
   - Direct indicator of vertical mixing volume.
   - Shallow boundary layers ($< 250\,\text{m}$) during Delhi winter nights compress surface emissions into a narrow breathing zone, leading to rapid air quality deterioration regardless of source emissions changes.
2. **Plume Advection Vectors ($u, v$ components):**
   - Wind speed and direction dictate the trajectory, travel time, and dilution rate of plumes emitted from industrial clusters and agricultural fires towards downwind residential communities.
3. **Secondary Aerosol Formation Conditions:**
   - High relative humidity ($> 75\%$) accelerates the aqueous-phase oxidation of gaseous $\text{SO}_2$ and $\text{NO}_2$ into secondary ammonium sulfate and nitrate particles.

---

## 2. API Endpoint & Request Parameters

Open-Meteo provides open, zero-authentication public endpoints for non-commercial research and community use under CC-BY 4.0.

- **Base Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Request Method:** `HTTP GET`
- **Authentication:** None required (unauthenticated public API).

### Verified Request Parameters:
| Parameter | Value / Configuration | Purpose |
| :--- | :--- | :--- |
| `latitude` | `28.6139` | Delhi pilot reference center |
| `longitude` | `77.2090` | Delhi pilot reference center |
| `hourly` | `temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m,precipitation,boundary_layer_height` | Required MVP meteorological variables |
| `wind_speed_unit` | `ms` | Direct metric meters per second extraction |
| `timezone` | `UTC` | Unambiguous temporal alignment |
| `forecast_days` | `1` | Controlled 24-hour horizon |

---

## 3. Canonical Units & Unit Standardization

| Variable | Raw Open-Meteo Unit | Canonical Unit | Transformation / Rule |
| :--- | :---: | :---: | :--- |
| **Temperature (`temperature_2m`)** | `?C` | `?C` | Preserved as-is |
| **Relative Humidity (`relative_humidity_2m`)** | `%` | `%` | Bounded strictly $0.0\% \le RH \le 100.0\%$ |
| **Surface Pressure (`surface_pressure`)** | `hPa` | `hPa` | Bounded $800.0 \le P \le 1100.0\,\text{hPa}$ |
| **Wind Speed (`wind_speed_10m`)** | `m/s` | `m/s` | Requested as `ms` directly; if in `km/h`, converted via $\frac{v}{3.6}$ |
| **Wind Direction (`wind_direction_10m`)** | `?` | `degrees` | Normalized to $[0.0^\circ, 360.0^\circ]$ |
| **Precipitation (`precipitation`)** | `mm` | `mm` | Non-negative ($P \ge 0.0$) |
| **Boundary Layer Height (`boundary_layer_height`)** | `m` | `m` | Preserved as `None` if absent; never replaced with 0 |

---

## 4. Meteorological Wind Vector Convention

In meteorology, wind direction $\theta$ is defined as the direction **from which** the wind is blowing, measured clockwise from true north ($0^\circ = \text{North}$, $90^\circ = \text{East}$, $180^\circ = \text{South}$, $270^\circ = \text{West}$).

The velocity vector points in the direction **to which** the air mass moves. VayuDrishti computes the standard Cartesian components:
$$u = - \text{wind\_speed} \times \sin\left(\theta \times \frac{\pi}{180}\right) \quad [\text{Eastward positive, Westward negative}]$$
$$v = - \text{wind\_speed} \times \cos\left(\theta \times \frac{\pi}{180}\right) \quad [\text{Northward positive, Southward negative}]$$

*Examples:*
- **Northerly wind ($	heta = 0^\circ$):** Blowing South $\rightarrow u = 0.0\,\text{m/s}, v = -\text{speed}\,\text{m/s}$.
- **Easterly wind ($	heta = 90^\circ$):** Blowing West $\rightarrow u = -\text{speed}\,\text{m/s}, v = 0.0\,\text{m/s}$.
- **Westerly wind ($	heta = 270^\circ$):** Blowing East $\rightarrow u = +\text{speed}\,\text{m/s}, v = 0.0\,\text{m/s}$.

---

## 5. Timezone & Timestamp Handling

1. **ISO-8601 UTC Standard:** All observation timestamps are normalized to timezone-aware UTC datetime instances.
2. **Deterministic Time Ordering:** Normalized observations are chronologically sorted (`timestamp` ascending) to ensure sequential validity for downstream dispersion engines.
3. **Preservation of Source Metadata:** The raw local timestamp and source timezone (`UTC`) are retained within the `raw_payload` provenance dictionary.

---

## 6. Missing Values Policy

- **No Synthetic Zeroing:** Missing variables are **NEVER** silently substituted with zero. Substituting `0 m` for missing boundary layer height would catastrophically trigger false emergency inversion alerts.
- **Null Preservation:** If optional variables (such as `boundary_layer_height_m`) are unavailable in a model step, they are preserved as `None` / `null` in the canonical observation and recorded in the data quality report.
- **Required Variable Completeness:** If core variables (`temperature`, `humidity`, `pressure`, `wind_speed`, `wind_direction`) are null, the record is flagged as invalid and excluded from the processed stream.

---

## 7. Validation & Deduplication Contracts

### Physical Plausibility Thresholds:
- **Latitude / Longitude:** $-90.0 \le lat \le 90.0$, $-180.0 \le lon \le 180.0$.
- **Temperature:** $-50.0^\circ\text{C} \le T \le 60.0^\circ\text{C}$.
- **Relative Humidity:** $0.0\% \le RH \le 100.0\%$.
- **Surface Pressure:** $800.0\,\text{hPa} \le P \le 1100.0\,\text{hPa}$.
- **Wind Speed:** $0.0 \le ws \le 100.0\,\text{m/s}$.
- **Wind Direction:** $0.0^\circ \le wd \le 360.0^\circ$.

### Deduplication:
Observations are fingerprinted deterministically:
$$\text{Fingerprint} = \text{"weather:"} + \text{lat} + \text{":"} + \text{lon} + \text{":"} + \text{timestamp\_iso}$$
Duplicate observations for identical coordinates and timestamps are excluded from processed outputs and counted in the quality report.

---

## 8. Storage Structure & Formats

All ingestion outputs reside within the locked project directory:

```
data/
??? raw/
?   ??? open_meteo_delhi_sample_<timestamp>.json     # Complete upstream API JSON response
??? processed/
    ??? open_meteo_delhi_weather_<timestamp>.jsonl   # Canonical WeatherObservation records
    ??? open_meteo_delhi_weather_report_<timestamp>.json # Machine-readable quality metrics
    ??? open_meteo_delhi_weather_report_<timestamp>.md   # Human-readable quality report
```

### Canonical `WeatherObservation` JSONL Line Format:
```json
{
  "weather_id": "weather-om-28.5764-77.1868-202609131200",
  "timestamp": "2026-09-13T12:00:00Z",
  "location": {
    "latitude": 28.5764,
    "longitude": 77.1868,
    "address": "Delhi NCR Pilot Reference"
  },
  "temperature_c": 31.1,
  "relative_humidity_pct": 67.0,
  "surface_pressure_hpa": 983.2,
  "wind_speed_ms": 2.42,
  "wind_direction_deg": 68.0,
  "precipitation_mm": 0.0,
  "boundary_layer_height_m": 945.0,
  "wind_u_ms": -2.244,
  "wind_v_ms": -0.907,
  "source": "Open-Meteo",
  "retrieved_at": "2026-09-13T18:16:18Z",
  "source_url": "https://api.open-meteo.com/v1/forecast",
  "normalization_version": "1.0",
  "raw_payload": { ... }
}
```

---

## 9. Command-Line Usage

The pipeline can be executed directly from the terminal via `scripts/ingest_weather.py`:

```bash
# Live Open-Meteo fetch for Delhi pilot reference (default behavior)
python scripts/ingest_weather.py --live --days 1

# Offline verification run using sanitized fixture
python scripts/ingest_weather.py --fixture tests/fixtures/open_meteo_delhi_sample.json

# Custom geographic coordinate query
python scripts/ingest_weather.py --live --latitude 28.6476 --longitude 77.3158 --days 1
```

---

## 10. Live Verification vs. Unit Tested Distinction

| Component | Status | Empirical Result / Notes |
| :--- | :---: | :--- |
| **Open-Meteo Public HTTP Access** | **LIVE VERIFIED** | HTTP 200 OK in ~280ms, zero authentication required. |
| **Hourly Variable Retrieval** | **LIVE VERIFIED** | Returned 24 hourly steps with temperature, humidity, pressure, wind speed, wind direction, and boundary layer height. |
| **Direct m/s Wind Speed Request** | **LIVE VERIFIED** | Confirmed `wind_speed_unit=ms` natively honored. |
| **Unit Normalization & Vector Math** | **UNIT TESTED** | 100% test coverage for Cartesian components, km/h $\rightarrow$ m/s. |
| **Boundary Audits & Deduplication** | **UNIT TESTED** | Tested rejection of negative humidity, extreme pressure, duplicate steps. |
| **Full Offline Pipeline Execution** | **UNIT TESTED** | Verified end-to-end fixture execution to `.jsonl` and reports. |

---

## 11. Test Execution Results

Total test suite: **30/30 passed** across the entire project:
- `10/10` Phase 1B API Contract Tests (`test_api_contracts.py`)
- `10/10` Phase 1E-A OpenAQ Ingestion Tests (`test_openaq_ingestion.py`)
- `10/10` Phase 1E-B Open-Meteo Weather Ingestion Tests (`test_weather_ingestion.py`)

---

## 12. Known Limitations & Downstream Phase Guidance

1. **Grid Resolution:** Open-Meteo provides atmospheric reanalysis at $1 - 11\,\text{km}$ grid resolution. Street-level micro-climates (e.g. urban street canyons in Old Delhi) require localized empirical adjustments.
2. **Forecast Drift:** Forecasted boundary layer heights beyond 48 hours have wider confidence intervals. The pipeline refreshes on an hourly/daily basis.
3. **No Hotspot or Plume Dispersion in Phase 1E-B:** Weather observations are strictly ingested and validated in this phase; dispersion cone calculation and ML feature engineering belong to Phase 2 and Phase 3.
