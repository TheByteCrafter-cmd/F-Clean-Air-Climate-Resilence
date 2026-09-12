from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, model_validator


class Location(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    address: Optional[str] = Field(None, description="Human-readable address or landmark")


class TimeRange(BaseModel):
    start_time: datetime = Field(..., description="Start timestamp")
    end_time: datetime = Field(..., description="End timestamp")

    @model_validator(mode="after")
    def validate_time_order(self):
        if self.start_time > self.end_time:
            raise ValueError("start_time must be less than or equal to end_time")
        return self


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Service operational status")
    service: str = Field("VayuDrishti API", description="Service identifier")
    phase: str = Field("1b", description="Current development phase")
    timestamp: Optional[datetime] = Field(None, description="Server timestamp")


class ApiStatusResponse(BaseModel):
    status: str = Field("ok", description="API version operational status")
    version: str = Field("v1", description="API major version")
    message: str = Field("VayuDrishti API v1 skeleton is operational.", description="Status message")


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Standard machine-readable error code")
    message: str = Field(..., description="Human-readable error explanation")
    details: Optional[Any] = Field(None, description="Optional diagnostic details or validation errors")


class ErrorResponse(BaseModel):
    error: ErrorDetail = Field(..., description="Standardized error envelope")
