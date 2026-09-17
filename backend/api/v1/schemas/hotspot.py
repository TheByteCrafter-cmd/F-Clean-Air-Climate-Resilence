from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from backend.api.v1.schemas.common import Location


class HotspotDetectionRequest(BaseModel):
    """Payload to trigger hyper-local hotspot detection."""
    pollutant: str = Field("PM2.5", description="Target pollutant for hotspot analysis")
    analysis_timestamp: Optional[datetime] = Field(None, description="ISO 8601 UTC analysis timestamp (defaults to latest available)")
    time_window_minutes: float = Field(60.0, ge=10.0, le=1440.0, description="Symmetrical temporal window in minutes (+/- time_window_minutes)")
    roi_bbox: Optional[List[float]] = Field(None, description="Optional custom bounding box [lat_min, lon_min, lat_max, lon_max]")


class SpatialCoverageInfo(BaseModel):
    """Proximity metrics for station coverage around analysis domain."""
    min_station_distance_km: Optional[float] = Field(None, description="Distance to closest observation station in km")
    max_station_distance_km: Optional[float] = Field(None, description="Distance to furthest observation station within radius in km")
    nearest_station_id: Optional[str] = Field(None, description="ID of nearest station")


class HotspotDetectionResult(BaseModel):
    """Canonical machine-readable output artifact for a detected hyper-local hotspot area."""
    hotspot_id: str = Field(..., description="Unique hotspot identifier: hs_<uuid_hex>")
    pollutant: str = Field("PM2.5", description="Target pollutant parameter")
    analysis_timestamp: datetime = Field(..., description="ISO 8601 UTC analysis timestamp")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON Polygon or MultiPolygon representing contiguous qualifying grid cells")
    center: Location = Field(..., description="Centroid location of the detected hotspot area")
    support_score: float = Field(..., ge=0.0, le=100.0, description="Hotspot Support Score (0.0 - 100.0)")
    confidence_tier: Literal["LOW_SUPPORT", "MODERATE_SUPPORT", "HIGH_SUPPORT"] = Field(..., description="Qualitative confidence tier")
    interpolated_value: float = Field(..., description="Peak or centroid interpolated concentration in µg/m³")
    local_baseline: float = Field(..., description="Robust local baseline (median of valid spatial observations) in µg/m³")
    anomaly_value: float = Field(..., description="Absolute spatial anomaly (interpolated_value - local_baseline)")
    relative_anomaly: float = Field(..., description="Relative spatial anomaly ((interpolated_value - local_baseline) / max(baseline, 1))")
    observation_count: int = Field(..., ge=0, description="Count of valid stations within IDW search radius")
    spatial_coverage: SpatialCoverageInfo = Field(..., description="Station distance metrics")
    supporting_source_families: List[str] = Field(default_factory=list, description="Independent source families providing corroborating evidence")
    linked_fusion_ids: List[str] = Field(default_factory=list, description="IDs of nearby EvidenceFusionResult artifacts within radius")
    nearby_context: Dict[str, Any] = Field(default_factory=dict, description="Counts and types of nearby FIRMS, Sentinel-5P, and OSM features")
    uncertainty_notes: List[str] = Field(default_factory=list, description="Explicit caveats and non-causal disclaimer notes")
    data_quality: str = Field("SUFFICIENT_SPATIAL_DATA", description="Data sufficiency status flag")
    provenance: List[str] = Field(default_factory=list, description="Relative paths of scanned local data artifacts")
    config_version: str = Field("1.0-provisional", description="Detector configuration version")
    schema_version: str = Field("1.0", description="Schema version")


class HotspotSummary(BaseModel):
    """Lightweight summary of a detected hyper-local hotspot area."""
    hotspot_id: str = Field(..., description="Unique hotspot identifier")
    pollutant: str = Field("PM2.5", description="Pollutant parameter")
    location: Location = Field(..., description="Estimated centroid of the detected hotspot")
    severity: str = Field(..., description="Severity or support level")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Hotspot support score (0-100)")
    confidence_tier: str = Field("MODERATE_SUPPORT", description="Qualitative confidence tier")
    detected_at: datetime = Field(..., description="Detection timestamp")
    interpolated_value: float = Field(0.0, description="Peak interpolated concentration")
    anomaly_value: float = Field(0.0, description="Absolute anomaly above local baseline")
    observation_count: int = Field(0, ge=0, description="Stations in window")
    radius_meters: Optional[float] = Field(None, ge=0.0, description="Estimated spatial impact radius in meters")


class HotspotCollectionResponse(BaseModel):
    """Collection response containing summaries of detected hotspots."""
    total_count: int = Field(..., ge=0, description="Total detected hotspots in collection")
    pollutant: str = Field("PM2.5", description="Pollutant filter")
    analysis_timestamp: Optional[datetime] = Field(None, description="Analysis timestamp")
    hotspots: List[HotspotSummary] = Field(default_factory=list, description="List of hotspot summaries")
