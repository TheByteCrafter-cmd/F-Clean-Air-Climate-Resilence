import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.api.v1.schemas.geospatial import (
    RoadContextFeature,
    IndustrialContextFeature,
    SensitiveReceptorFeature,
    GeoJSONFeature,
)

logger = logging.getLogger(__name__)

# Strict tag whitelist for MVP geospatial context
ALLOWED_HIGHWAYS = {
    "motorway": "freight_corridor",
    "motorway_link": "freight_corridor",
    "trunk": "freight_corridor",
    "trunk_link": "freight_corridor",
    "primary": "arterial_road",
    "primary_link": "arterial_road",
    "secondary": "secondary_collector",
    "secondary_link": "secondary_collector",
}

ALLOWED_LANDUSE = {"industrial"}

ALLOWED_AMENITIES = {
    "hospital": "HEALTHCARE",
    "clinic": "HEALTHCARE",
    "school": "EDUCATION",
}


class OSMNormalizer:
    """Transforms raw Overpass JSON objects into canonical GeoJSON features and Pydantic models.
    
    Adheres strictly to the tag whitelist and canonical CRS standard (EPSG:4326).
    """

    def __init__(self, city_code: str = "DELHI"):
        self.city_code = city_code
        self.raw_count = 0
        self.normalized_count = 0
        self.rejected_count = 0
        self.rejection_reasons: Dict[str, int] = {}

    def _record_rejection(self, reason: str):
        self.rejected_count += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1

    def normalize_element(
        self, element: Dict[str, Any]
    ) -> Optional[Tuple[str, Union[RoadContextFeature, IndustrialContextFeature, SensitiveReceptorFeature], GeoJSONFeature]]:
        """Normalizes a single Overpass element into a canonical schema model and GeoJSON feature.
        
        Args:
            element: Raw Overpass element dictionary.
            
        Returns:
            Tuple of (category, pydantic_feature, geojson_feature) or None if rejected.
        """
        self.raw_count += 1
        if not isinstance(element, dict):
            self._record_rejection("element_not_a_dict")
            return None

        osm_id = element.get("id")
        osm_type = element.get("type")
        tags = element.get("tags") or {}

        if not osm_id or not osm_type:
            self._record_rejection("missing_osm_id_or_type")
            return None

        # Determine feature category based strictly on verified source tags
        highway_tag = tags.get("highway")
        landuse_tag = tags.get("landuse")
        amenity_tag = tags.get("amenity")

        is_road = highway_tag in ALLOWED_HIGHWAYS
        is_industrial = landuse_tag in ALLOWED_LANDUSE
        is_receptor = amenity_tag in ALLOWED_AMENITIES

        if not (is_road or is_industrial or is_receptor):
            self._record_rejection("unsupported_or_missing_tags")
            return None

        # Build geometry in GeoJSON format [lon, lat]
        geometry = self._extract_geometry(element, is_polygon=is_industrial)
        if not geometry:
            self._record_rejection("invalid_or_missing_geometry")
            return None

        name = tags.get("name")
        provenance = {
            "osm_id": osm_id,
            "osm_type": osm_type,
            "source": "OPENSTREETMAP_OVERPASS",
            "tags_preserved": {
                k: v for k, v in tags.items()
                if k in ("name", "highway", "landuse", "industrial", "amenity", "ref", "surface", "operator")
            },
        }

        # 1. Road corridor
        if is_road:
            classification = ALLOWED_HIGHWAYS[highway_tag]
            traffic_rank = 5 if classification == "freight_corridor" else (4 if classification == "arterial_road" else 3)
            pydantic_model = RoadContextFeature(
                feature_id=f"geo_road_way_{osm_id}",
                feature_type="road",
                osm_id=osm_id,
                highway=highway_tag,
                ref=tags.get("ref"),
                surface=tags.get("surface"),
                classification=classification,
                traffic_density_rank=traffic_rank,
                name=name,
                city_code=self.city_code,
                geometry=geometry,
                properties={
                    "osm_id": osm_id,
                    "highway": highway_tag,
                    "ref": tags.get("ref"),
                    "surface": tags.get("surface"),
                    "classification": classification,
                    "traffic_density_rank": traffic_rank,
                },
                source="OPENSTREETMAP_OVERPASS",
                license="ODbL",
                attribution="? OpenStreetMap contributors",
                provenance=provenance,
            )
            geojson_feat = GeoJSONFeature(
                id=f"geo_road_way_{osm_id}",
                geometry=geometry,
                properties=pydantic_model.model_dump(),
            )
            self.normalized_count += 1
            return ("road", pydantic_model, geojson_feat)

        # 2. Industrial area
        elif is_industrial:
            industrial_type = tags.get("industrial")
            pydantic_model = IndustrialContextFeature(
                feature_id=f"geo_industrial_{osm_type}_{osm_id}",
                feature_type="industrial",
                osm_id=osm_id,
                landuse="industrial",
                industrial_type=industrial_type,
                zone_classification="manufacturing_zone",
                name=name,
                city_code=self.city_code,
                geometry=geometry,
                properties={
                    "osm_id": osm_id,
                    "landuse": "industrial",
                    "industrial_type": industrial_type,
                    "zone_classification": "manufacturing_zone",
                },
                source="OPENSTREETMAP_OVERPASS",
                license="ODbL",
                attribution="? OpenStreetMap contributors",
                provenance=provenance,
            )
            geojson_feat = GeoJSONFeature(
                id=f"geo_industrial_{osm_type}_{osm_id}",
                geometry=geometry,
                properties=pydantic_model.model_dump(),
            )
            self.normalized_count += 1
            return ("industrial", pydantic_model, geojson_feat)

        # 3. Sensitive receptor
        elif is_receptor:
            receptor_type = ALLOWED_AMENITIES[amenity_tag]
            pydantic_model = SensitiveReceptorFeature(
                feature_id=f"geo_sensitive_{osm_type}_{osm_id}",
                feature_type="sensitive_receptor",
                osm_id=osm_id,
                amenity=amenity_tag,
                receptor_type=receptor_type,
                operator=tags.get("operator"),
                name=name,
                city_code=self.city_code,
                geometry=geometry,
                properties={
                    "osm_id": osm_id,
                    "amenity": amenity_tag,
                    "receptor_type": receptor_type,
                    "operator": tags.get("operator"),
                },
                source="OPENSTREETMAP_OVERPASS",
                license="ODbL",
                attribution="? OpenStreetMap contributors",
                provenance=provenance,
            )
            geojson_feat = GeoJSONFeature(
                id=f"geo_sensitive_{osm_type}_{osm_id}",
                geometry=geometry,
                properties=pydantic_model.model_dump(),
            )
            self.normalized_count += 1
            return ("sensitive_receptor", pydantic_model, geojson_feat)

        return None

    def _extract_geometry(self, element: Dict[str, Any], is_polygon: bool = False) -> Optional[Dict[str, Any]]:
        """Extracts and constructs WGS84 GeoJSON geometry from Overpass element."""
        elem_type = element.get("type")

        # Case 1: node with lat/lon
        if elem_type == "node":
            lat = element.get("lat")
            lon = element.get("lon")
            if lat is not None and lon is not None:
                return {"type": "Point", "coordinates": [round(float(lon), 6), round(float(lat), 6)]}

        # Case 2: way or relation with 'geometry' array from 'out geom'
        raw_geom = element.get("geometry")
        if isinstance(raw_geom, list) and len(raw_geom) >= 2:
            coords = []
            for pt in raw_geom:
                if isinstance(pt, dict) and "lat" in pt and "lon" in pt:
                    coords.append([round(float(pt["lon"]), 6), round(float(pt["lat"]), 6)])
            
            if len(coords) < 2:
                return None

            if is_polygon and len(coords) >= 3:
                # Ensure closed linear ring for Polygon GeoJSON standard
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                if len(coords) >= 4:
                    return {"type": "Polygon", "coordinates": [coords]}

            return {"type": "LineString", "coordinates": coords}

        return None
