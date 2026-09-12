from typing import List, Optional
from pydantic import BaseModel, Field


class RiskSummary(BaseModel):
    risk_level: str = Field(..., description="Calculated public health risk level: LOW, MODERATE, HIGH, CRITICAL")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Risk assessment confidence (0-100)")
    contributing_signals: List[str] = Field(default_factory=list, description="List of primary contributing factor tags")
    affected_zone: Optional[str] = Field(None, description="Affected municipal ward or corridor zone name")
