from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


class GeospatialFeature(BaseModel):
    """Canonical base schema for geospatial context features.
    
    Adheres strictly to docs/DATA_ARCHITECTURE.md Domain C:
    Spatial priors indicating industrial zones, freight corridors,
    sensitive receptors (schools, hospitals), and municipal boundaries.
    """
    feature_id: str = Field(..., description="Canonical ID: geo_{feature_type}_{osm_or_ward_id}")
    feature_type: Literal["road", "industrial", "sensitive_receptor", "ward_boundary"] = Field(
        ..., description="Standardized feature classification"
    )
    name: Optional[str] = Field(None, description="Human-readable name of feature (or None if unnamed)")
    city_code: str = Field(..., description="Pilot city identifier: 'DELHI', 'BENGALURU'")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry object in WGS84 (EPSG:4326)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Domain-specific normalized properties")
    source: str = Field(..., description="Source attribution identifier (e.g., 'OPENSTREETMAP_OVERPASS', 'DATAMEET_MUNICIPAL')")
    license: str = Field(..., description="Data license (e.g., 'ODbL', 'CC-BY-SA 4.0')")
    attribution: str = Field(..., description="Formal citation (e.g., '? OpenStreetMap contributors')")
    valid_from: Optional[str] = Field(None, description="ISO date validity start (YYYY-MM-DD)")
    valid_to: Optional[str] = Field(None, description="ISO date validity end")
    provenance: Optional[Dict[str, Any]] = Field(
        None, description="Audit trail: endpoint, retrieval_timestamp, query_filter, source_id"
    )


class RoadContextFeature(GeospatialFeature):
    """Specialized model for major road and freight corridors.
    
    Identifies vehicular emission corridors for spatial correlation.
    """
    feature_type: Literal["road"] = "road"
    osm_id: int = Field(..., description="OpenStreetMap element identifier")
    highway: str = Field(..., description="OSM highway tag: 'motorway', 'trunk', 'primary', 'secondary'")
    ref: Optional[str] = Field(None, description="Road reference number (e.g., 'NH-48', 'Ring Road')")
    surface: Optional[str] = Field(None, description="Pavement surface type (e.g., 'asphalt', 'paved')")
    classification: str = Field(
        "arterial_road",
        description="Functional classification: 'freight_corridor', 'arterial_road', 'secondary_collector'",
    )
    traffic_density_rank: Optional[int] = Field(
        None, ge=1, le=5, description="Estimated corridor traffic density rank (1=lowest, 5=highest)"
    )


class IndustrialContextFeature(GeospatialFeature):
    """Specialized model for industrial land-use zones.
    
    Identifies stationary manufacturing, scrap processing, and industrial zones.
    """
    feature_type: Literal["industrial"] = "industrial"
    osm_id: int = Field(..., description="OpenStreetMap element identifier")
    landuse: Literal["industrial"] = "industrial"
    industrial_type: Optional[str] = Field(None, description="Specific industrial tag subtype if present in source")
    zone_classification: str = Field(
        "manufacturing_zone",
        description="Zone classification: 'heavy_industrial', 'light_industrial', 'manufacturing_zone'",
    )


class SensitiveReceptorFeature(GeospatialFeature):
    """Specialized model for sensitive/vulnerable community receptors.
    
    Identifies schools, hospitals, and clinics requiring heightened health protections.
    """
    feature_type: Literal["sensitive_receptor"] = "sensitive_receptor"
    osm_id: int = Field(..., description="OpenStreetMap element identifier")
    amenity: Literal["hospital", "clinic", "school"] = Field(
        ..., description="Specific amenity classification: 'hospital', 'clinic', 'school'"
    )
    receptor_type: Literal["HEALTHCARE", "EDUCATION", "VULNERABLE_COMMUNITY"] = Field(
        ..., description="Standardized receptor category"
    )
    operator: Optional[str] = Field(None, description="Operating entity (government, private, trust)")


class WardBoundaryFeature(GeospatialFeature):
    """Specialized model for municipal administrative ward boundaries.
    
    Enables jurisdictional attribution of pollution anomalies.
    """
    feature_type: Literal["ward_boundary"] = "ward_boundary"
    ward_id: str = Field(..., description="Canonical ward identifier (e.g., 'delhi_ward_101')")
    ward_no: str = Field(..., description="Official ward number or code")
    ward_name: str = Field(..., description="Official ward name")
    admin_level: str = Field("municipal_ward", description="Administrative jurisdiction tier")
    source_ward_id: Optional[Union[str, int]] = Field(None, description="Upstream source identifier (e.g., KGISWardID)")
    source_properties: Dict[str, Any] = Field(
        default_factory=dict, description="Preserved upstream source properties for complete auditability"
    )


class GeoJSONFeature(BaseModel):
    """Standard RFC 7946 GeoJSON Feature representation."""
    type: Literal["Feature"] = "Feature"
    id: Optional[str] = Field(None, description="Feature identifier")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON geometry object")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Feature properties")


class GeospatialMetadata(BaseModel):
    """Standard provenance and audit metadata for geospatial GeoJSON artifacts."""
    source: str = Field(..., description="Originating source system")
    retrieval_timestamp: str = Field(..., description="ISO 8601 UTC timestamp of retrieval")
    crs: str = Field("EPSG:4326", description="Coordinate Reference System (canonical WGS84)")
    geometry_types: List[str] = Field(..., description="Set of geometry types present in collection")
    feature_count: int = Field(..., ge=0, description="Total number of valid features")
    bounding_box: Dict[str, float] = Field(
        ..., description="Computed spatial bounding box: lat_min, lat_max, lon_min, lon_max"
    )
    normalization_version: str = Field("1.0.0", description="Normalization pipeline version")
    license: str = Field(..., description="Data license")
    attribution: str = Field(..., description="Mandatory attribution statement")
    query_filter: Optional[str] = Field(None, description="Overpass QL or source filter used")


class GeoJSONFeatureCollection(BaseModel):
    """Standard RFC 7946 GeoJSON FeatureCollection with embedded metadata."""
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoJSONFeature] = Field(default_factory=list, description="List of GeoJSON features")
    metadata: Optional[GeospatialMetadata] = Field(None, description="Dataset metadata and provenance")
