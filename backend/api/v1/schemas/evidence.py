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
    status: Literal[
        "RECEIVED",
        "VALIDATED",
        "REJECTED",
        "READY_FOR_AI_ANALYSIS",
        "AI_ANALYZED",
        "AI_ANALYSIS_FAILED",
    ] = Field("RECEIVED", description="Evidence lifecycle processing status")
    source: str = Field("citizen_web", description="Intake source channel")
    schema_version: str = Field("1.0", description="Manifest schema version")


class ProbableCategoryItem(BaseModel):
    """Category classification with qualitative confidence level."""
    category: str = Field(..., description="Environmental category from taxonomy (e.g. industrial_smoke, biomass_burning)")
    confidence_level: Literal["high", "medium", "low"] = Field(
        ..., description="Qualitative confidence assessment (never calibrated probability)"
    )


class EvidenceAIAnalysis(BaseModel):
    """Structured AI analysis artifact produced by Gemini multimodal processing."""
    analysis_id: str = Field(..., description="Unique analysis identifier: an_<uuid_hex>")
    evidence_id: str = Field(..., description="Associated evidence identifier: ev_<uuid_hex>")
    model_name: str = Field(..., description="Gemini model identifier used for analysis")
    model_version: str = Field("2026-09", description="Model version or API snapshot identifier")
    analyzed_at: datetime = Field(..., description="ISO 8601 UTC analysis timestamp")
    relevance: Literal["relevant", "partially_relevant", "irrelevant", "insufficient_evidence"] = Field(
        ..., description="Qualitative relevance of visual/text evidence to environmental monitoring"
    )
    observed_phenomena: List[str] = Field(
        default_factory=list, description="List of observed environmental phenomena grounded in evidence"
    )
    probable_categories: List[ProbableCategoryItem] = Field(
        default_factory=list, description="Categorical emission classifications with qualitative confidence"
    )
    visual_indicators: List[str] = Field(
        default_factory=list, description="Observable visual features (e.g. dark plume, dense dust cloud)"
    )
    evidence_quality: str = Field(
        "clear", description="Assessment of visual clarity (clear, partially_obscured, blurry, low_resolution, dark)"
    )
    audio_status: str = Field(
        "AUDIO_ANALYSIS_DEFERRED", description="Explicit audio analysis status tag"
    )
    uncertainty: List[str] = Field(
        default_factory=list, description="Explicit statements of ambiguity, obscuration, or incomplete context"
    )
    explanation: str = Field(
        ..., description="Concise, evidence-grounded interpretation avoiding unsupported causal claims"
    )
    recommended_followup: List[str] = Field(
        default_factory=list, description="Suggested additional evidence (e.g. clearer photo, wider angle)"
    )
    safety_note: Optional[str] = Field(
        None, description="Optional safety, refusal, or prompt injection guard note"
    )
    schema_version: str = Field("1.0", description="Analysis schema version")



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
