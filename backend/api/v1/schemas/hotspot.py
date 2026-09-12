from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from backend.api.v1.schemas.common import Location


class HotspotSummary(BaseModel):
    hotspot_id: str = Field(..., description="Unique hotspot identifier")
    location: Location = Field(..., description="Estimated centroid of the detected hotspot")
    severity: str = Field(..., description="Severity classification: LOW, MODERATE, HIGH, SEVERE")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Evidence fusion confidence score (0-100)")
    detected_at: datetime = Field(..., description="Detection timestamp")
    radius_meters: Optional[float] = Field(None, ge=0.0, description="Estimated spatial impact radius in meters")
