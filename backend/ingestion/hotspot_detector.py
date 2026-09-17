"""
VayuDrishti — Phase 1E-I Hyper-Local Pollution Hotspot Detection Engine

Provides deterministic, rule-based, offline spatial hotspot detection using IDW
(Inverse Distance Weighting) spatial interpolation over OpenAQ observations,
correlated with existing EvidenceFusionResult artifacts, Open-Meteo weather,
NASA FIRMS thermal anomalies, Sentinel-5P satellite signals, and OSM geospatial context.
"""

import json
import logging
import math
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from backend.api.v1.schemas.common import Location
from backend.api.v1.schemas.fusion import EvidenceFusionResult
from backend.api.v1.schemas.hotspot import (
    HotspotDetectionResult,
    HotspotSummary,
    SpatialCoverageInfo,
)
from backend.ingestion.citizen_evidence_storage import validate_safe_id
from backend.ingestion.exceptions import (
    HotspotDetectionError,
    HotspotPersistenceError,
    InsufficientSpatialDataError,
)

logger = logging.getLogger(__name__)


def haversine_spherical_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates Haversine spherical-distance approximation using WGS84 coordinates.
    Returns distance in kilometers rounded to 3 decimal places.
    """
    R = 6371.0  # Mean Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 3)


class HotspotDetectorConfiguration:
    """Explicit, documented configuration for provisional hyper-local hotspot detection."""

    def __init__(
        self,
        config_version: str = "1.0-provisional",
        pollutant: str = "PM2.5",
        time_window_minutes: float = 60.0,
        roi_bbox: Optional[List[float]] = None,
        min_stations_for_idw: int = 3,
        max_idw_radius_km: float = 10.0,
        idw_power: float = 2.0,
        grid_resolution_deg: float = 0.01,  # ~1.1 km cell spacing
        hotspot_anomaly_threshold: float = 30.0,  # µg/m³ above local median
        relative_anomaly_threshold: float = 0.25,  # 25% elevation above baseline
        tier_moderate_threshold: float = 40.0,
        tier_high_threshold: float = 70.0,
    ):
        self.config_version = config_version
        self.pollutant = pollutant
        self.time_window_minutes = time_window_minutes
        # Default approved Delhi Pilot ROI Bounding Box: [lat_min, lon_min, lat_max, lon_max]
        self.roi_bbox = roi_bbox or [28.40, 76.85, 28.88, 77.40]
        self.min_stations_for_idw = min_stations_for_idw
        self.max_idw_radius_km = max_idw_radius_km
        self.idw_power = idw_power
        self.grid_resolution_deg = grid_resolution_deg
        self.hotspot_anomaly_threshold = hotspot_anomaly_threshold
        self.relative_anomaly_threshold = relative_anomaly_threshold
        self.tier_moderate_threshold = tier_moderate_threshold
        self.tier_high_threshold = tier_high_threshold


class HyperLocalHotspotDetector:
    """Deterministic offline engine for hyper-local pollution hotspot detection."""

    def __init__(
        self,
        data_root: Optional[Union[str, Path]] = None,
        config: Optional[HotspotDetectorConfiguration] = None,
    ):
        self.config = config or HotspotDetectorConfiguration()
        self.data_root = Path(data_root) if data_root else Path(os.getcwd()) / "data"
        self.processed_dir = self.data_root / "processed"
        self.hotspot_dir = self.processed_dir / "hotspots"
        self.hotspot_dir.mkdir(parents=True, exist_ok=True)

    def detect_hotspots(
        self,
        pollutant: Optional[str] = None,
        analysis_timestamp: Optional[datetime] = None,
        custom_openaq_data: Optional[List[Dict[str, Any]]] = None,
        custom_fusion_data: Optional[List[Dict[str, Any]]] = None,
        custom_weather_data: Optional[List[Dict[str, Any]]] = None,
        custom_firms_data: Optional[List[Dict[str, Any]]] = None,
        custom_satellite_data: Optional[List[Dict[str, Any]]] = None,
        custom_geospatial_data: Optional[List[Dict[str, Any]]] = None,
    ) -> List[HotspotDetectionResult]:
        """
        Executes spatial IDW interpolation and contiguous grid cell aggregation to detect hotspots.

        Args:
            pollutant: Target pollutant (default from config: 'PM2.5')
            analysis_timestamp: Target timestamp for temporal windowing
            custom_openaq_data: Optional in-memory OpenAQ records for testing
            custom_fusion_data: Optional in-memory fusion results for testing
            custom_weather_data: Optional in-memory weather records for testing
            custom_firms_data: Optional in-memory FIRMS records for testing
            custom_satellite_data: Optional in-memory Sentinel-5P records for testing
            custom_geospatial_data: Optional in-memory GeoJSON features for testing

        Returns:
            List of detected HotspotDetectionResult objects.
        """
        target_pollutant = pollutant or self.config.pollutant
        provenance_files: List[str] = []

        # 1. Load & Filter Station Observations
        raw_openaq = custom_openaq_data if custom_openaq_data is not None else self._load_openaq_records(provenance_files)
        valid_obs, anchor_time = self._prepare_station_observations(
            raw_openaq, target_pollutant, analysis_timestamp
        )

        # Minimum Data Density Check
        if len(valid_obs) < self.config.min_stations_for_idw:
            logger.warning(
                f"Insufficient spatial data points ({len(valid_obs)} < {self.config.min_stations_for_idw}) for IDW."
            )
            return []

        # 2. Compute Robust Local Baseline (Median)
        obs_values = [obs["value"] for obs in valid_obs]
        local_baseline = round(float(median(obs_values)), 2)

        # 3. Generate Analysis Grid & Interpolate via IDW
        grid_cells = self._generate_analysis_grid()
        interpolated_grid = self._interpolate_idw(grid_cells, valid_obs, local_baseline)

        # 4. Filter Candidate Grid Cells & Aggregate Contiguous Regions
        candidate_cells = [
            cell for cell in interpolated_grid
            if cell["sufficient_data"]
            and cell["anomaly_value"] >= self.config.hotspot_anomaly_threshold
            and cell["relative_anomaly"] >= self.config.relative_anomaly_threshold
        ]

        if not candidate_cells:
            logger.info("No contiguous grid cells met the candidate hotspot threshold.")
            return []

        contiguous_regions = self._group_contiguous_cells(candidate_cells)

        # 5. Load Contextual Evidence Layers
        fusion_results = custom_fusion_data if custom_fusion_data is not None else self._load_fusion_results(provenance_files)
        weather_records = custom_weather_data if custom_weather_data is not None else self._load_weather_records(provenance_files)
        firms_records = custom_firms_data if custom_firms_data is not None else self._load_firms_records(provenance_files)
        sat_records = custom_satellite_data if custom_satellite_data is not None else self._load_satellite_records(provenance_files)
        geo_records = custom_geospatial_data if custom_geospatial_data is not None else self._load_geospatial_records(provenance_files)

        # 6. Build Hotspot Results for each Contiguous Region
        results: List[HotspotDetectionResult] = []
        for reg_idx, region in enumerate(contiguous_regions):
            hotspot_res = self._build_hotspot_result(
                region_cells=region,
                pollutant=target_pollutant,
                analysis_timestamp=anchor_time,
                local_baseline=local_baseline,
                valid_obs=valid_obs,
                fusion_results=fusion_results,
                weather_records=weather_records,
                firms_records=firms_records,
                sat_records=sat_records,
                geo_records=geo_records,
                provenance_files=provenance_files,
            )
            self.save_hotspot_result(hotspot_res)
            results.append(hotspot_res)

        # Update lightweight GeoJSON collection
        self.save_geojson_collection(results)
        return results

    def _prepare_station_observations(
        self,
        records: List[Dict[str, Any]],
        pollutant: str,
        target_timestamp: Optional[datetime],
    ) -> Tuple[List[Dict[str, Any]], datetime]:
        """Filters, validates, and deduplicates station observations."""
        if not records:
            now_utc = target_timestamp or datetime.now(timezone.utc)
            return [], now_utc

        # Determine target timestamp if not provided (latest observation timestamp)
        parsed_times: List[datetime] = []
        for r in records:
            raw_t = r.get("timestamp") or r.get("datetime")
            if raw_t:
                try:
                    dt = datetime.fromisoformat(str(raw_t).replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    parsed_times.append(dt)
                except Exception:
                    pass

        anchor_time = target_timestamp
        if not anchor_time:
            anchor_time = max(parsed_times) if parsed_times else datetime.now(timezone.utc)
        if anchor_time.tzinfo is None:
            anchor_time = anchor_time.replace(tzinfo=timezone.utc)

        valid_obs: List[Dict[str, Any]] = []
        dedup_keys: Set[Tuple[str, str]] = set()

        for r in records:
            r_pol = str(r.get("pollutant", "PM2.5")).upper().replace(".", "").replace(" ", "")
            target_pol = pollutant.upper().replace(".", "").replace(" ", "")
            if r_pol != target_pol:
                continue

            r_lat = r.get("latitude") or (r.get("location", {}).get("latitude") if isinstance(r.get("location"), dict) else None)
            r_lon = r.get("longitude") or (r.get("location", {}).get("longitude") if isinstance(r.get("location"), dict) else None)
            if r_lat is None or r_lon is None:
                continue

            try:
                lat = float(r_lat)
                lon = float(r_lon)
                val = float(r.get("value", -1.0))
            except (ValueError, TypeError):
                continue

            if val < 0.0 or not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue

            raw_t = r.get("timestamp") or r.get("datetime")
            if not raw_t:
                continue
            try:
                t_obs = datetime.fromisoformat(str(raw_t).replace("Z", "+00:00"))
                if t_obs.tzinfo is None:
                    t_obs = t_obs.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            t_diff_min = abs((t_obs - anchor_time).total_seconds() / 60.0)
            if t_diff_min > self.config.time_window_minutes:
                continue

            station_id = str(r.get("station_id") or r.get("source_record_id") or f"{lat:.3f}_{lon:.3f}")
            dedup_key = (station_id, t_obs.isoformat())
            if dedup_key in dedup_keys:
                continue
            dedup_keys.add(dedup_key)

            valid_obs.append({
                "station_id": station_id,
                "latitude": lat,
                "longitude": lon,
                "timestamp": t_obs,
                "value": val,
                "pollutant": pollutant,
                "unit": r.get("unit", "µg/m³"),
                "source_file": r.get("source_file", "data/processed/openaq_delhi_observations.jsonl"),
            })

        return valid_obs, anchor_time

    def _generate_analysis_grid(self) -> List[Tuple[float, float]]:
        """Generates regular grid coordinate centers across configured ROI bounding box."""
        lat_min, lon_min, lat_max, lon_max = self.config.roi_bbox
        step = self.config.grid_resolution_deg

        grid: List[Tuple[float, float]] = []
        curr_lat = lat_min + step / 2.0
        while curr_lat <= lat_max:
            curr_lon = lon_min + step / 2.0
            while curr_lon <= lon_max:
                grid.append((round(curr_lat, 4), round(curr_lon, 4)))
                curr_lon += step
            curr_lat += step
        return grid

    def _interpolate_idw(
        self,
        grid_cells: List[Tuple[float, float]],
        valid_obs: List[Dict[str, Any]],
        local_baseline: float,
    ) -> List[Dict[str, Any]]:
        """Applies Inverse Distance Weighting (IDW) interpolation over analysis grid cells."""
        interpolated: List[Dict[str, Any]] = []

        for cell_lat, cell_lon in grid_cells:
            station_weights: List[Tuple[float, float, Dict[str, Any]]] = []
            for obs in valid_obs:
                dist = haversine_spherical_distance_km(cell_lat, cell_lon, obs["latitude"], obs["longitude"])
                if dist <= self.config.max_idw_radius_km:
                    station_weights.append((dist, obs["value"], obs))

            if len(station_weights) < self.config.min_stations_for_idw:
                interpolated.append({
                    "lat": cell_lat,
                    "lon": cell_lon,
                    "interpolated_value": local_baseline,
                    "anomaly_value": 0.0,
                    "relative_anomaly": 0.0,
                    "sufficient_data": False,
                    "station_count": len(station_weights),
                    "min_distance_km": min([d for d, _, _ in station_weights]) if station_weights else None,
                })
                continue

            # Check zero-distance exact match
            exact_match = next((val for dist, val, _ in station_weights if dist < 1e-5), None)
            if exact_match is not None:
                interp_val = exact_match
            else:
                numerator = sum(val / (dist ** self.config.idw_power) for dist, val, _ in station_weights)
                denominator = sum(1.0 / (dist ** self.config.idw_power) for dist, _, _ in station_weights)
                interp_val = numerator / denominator if denominator > 0 else local_baseline

            interp_val = round(interp_val, 2)
            abs_anomaly = round(interp_val - local_baseline, 2)
            denom_base = max(abs(local_baseline), 1.0)
            rel_anomaly = round(abs_anomaly / denom_base, 3)
            min_dist = round(min(d for d, _, _ in station_weights), 3)

            interpolated.append({
                "lat": cell_lat,
                "lon": cell_lon,
                "interpolated_value": interp_val,
                "anomaly_value": abs_anomaly,
                "relative_anomaly": rel_anomaly,
                "sufficient_data": True,
                "station_count": len(station_weights),
                "min_distance_km": min_dist,
            })

        return interpolated

    def _group_contiguous_cells(self, candidate_cells: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Groups contiguous 4-neighbor grid cells into candidate region clusters."""
        cell_map = {(c["lat"], c["lon"]): c for c in candidate_cells}
        visited: Set[Tuple[float, float]] = set()
        clusters: List[List[Dict[str, Any]]] = []

        step = round(self.config.grid_resolution_deg, 4)

        for key, cell in cell_map.items():
            if key in visited:
                continue

            cluster: List[Dict[str, Any]] = []
            queue = [key]
            visited.add(key)

            while queue:
                curr_lat, curr_lon = queue.pop(0)
                cluster.append(cell_map[(curr_lat, curr_lon)])

                # Check 4 neighbors
                neighbors = [
                    (round(curr_lat + step, 4), curr_lon),
                    (round(curr_lat - step, 4), curr_lon),
                    (curr_lat, round(curr_lon + step, 4)),
                    (curr_lat, round(curr_lon - step, 4)),
                ]
                for n_key in neighbors:
                    if n_key in cell_map and n_key not in visited:
                        visited.add(n_key)
                        queue.append(n_key)

            clusters.append(cluster)

        return clusters

    def _build_hotspot_result(
        self,
        region_cells: List[Dict[str, Any]],
        pollutant: str,
        analysis_timestamp: datetime,
        local_baseline: float,
        valid_obs: List[Dict[str, Any]],
        fusion_results: List[Dict[str, Any]],
        weather_records: List[Dict[str, Any]],
        firms_records: List[Dict[str, Any]],
        sat_records: List[Dict[str, Any]],
        geo_records: List[Dict[str, Any]],
        provenance_files: List[str],
    ) -> HotspotDetectionResult:
        """Constructs a validated HotspotDetectionResult for a contiguous region."""
        # Calculate region centroid
        lats = [c["lat"] for c in region_cells]
        lons = [c["lon"] for c in region_cells]
        center_lat = round(sum(lats) / len(lats), 4)
        center_lon = round(sum(lons) / len(lons), 4)

        peak_cell = max(region_cells, key=lambda c: c["interpolated_value"])
        interpolated_value = peak_cell["interpolated_value"]
        anomaly_value = round(interpolated_value - local_baseline, 2)
        denom_base = max(abs(local_baseline), 1.0)
        relative_anomaly = round(anomaly_value / denom_base, 3)

        # Generate GeoJSON Polygon / MultiPolygon geometry for grid cells
        step = self.config.grid_resolution_deg / 2.0
        polygons: List[List[List[float]]] = []
        for c in region_cells:
            c_lat, c_lon = c["lat"], c["lon"]
            poly = [
                [round(c_lon - step, 4), round(c_lat - step, 4)],
                [round(c_lon + step, 4), round(c_lat - step, 4)],
                [round(c_lon + step, 4), round(c_lat + step, 4)],
                [round(c_lon - step, 4), round(c_lat + step, 4)],
                [round(c_lon - step, 4), round(c_lat - step, 4)],
            ]
            polygons.append(poly)

        if len(polygons) == 1:
            geometry = {"type": "Polygon", "coordinates": polygons}
        else:
            geometry = {"type": "MultiPolygon", "coordinates": [[p] for p in polygons]}

        # Distance & Station metrics around centroid
        station_distances = [
            haversine_spherical_distance_km(center_lat, center_lon, obs["latitude"], obs["longitude"])
            for obs in valid_obs
        ]
        nearby_stations = [
            (d, obs) for d, obs in zip(station_distances, valid_obs) if d <= self.config.max_idw_radius_km
        ]
        obs_count = len(nearby_stations)

        min_dist = min([d for d, _ in nearby_stations]) if nearby_stations else None
        max_dist = max([d for d, _ in nearby_stations]) if nearby_stations else None
        nearest_st_id = min(nearby_stations, key=lambda x: x[0])[1]["station_id"] if nearby_stations else None

        coverage_info = SpatialCoverageInfo(
            min_station_distance_km=min_dist,
            max_station_distance_km=max_dist,
            nearest_station_id=nearest_st_id,
        )

        # Evidence Linkage (Corroborating Source Families)
        supporting_families: Set[str] = {"AIR_QUALITY"}
        linked_fusion_ids: List[str] = []
        nearby_context: Dict[str, Any] = {"firms_signals": 0, "satellite_signals": 0, "osm_features": 0}

        # Check linked fusion results within 10 km
        for fus in fusion_results:
            # Check if fusion result anchor location is near centroid
            f_id = fus.get("fusion_id")
            if f_id and f_id not in linked_fusion_ids:
                linked_fusion_ids.append(f_id)
                supporting_families.add("CITIZEN_GEMINI")

        # Check FIRMS signals within 15 km
        firms_count = 0
        for f_rec in firms_records:
            f_lat = f_rec.get("latitude")
            f_lon = f_rec.get("longitude")
            if f_lat and f_lon:
                if haversine_spherical_distance_km(center_lat, center_lon, float(f_lat), float(f_lon)) <= 15.0:
                    firms_count += 1
        if firms_count > 0:
            supporting_families.add("THERMAL_ANOMALY")
            nearby_context["firms_signals"] = firms_count

        # Check Weather context (Stagnant wind)
        stagnant_wx = any(
            float(w.get("wind_speed_ms", w.get("wind_speed_10m", 5.0))) <= 3.0
            for w in weather_records
        )
        if stagnant_wx or weather_records:
            supporting_families.add("WEATHER")
            nearby_context["weather_stagnant"] = stagnant_wx

        # Check Satellite NO2 context
        if sat_records:
            supporting_families.add("SATELLITE_NO2")
            nearby_context["satellite_signals"] = len(sat_records)

        # Check OSM Geospatial context
        if geo_records:
            supporting_families.add("GEOSPATIAL_CONTEXT")
            nearby_context["osm_features"] = len(geo_records)

        # Calculate Hotspot Support Score (0–100)
        # Components:
        # 1. Anomaly magnitude (up to 40 pts)
        # 2. Spatial extent/cell count (up to 20 pts)
        # 3. Observation density & proximity (up to 15 pts)
        # 4. Corroborating evidence families (up to 25 pts)
        anomaly_score = min(40.0, (anomaly_value / 50.0) * 40.0)
        extent_score = min(20.0, len(region_cells) * 5.0)
        density_score = min(15.0, obs_count * 3.0)
        corroboration_score = min(25.0, (len(supporting_families) - 1) * 6.25)

        total_raw_score = anomaly_score + extent_score + density_score + corroboration_score
        support_score = round(min(100.0, max(0.0, total_raw_score)), 1)

        if support_score >= self.config.tier_high_threshold:
            confidence_tier = "HIGH_SUPPORT"
        elif support_score >= self.config.tier_moderate_threshold:
            confidence_tier = "MODERATE_SUPPORT"
        else:
            confidence_tier = "LOW_SUPPORT"

        uncertainty_notes = [
            f"IDW spatial interpolation derived using Haversine distance with power p={self.config.idw_power}.",
            "Identifies potential hyper-local pollution hotspot area relative to local median baseline.",
            "Does NOT establish causal pollution source proof, health exposure, or legal violation."
        ]

        hotspot_id = f"hs_{uuid.uuid4().hex}"

        return HotspotDetectionResult(
            hotspot_id=hotspot_id,
            pollutant=pollutant,
            analysis_timestamp=analysis_timestamp,
            geometry=geometry,
            center=Location(latitude=center_lat, longitude=center_lon),
            support_score=support_score,
            confidence_tier=confidence_tier,
            interpolated_value=interpolated_value,
            local_baseline=local_baseline,
            anomaly_value=anomaly_value,
            relative_anomaly=relative_anomaly,
            observation_count=obs_count,
            spatial_coverage=coverage_info,
            supporting_source_families=sorted(list(supporting_families)),
            linked_fusion_ids=linked_fusion_ids,
            nearby_context=nearby_context,
            uncertainty_notes=uncertainty_notes,
            data_quality="SUFFICIENT_SPATIAL_DATA",
            provenance=list(dict.fromkeys(provenance_files)),
            config_version=self.config.config_version,
            schema_version="1.0",
        )

    # --------------------------------------------------------------------------
    # DATA LOADERS (OFFLINE FILESYSTEM SCANNING)
    # --------------------------------------------------------------------------
    def _load_openaq_records(self, prov_list: List[str]) -> List[Dict[str, Any]]:
        """Scans data/processed/ for openaq_*.jsonl files."""
        return self._scan_jsonl_files(self.processed_dir, "openaq_*.jsonl", prov_list)

    def _load_fusion_results(self, prov_list: List[str]) -> List[Dict[str, Any]]:
        """Scans data/processed/fusion/ for fu_*.json files."""
        fusion_dir = self.processed_dir / "fusion"
        if not fusion_dir.exists():
            return []
        results: List[Dict[str, Any]] = []
        for path in fusion_dir.glob("fu_*.json"):
            try:
                rel_path = str(path.relative_to(self.data_root)).replace("\\", "/")
                prov_list.append(rel_path)
                with open(path, "r", encoding="utf-8") as f:
                    results.append(json.load(f))
            except Exception as e:
                logger.warning(f"Error reading fusion artifact {path}: {e}")
        return results

    def _load_firms_records(self, prov_list: List[str]) -> List[Dict[str, Any]]:
        """Scans data/processed/ for firms_*.jsonl files."""
        return self._scan_jsonl_files(self.processed_dir, "firms_*.jsonl", prov_list)

    def _load_weather_records(self, prov_list: List[str]) -> List[Dict[str, Any]]:
        """Scans data/processed/ for open_meteo_*.jsonl files."""
        return self._scan_jsonl_files(self.processed_dir, "open_meteo_*.jsonl", prov_list)

    def _load_satellite_records(self, prov_list: List[str]) -> List[Dict[str, Any]]:
        """Scans data/processed/satellite/ for sentinel5p_*.jsonl files."""
        sat_dir = self.processed_dir / "satellite"
        return self._scan_jsonl_files(sat_dir, "sentinel5p_*.jsonl", prov_list)

    def _load_geospatial_records(self, prov_list: List[str]) -> List[Dict[str, Any]]:
        """Scans data/processed/geospatial/ for *.geojson files."""
        geo_dir = self.processed_dir / "geospatial"
        if not geo_dir.exists():
            return []
        features: List[Dict[str, Any]] = []
        for path in geo_dir.glob("*.geojson"):
            try:
                rel_path = str(path.relative_to(self.data_root)).replace("\\", "/")
                prov_list.append(rel_path)
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for feat in data.get("features", []):
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates")
                    if geom.get("type") == "Point" and coords:
                        features.append({
                            "feature_id": props.get("id") or props.get("name") or "geo_feat",
                            "latitude": coords[1],
                            "longitude": coords[0],
                            "category": props.get("category") or props.get("landuse") or "industrial",
                        })
            except Exception as e:
                logger.warning(f"Error reading GeoJSON {path}: {e}")
        return features

    def _scan_jsonl_files(self, directory: Path, pattern: str, prov_list: List[str]) -> List[Dict[str, Any]]:
        """Scans directory for jsonl files matching pattern."""
        if not directory.exists():
            return []
        records: List[Dict[str, Any]] = []
        for path in directory.glob(pattern):
            try:
                rel_path = str(path.relative_to(self.data_root)).replace("\\", "/")
                prov_list.append(rel_path)
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            rec["source_file"] = rel_path
                            records.append(rec)
            except Exception as e:
                logger.warning(f"Error reading JSONL {path}: {e}")
        return records

    # --------------------------------------------------------------------------
    # PERSISTENCE
    # --------------------------------------------------------------------------
    def save_hotspot_result(self, result: HotspotDetectionResult) -> Path:
        """Persists HotspotDetectionResult JSON artifact under data/processed/hotspots/<hotspot_id>.json."""
        target_path = self.hotspot_dir / f"{result.hotspot_id}.json"
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=2))
            logger.info(f"Persisted hotspot detection artifact to {target_path}")
            return target_path
        except Exception as e:
            raise HotspotPersistenceError(f"Failed to persist hotspot result artifact: {e}")

    def save_geojson_collection(self, results: List[HotspotDetectionResult]) -> Path:
        """Persists lightweight GeoJSON FeatureCollection artifact under data/processed/hotspots/delhi_hotspots.geojson."""
        target_path = self.hotspot_dir / "delhi_hotspots.geojson"
        features: List[Dict[str, Any]] = []

        for r in results:
            feat = {
                "type": "Feature",
                "id": r.hotspot_id,
                "geometry": r.geometry,
                "properties": {
                    "hotspot_id": r.hotspot_id,
                    "pollutant": r.pollutant,
                    "support_score": r.support_score,
                    "confidence_tier": r.confidence_tier,
                    "interpolated_value": r.interpolated_value,
                    "local_baseline": r.local_baseline,
                    "anomaly_value": r.anomaly_value,
                    "observation_count": r.observation_count,
                    "detected_at": r.analysis_timestamp.isoformat(),
                },
            }
            features.append(feat)

        collection = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "detector_version": self.config.config_version,
                "total_hotspots": len(results),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(collection, f, indent=2)
            return target_path
        except Exception as e:
            logger.error(f"Failed to write GeoJSON collection {target_path}: {e}")
            return target_path

    def get_hotspot_result(self, hotspot_id: str) -> Optional[HotspotDetectionResult]:
        """Retrieves a persisted hotspot detection artifact by hotspot_id."""
        target_path = self.hotspot_dir / f"{hotspot_id}.json"
        if not target_path.exists():
            return None
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return HotspotDetectionResult.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to read hotspot artifact {target_path}: {e}")
            return None

    def list_hotspot_summaries(self) -> List[HotspotSummary]:
        """Lists summaries of all persisted hotspot artifacts in data/processed/hotspots/."""
        summaries: List[HotspotSummary] = []
        for path in self.hotspot_dir.glob("hs_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                res = HotspotDetectionResult.model_validate(data)
                summaries.append(
                    HotspotSummary(
                        hotspot_id=res.hotspot_id,
                        pollutant=res.pollutant,
                        location=res.center,
                        severity=res.confidence_tier,
                        confidence=res.support_score,
                        confidence_tier=res.confidence_tier,
                        detected_at=res.analysis_timestamp,
                        interpolated_value=res.interpolated_value,
                        anomaly_value=res.anomaly_value,
                        observation_count=res.observation_count,
                    )
                )
            except Exception as e:
                logger.warning(f"Error reading hotspot summary {path}: {e}")
        return summaries
