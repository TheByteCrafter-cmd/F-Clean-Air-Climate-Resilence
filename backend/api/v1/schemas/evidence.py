from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from backend.api.v1.schemas.common import Location


class CitizenEvidenceMetadata(BaseModel):
    evidence_id: str = Field(..., description="Unique UUID for citizen evidence report")
    timestamp: datetime = Field(..., description="Submission or photo capture timestamp")
    location: Location = Field(..., description="Geotagged submission location")
    media_type: str = Field(..., description="Media MIME type, e.g. image/jpeg, audio/wav")
    description: Optional[str] = Field(None, description="Citizen text remark or transcribed voice summary")
    source: str = Field("citizen_report", description="Origin channel, default citizen_report")
    category: Optional[str] = Field(None, description="Suspected pollution category, e.g. biomass_burning")
