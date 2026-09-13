from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.api.v1.schemas.common import Location


class WeatherObservation(BaseModel):
    weather_id: Optional[str] = Field(None, description="Canonical weather observation identifier")
    timestamp: datetime = Field(..., description="Observation timestamp in UTC")
    location: Location = Field(..., description="Geographic coordinate of observation")
    temperature_c: float = Field(..., description="Air temperature at 2 meters above ground in ?C")
    relative_humidity_pct: float = Field(..., ge=0.0, le=100.0, description="Relative humidity at 2 meters in %")
    surface_pressure_hpa: float = Field(..., ge=800.0, le=1100.0, description="Surface atmospheric pressure in hPa")
    wind_speed_ms: float = Field(..., ge=0.0, description="Wind speed at 10 meters in m/s")
    wind_direction_deg: float = Field(..., ge=0.0, le=360.0, description="Wind direction at 10 meters in degrees from north (0-360)")
    precipitation_mm: Optional[float] = Field(0.0, ge=0.0, description="Precipitation rate or accumulation in mm")
    boundary_layer_height_m: Optional[float] = Field(None, ge=0.0, description="Planetary boundary layer height in meters")
    wind_u_ms: Optional[float] = Field(None, description="Zonal eastward wind component in m/s (Cartesian)")
    wind_v_ms: Optional[float] = Field(None, description="Meridional northward wind component in m/s (Cartesian)")
    source: str = Field("Open-Meteo", description="Data provider or atmospheric model source")
    retrieved_at: Optional[datetime] = Field(None, description="UTC timestamp of retrieval")
    source_url: Optional[str] = Field(None, description="Upstream source endpoint")
    normalization_version: Optional[str] = Field("1.0", description="Normalization version")
    raw_payload: Optional[Dict[str, Any]] = Field(None, description="Preserved minimal raw record payload for auditing")
