from typing import Optional
from pydantic import BaseModel, Field
from backend.api.v1.schemas.common import Location


class ForecastSummary(BaseModel):
    location: Location = Field(..., description="Target forecast location or corridor node")
    pollutant: str = Field(..., description="Forecasted pollutant parameter, e.g. PM2.5")
    forecast_horizon: str = Field(..., description="Horizon duration, e.g. 1h, 3h, 6h")
    predicted_value: float = Field(..., ge=0.0, description="Point predicted concentration")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Model forecast confidence percentage")
    lower_bound: Optional[float] = Field(None, ge=0.0, description="Lower prediction interval (P10)")
    upper_bound: Optional[float] = Field(None, ge=0.0, description="Upper prediction interval (P90)")
