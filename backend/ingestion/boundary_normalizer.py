import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.api.v1.schemas.geospatial import (
    WardBoundaryFeature,
    GeoJSONFeature,
)

logger = logging.getLogger(__name__)


class BoundaryNormalizer:
    """Normalizes raw municipal boundary GeoJSON features into canonical WardBoundaryFeatures.
    
    Supports:
      - Delhi MCD 250 wards (Ward_Name, Ward_No)
      - Bengaluru BBMP 198/243 wards (KGISWardName, KGISWardNo, KGISWardID)
    
    Preserves all original source attributes under `source_properties` for provenance.
    """

    def __init__(self, city: str):
        self.city = city.lower().strip()
        self.city_code = "DELHI" if self.city == "delhi" else ("BENGALURU" if self.city == "bengaluru" else city.upper())
        self.raw_count = 0
        self.normalized_count = 0
        self.rejected_count = 0
        self.rejection_reasons: Dict[str, int] = {}

    def _record_rejection(self, reason: str):
        self.rejected_count += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1

    def normalize_feature(
        self, raw_feature: Dict[str, Any]
    ) -> Optional[Tuple[WardBoundaryFeature, GeoJSONFeature]]:
        """Normalizes a single GeoJSON ward feature dictionary.
        
        Args:
            raw_feature: GeoJSON feature dict with 'geometry' and 'properties'.
            
        Returns:
            Tuple of (WardBoundaryFeature, GeoJSONFeature) or None if rejected.
        """
        self.raw_count += 1
        if not isinstance(raw_feature, dict):
            self._record_rejection("feature_not_a_dict")
            return None

        geom = raw_feature.get("geometry")
        if not geom or not isinstance(geom, dict):
            self._record_rejection("missing_geometry")
            return None

        geom_type = geom.get("type")
        coords = geom.get("coordinates")
        if geom_type not in ("Polygon", "MultiPolygon") or not coords:
            self._record_rejection("invalid_geometry_type_or_coordinates")
            return None

        props = raw_feature.get("properties") or {}

        # City-specific extraction
        if self.city == "delhi":
            ward_name = props.get("Ward_Name") or props.get("WARD_NAME") or props.get("ward_name")
            ward_no = props.get("Ward_No") or props.get("WARD_NO") or props.get("ward_no")
            source_id = str(ward_no) if ward_no else None

            if not ward_no and not ward_name:
                self._record_rejection("missing_delhi_ward_identifiers")
                return None

            ward_no_clean = str(ward_no).strip() if ward_no else f"delhi_idx_{self.raw_count}"
            ward_name_clean = str(ward_name).strip() if ward_name else f"Ward {ward_no_clean}"
            sanitized_id = ward_no_clean.lower().replace(" ", "_").replace("/", "_")
            canonical_id = f"geo_ward_delhi_{sanitized_id}"

        elif self.city == "bengaluru":
            ward_name = props.get("KGISWardName") or props.get("WARD_NAME") or props.get("ward_name")
            ward_no = props.get("KGISWardNo") or props.get("WARD_NO") or props.get("ward_no")
            source_id = str(props.get("KGISWardID") or "") or None

            if not ward_no and not ward_name:
                self._record_rejection("missing_bengaluru_ward_identifiers")
                return None

            ward_no_clean = str(ward_no).strip() if ward_no else f"blr_idx_{self.raw_count}"
            ward_name_clean = str(ward_name).strip() if ward_name else f"Ward {ward_no_clean}"
            sanitized_id = ward_no_clean.lower().replace(" ", "_").replace("/", "_")
            canonical_id = f"geo_ward_bengaluru_{sanitized_id}"

        else:
            self._record_rejection(f"unsupported_city_{self.city}")
            return None

        provenance = {
            "source": "DATAMEET_MUNICIPAL_SPATIAL_DATA",
            "city": self.city,
            "source_properties": props,
            "source_crs": "EPSG:4326",
        }

        pydantic_model = WardBoundaryFeature(
            feature_id=canonical_id,
            feature_type="ward_boundary",
            ward_id=canonical_id,
            ward_no=ward_no_clean,
            ward_name=ward_name_clean,
            admin_level="municipal_ward",
            source_ward_id=source_id,
            source_properties=props,
            name=ward_name_clean,
            city_code=self.city_code,
            geometry=geom,
            properties={
                "ward_id": canonical_id,
                "ward_no": ward_no_clean,
                "ward_name": ward_name_clean,
                "admin_level": "municipal_ward",
                "source_ward_id": source_id,
                "city": self.city_code,
            },
            source="DATAMEET_MUNICIPAL_SPATIAL_DATA",
            license="CC-BY-SA 4.0",
            attribution="DataMeet Municipal Spatial Data",
            provenance=provenance,
        )

        geojson_feat = GeoJSONFeature(
            id=canonical_id,
            geometry=geom,
            properties=pydantic_model.model_dump(),
        )

        self.normalized_count += 1
        return (pydantic_model, geojson_feat)
