import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.api.v1.schemas.geospatial import GeoJSONFeature, GeospatialMetadata

logger = logging.getLogger(__name__)


def validate_coordinates(coords: Any, geom_type: str) -> Tuple[bool, Optional[str]]:
    """Validates that coordinates conform to WGS84 EPSG:4326 ranges and GeoJSON standards.
    
    Lon in [-180, 180], Lat in [-90, 90].
    """
    if geom_type == "Point":
        if not (isinstance(coords, (list, tuple)) and len(coords) >= 2):
            return False, "Point coordinate must be [lon, lat]"
        lon, lat = coords[0], coords[1]
        if not (-180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0):
            return False, f"Point coordinates out of WGS84 bounds: lon={lon}, lat={lat}"
        return True, None

    elif geom_type == "LineString":
        if not (isinstance(coords, (list, tuple)) and len(coords) >= 2):
            return False, "LineString must have at least 2 coordinate pairs"
        for pt in coords:
            if not (isinstance(pt, (list, tuple)) and len(pt) >= 2):
                return False, f"Invalid point in LineString: {pt}"
            if not (-180.0 <= pt[0] <= 180.0 and -90.0 <= pt[1] <= 90.0):
                return False, f"LineString point out of WGS84 bounds: {pt}"
        return True, None

    elif geom_type == "Polygon":
        if not (isinstance(coords, (list, tuple)) and len(coords) >= 1):
            return False, "Polygon must have at least 1 linear ring"
        for ring in coords:
            if not (isinstance(ring, (list, tuple)) and len(ring) >= 4):
                return False, "Polygon linear ring must have at least 4 coordinate pairs"
            for pt in ring:
                if not (isinstance(pt, (list, tuple)) and len(pt) >= 2):
                    return False, f"Invalid point in Polygon ring: {pt}"
                if not (-180.0 <= pt[0] <= 180.0 and -90.0 <= pt[1] <= 90.0):
                    return False, f"Polygon coordinate out of WGS84 bounds: {pt}"
            # Check closed ring
            if ring[0] != ring[-1]:
                return False, "Polygon linear ring must be closed (first == last coordinate)"
        return True, None

    elif geom_type == "MultiPolygon":
        if not (isinstance(coords, (list, tuple)) and len(coords) >= 1):
            return False, "MultiPolygon must contain at least 1 polygon"
        for poly in coords:
            ok, err = validate_coordinates(poly, "Polygon")
            if not ok:
                return False, f"MultiPolygon component error: {err}"
        return True, None

    return False, f"Unsupported geometry type '{geom_type}'"


def compute_bounding_box(coords: Any, geom_type: str, current_bbox: Dict[str, float]) -> None:
    """Incrementally updates the bounding box with coordinates from a geometry."""
    def _update_pt(pt: List[float]):
        lon, lat = pt[0], pt[1]
        current_bbox["lon_min"] = min(current_bbox["lon_min"], lon)
        current_bbox["lon_max"] = max(current_bbox["lon_max"], lon)
        current_bbox["lat_min"] = min(current_bbox["lat_min"], lat)
        current_bbox["lat_max"] = max(current_bbox["lat_max"], lat)

    if geom_type == "Point":
        _update_pt(coords)
    elif geom_type == "LineString":
        for pt in coords:
            _update_pt(pt)
    elif geom_type == "Polygon":
        for ring in coords:
            for pt in ring:
                _update_pt(pt)
    elif geom_type == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                for pt in ring:
                    _update_pt(pt)


