from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class MatchedRecordRef(BaseModel):
    """Reference payload for an individual signal matched by spatial/temporal windows."""
    source_family: Literal[
        "CITIZEN_GEMINI",
        "AIR_QUALITY",
        "WEATHER",
        "THERMAL_ANOMALY",
        "SATELLITE_NO2",
        "GEOSPATIAL_CONTEXT",
    ] = Field(..., description="High-level independent evidence family")
    source_type: str = Field(..., description="Origin data source (e.g. OpenAQ, OpenMeteo, FIRMS, Sentinel-5P, OSM, CitizenReport)")
    record_id: str = Field(..., description="Canonical or unique ID of the source observation record")
    distance_km: Optional[float] = Field(None, ge=0.0, description="Geodesic distance from event anchor in kilometers")
    time_difference_minutes: Optional[float] = Field(None, description="Signed time difference in minutes (observation - anchor)")
    key_values: Dict[str, Any] = Field(default_factory=dict, description="Extracted key measurement values (e.g. PM2.5 value, FRP, wind speed)")
    provenance_ref: str = Field(..., description="Path or source identifier of the raw/processed dataset artifact")


class EvidenceFusionResult(BaseModel):
    """Canonical machine-readable output for multi-source evidence fusion."""
    fusion_id: str = Field(..., description="Canonical fusion identifier: fu_<uuid_hex>")
    event_anchor_id: str = Field(..., description="Associated citizen evidence anchor ID: ev_<uuid_hex>")
    created_at: datetime = Field(..., description="ISO 8601 UTC fusion computation timestamp")
    support_score: float = Field(..., ge=0.0, le=100.0, description="Deterministic evidence support score (0.0 to 100.0)")
    confidence_tier: Literal["LOW_SUPPORT", "MODERATE_SUPPORT", "HIGH_SUPPORT"] = Field(
        ..., description="Qualitative confidence tier derived from support score"
    )
    supporting_signals: List[MatchedRecordRef] = Field(
        default_factory=list, description="List of matched supporting signal references"
    )
    unavailable_signals: List[str] = Field(
        default_factory=list, description="List of source families with no observation data available"
    )
    conflicting_signals: List[MatchedRecordRef] = Field(
        default_factory=list, description="List of matched records that contradict or fail to support event candidate"
    )
    explanation: str = Field(..., description="Deterministic human-readable explanation of fusion findings")
    uncertainty_notes: List[str] = Field(
        default_factory=list, description="Explicit caveats, spatial/temporal offsets, or missing data notes"
    )
    provenance_sources: List[str] = Field(
        default_factory=list, description="List of referenced source artifact file paths or IDs"
    )
    config_version: str = Field("1.0-provisional", description="Fusion matching configuration version")
    schema_version: str = Field("1.0", description="Fusion schema version")
