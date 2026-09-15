from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from backend.api.v1.schemas.common import Location


class EvidenceLocation(BaseModel):
    """Geographical coordinates and accuracy for citizen evidence."""
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 longitude")
    accuracy_m: Optional[float] = Field(None, ge=0.0, description="Horizontal accuracy radius in meters")
    source: Literal["gps", "manual"] = Field("gps", description="Location acquisition source")
    timestamp: Optional[datetime] = Field(None, description="Client GPS acquisition timestamp")


class MediaItem(BaseModel):
    """Metadata for an individual uploaded citizen media file."""
    media_id: str = Field(..., description="Unique media file identifier")
    media_type: Literal["photo", "voice"] = Field(..., description="Evidence media type")
    mime_type: str = Field(..., description="Standard MIME type (e.g. image/jpeg, audio/webm)")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    filename: str = Field(..., description="Server-sanitized storage filename")
    captured_at: Optional[datetime] = Field(None, description="Optional media capture timestamp")


class EvidenceManifest(BaseModel):
    """Canonical machine-readable manifest for a citizen evidence report."""
    evidence_id: str = Field(..., description="Unique evidence ID: ev_<uuid_hex>")
    submitted_at: datetime = Field(..., description="ISO 8601 UTC submission timestamp")
    location: Optional[EvidenceLocation] = Field(None, description="Submission location coordinates")
    media: List[MediaItem] = Field(default_factory=list, description="List of attached media items")
    description: Optional[str] = Field(None, max_length=1000, description="Optional citizen observation remarks")
    category: Optional[str] = Field(None, description="Suspected pollution category tag")
    consent_given: bool = Field(True, description="Explicit citizen consent confirmation")
    status: Literal["RECEIVED", "VALIDATED", "REJECTED", "READY_FOR_AI_ANALYSIS"] = Field(
        "RECEIVED", description="Evidence lifecycle processing status"
    )
    source: str = Field("citizen_web", description="Intake source channel")
    schema_version: str = Field("1.0", description="Manifest schema version")


class EvidenceSubmissionResponse(BaseModel):
    """Structured response returned to client after evidence intake."""
    evidence_id: str = Field(..., description="Assigned canonical evidence identifier")
    status: str = Field("received", description="Initial intake status")
    submitted_at: datetime = Field(..., description="Server reception timestamp")
    location: Optional[EvidenceLocation] = Field(None, description="Stored location")
    media_count: int = Field(..., ge=0, description="Count of successfully saved media files")
    media_types: List[str] = Field(default_factory=list, description="Media types attached")
    message: str = Field("Citizen evidence submitted and registered successfully.", description="Civic status message")


class CitizenEvidenceMetadata(BaseModel):
    """Backward-compatible schema for Phase 1B contract verification."""
    evidence_id: str = Field(..., description="Unique UUID for citizen evidence report")
    timestamp: datetime = Field(..., description="Submission or photo capture timestamp")
    location: Location = Field(..., description="Geotagged submission location")
    media_type: str = Field(..., description="Media MIME type, e.g. image/jpeg, audio/wav")
    description: Optional[str] = Field(None, description="Citizen text remark or transcribed voice summary")
    source: str = Field("citizen_report", description="Origin channel, default citizen_report")
    category: Optional[str] = Field(None, description="Suspected pollution category, e.g. biomass_burning")