class GeospatialValidator:
    """Validates canonical GeoJSON features, enforces WGS84 standards, deduplicates, and generates quality reports."""

    def __init__(self, source_name: str, bbox_filter: Optional[Dict[str, float]] = None):
        self.source_name = source_name
        self.bbox_filter = bbox_filter
        self.seen_ids: Set[str] = set()
        self.valid_features: List[GeoJSONFeature] = []
        self.rejected_count = 0
        self.duplicate_count = 0
        self.rejection_reasons: Dict[str, int] = {}
        self.geometry_types: Dict[str, int] = {}
        self.tag_categories: Dict[str, int] = {}
        self.computed_bbox = {
            "lat_min": 90.0,
            "lat_max": -90.0,
            "lon_min": 180.0,
            "lon_max": -180.0,
        }

    def validate_feature(self, feature: GeoJSONFeature) -> Tuple[bool, Optional[str]]:
        """Validates a single GeoJSONFeature for structure, WGS84 geometry, and deduplication.
        
        Args:
            feature: GeoJSONFeature instance.
            
        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        fid = feature.id or (feature.properties or {}).get("feature_id")
        if not fid:
            self._record_rejection("missing_feature_id")
            return False, "missing_feature_id"

        # Deduplication by canonical feature ID
        if fid in self.seen_ids:
            self.duplicate_count += 1
            self._record_rejection("duplicate_feature_id")
            return False, f"duplicate_feature_id_{fid}"

        geom = feature.geometry
        if not geom or not isinstance(geom, dict):
            self._record_rejection("missing_geometry_object")
            return False, "missing_geometry_object"

        geom_type = geom.get("type")
        coords = geom.get("coordinates")
        if not geom_type or coords is None:
            self._record_rejection("missing_geometry_type_or_coordinates")
            return False, "missing_geometry_type_or_coordinates"

        # Validate coordinate ranges
        is_coord_valid, coord_err = validate_coordinates(coords, geom_type)
        if not is_coord_valid:
            self._record_rejection(coord_err or "coordinate_validation_failed")
            return False, coord_err

        # Optional spatial bounding filter check
        if self.bbox_filter:
            if not self._is_within_filter(coords, geom_type):
                self._record_rejection("out_of_bounding_box")
                return False, "out_of_bounding_box"

        # Update running stats
        self.seen_ids.add(fid)
        self.valid_features.append(feature)
        self.geometry_types[geom_type] = self.geometry_types.get(geom_type, 0) + 1

        compute_bounding_box(coords, geom_type, self.computed_bbox)

        # Categorize properties if available
        props = feature.properties or {}
        ftype = props.get("feature_type") or "unknown"
        self.tag_categories[ftype] = self.tag_categories.get(ftype, 0) + 1

        return True, None

    def _is_within_filter(self, coords: Any, geom_type: str) -> bool:
        """Checks if at least one coordinate of the feature falls within bbox_filter."""
        b = self.bbox_filter
        def pt_in_box(p):
            return b["lon_min"] <= p[0] <= b["lon_max"] and b["lat_min"] <= p[1] <= b["lat_max"]

        if geom_type == "Point":
            return pt_in_box(coords)
        elif geom_type == "LineString":
            return any(pt_in_box(p) for p in coords)
        elif geom_type == "Polygon":
            return any(pt_in_box(p) for ring in coords for p in ring)
        elif geom_type == "MultiPolygon":
            return any(pt_in_box(p) for poly in coords for ring in poly for p in ring)
        return True

    def _record_rejection(self, reason: str):
        self.rejected_count += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1

    def get_metadata(
        self,
        retrieval_timestamp: str,
        license_str: str,
        attribution_str: str,
        query_filter: Optional[str] = None,
    ) -> GeospatialMetadata:
        """Generates canonical GeospatialMetadata object."""
        has_features = len(self.valid_features) > 0
        final_bbox = self.computed_bbox if has_features else {
            "lat_min": 0.0, "lat_max": 0.0, "lon_min": 0.0, "lon_max": 0.0
        }
        return GeospatialMetadata(
            source=self.source_name,
            retrieval_timestamp=retrieval_timestamp,
            crs="EPSG:4326",
            geometry_types=sorted(list(self.geometry_types.keys())),
            feature_count=len(self.valid_features),
            bounding_box=final_bbox,
            normalization_version="1.0.0",
            license=license_str,
            attribution=attribution_str,
            query_filter=query_filter,
        )

    def generate_quality_report(
        self,
        request_url: str,
        retrieval_timestamp: str,
        latency_ms: Optional[int],
        raw_count: int,
        license_str: str,
        attribution_str: str,
        query_scope: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Constructs complete JSON quality report."""
        return {
            "source": self.source_name,
            "request_url": request_url,
            "query_scope": query_scope,
            "retrieval_timestamp": retrieval_timestamp,
            "response_latency_ms": latency_ms,
            "raw_object_count": raw_count,
            "valid_feature_count": len(self.valid_features),
            "rejected_feature_count": self.rejected_count,
            "duplicate_count": self.duplicate_count,
            "rejection_breakdown": self.rejection_reasons,
            "geometry_distribution": self.geometry_types,
            "category_distribution": self.tag_categories,
            "bounding_box": self.computed_bbox if self.valid_features else None,
            "coordinate_reference_system": "EPSG:4326 (WGS84)",
            "license": license_str,
            "attribution": attribution_str,
        }

    def render_markdown_report(self, report_dict: Dict[str, Any]) -> str:
        """Renders Markdown quality report from the report dict."""
        bbox = report_dict.get("bounding_box") or {}
        bbox_str = (
            f"[{bbox.get('lat_min', 0):.4f}, {bbox.get('lon_min', 0):.4f}] to "
            f"[{bbox.get('lat_max', 0):.4f}, {bbox.get('lon_max', 0):.4f}]"
            if bbox else "N/A"
        )
        geom_str = ", ".join(f"{k}: {v}" for k, v in report_dict.get("geometry_distribution", {}).items()) or "None"
        cat_str = ", ".join(f"{k}: {v}" for k, v in report_dict.get("category_distribution", {}).items()) or "None"
        rej_str = ", ".join(f"{k}: {v}" for k, v in report_dict.get("rejection_breakdown", {}).items()) or "None"

        return f"""# Geospatial Ingestion Quality Report: {report_dict.get('source')}

**Generated At (UTC):** {report_dict.get('retrieval_timestamp')}  
**Source Endpoint:** `{report_dict.get('request_url')}`  
**Response Latency:** {report_dict.get('response_latency_ms')} ms  
**Coordinate Reference System:** {report_dict.get('coordinate_reference_system')}  
**Licensing & Attribution:** {report_dict.get('license')} ? *{report_dict.get('attribution')}*  

---

## 1. Feature Ingestion Summary

| Metric | Value |
|---|---|
| **Raw Objects Ingested** | {report_dict.get('raw_object_count')} |
| **Valid Canonical Features** | {report_dict.get('valid_feature_count')} |
| **Rejected Objects** | {report_dict.get('rejected_feature_count')} |
| **Duplicate Identifiers** | {report_dict.get('duplicate_count')} |
| **Computed Bounding Box (WGS84)** | {bbox_str} |

---

## 2. Geometry & Category Distribution

* **Geometry Types:** {geom_str}
* **Feature Categories:** {cat_str}
* **Rejection Breakdown:** {rej_str}

---

## 3. Provenance & Compliance

- **Storage Format:** Valid GeoJSON RFC 7946 FeatureCollection
- **Geodetic Standard:** WGS84 (EPSG:4326)
- **Scientific Boundary:** Pure geospatial context; NO spatial inference, hotspot modeling, or pollution interpolation applied.
"""
