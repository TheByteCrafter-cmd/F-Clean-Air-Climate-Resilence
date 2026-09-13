from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.api.v1.schemas.common import Location


class EnvironmentalObservation(BaseModel):
    timestamp: datetime = Field(..., description="Observation capture timestamp")
    location: Location = Field(..., description="Geographic location of sensor reading")
    pollutant: str = Field(..., description="Pollutant parameter name, e.g. PM2.5, PM10, NO2, AQI")
    value: float = Field(..., ge=0.0, description="Measured numeric concentration or index")
    unit: str = Field(..., description="Measurement unit, e.g. ?g/m? or AQI")
    source: str = Field(..., description="Data originator, e.g. CAAQMS, IoT_Sensor, Satellite_Proxy")
    station_id: Optional[str] = Field(None, description="Optional station or sensor hardware identifier")
    source_record_id: Optional[str] = Field(None, description="Identifier of the record in the original data source")
    retrieved_at: Optional[datetime] = Field(None, description="Timestamp when the record was ingested")
    source_url: Optional[str] = Field(None, description="Source endpoint or upstream retrieval URL")
    normalization_version: Optional[str] = Field(None, description="Schema or pipeline normalization version")
    raw_payload: Optional[Dict[str, Any]] = Field(None, description="Preserved minimal raw record payload for auditing")
