from typing import Optional
from pydantic import BaseModel, Field


class AuthorityRecommendation(BaseModel):
    recommendation_id: str = Field(..., description="Unique recommendation ID")
    priority: str = Field(..., description="Intervention priority: P1_URGENT, P2_ELEVATED, P3_ROUTINE")
    action: str = Field(..., description="Operational directive text, e.g. Deploy Mobile Mist Sprayer")
    reason: str = Field(..., description="Evidentiary reason and sensor/satellite justification")
    grap_stage: Optional[str] = Field(None, description="Corresponding statutory GRAP stage, e.g. GRAP-III")
