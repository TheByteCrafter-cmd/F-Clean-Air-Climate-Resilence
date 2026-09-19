"""
VayuDrishti — Forecast API Pydantic Schemas (Phase 1E-J2E.2)

Defines request and response schemas for post-inference PM2.5 air quality forecasts
with unclipped Split Conformal prediction intervals.
"""

import math
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.api.v1.schemas.common import Location


# Legacy Phase 1B schema preserved for backward compatibility
class ForecastSummary(BaseModel):
    location: Location = Field(..., description="Target forecast location or corridor node")
    pollutant: str = Field(..., description="Forecasted pollutant parameter, e.g. PM2.5")
    forecast_horizon: str = Field(..., description="Horizon duration, e.g. 1h, 3h, 6h")
    predicted_value: float = Field(..., ge=0.0, description="Point predicted concentration")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Model forecast confidence percentage")
    lower_bound: Optional[float] = Field(None, ge=0.0, description="Lower prediction interval (P10)")
    upper_bound: Optional[float] = Field(None, ge=0.0, description="Upper prediction interval (P90)")


# Phase 1E-J2E.2 Production Forecast Schemas
class ForecastRequest(BaseModel):
    station_id: str = Field(
        ...,
        description="Monitoring station ID (e.g., ANAND_VIHAR_8118 or 8118)",
        examples=["ANAND_VIHAR_8118", "8118"],
    )
    prediction_timestamp: str = Field(
        ...,
        description="ISO-8601 UTC prediction timestamp",
        examples=["2025-01-31T12:00:00Z"],
    )
    features: Dict[str, float] = Field(
        ...,
        description="Leakage-safe prepared feature dictionary matching exact manifest columns",
    )

    @field_validator("station_id")
    @classmethod
    def validate_station_id_non_empty(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("station_id must be a non-empty string.")
        return v.strip()

    @field_validator("prediction_timestamp")
    @classmethod
    def validate_timestamp_non_empty(cls, v: str) -> str:
        if not v or not isinstance(v, str) or not v.strip():
            raise ValueError("prediction_timestamp must be a non-empty string.")
        return v.strip()

    @field_validator("features")
    @classmethod
    def validate_features_dict(cls, v: Dict[str, Any]) -> Dict[str, float]:
        if not isinstance(v, dict) or len(v) == 0:
            raise ValueError("features dictionary must not be empty.")

        cleaned_features: Dict[str, float] = {}
        invalid_keys = []
        for key, val in v.items():
            if val is None or val == "":
                invalid_keys.append((key, "null/missing value"))
                continue
            try:
                val_float = float(val)
                if math.isnan(val_float) or math.isinf(val_float):
                    invalid_keys.append((key, f"NaN or Infinite value: {val}"))
                else:
                    cleaned_features[key] = val_float
            except (ValueError, TypeError):
                invalid_keys.append((key, f"non-numeric value: {val}"))

        if invalid_keys:
            raise ValueError(f"Features dictionary contains invalid values: {invalid_keys}")

        return cleaned_features


class ConformalIntervalDetail(BaseModel):
    confidence_level: str = Field(..., description="Nominal confidence level (e.g. 80%, 90%)")
    conformal_radius: float = Field(..., description="Frozen conformal radius 'q' from validation residuals")
    lower_bound: float = Field(..., description="Unclipped lower prediction interval bound (pred - q)")
    upper_bound: float = Field(..., description="Unclipped upper prediction interval bound (pred + q)")
    interval_width: float = Field(..., description="Full prediction interval width (2 * q)")


class HorizonForecastResult(BaseModel):
    horizon: str = Field(..., description="Target forecast horizon (+1h, +3h, +6h)")
    target_column: str = Field(..., description="Target target dataset column name")
    predicted_pm25: float = Field(..., description="Unclipped point predicted PM2.5 concentration in ug/m3")
    prediction_negative: bool = Field(..., description="Diagnostic flag indicating if raw point forecast < 0.0")
    prediction_intervals: Dict[str, ConformalIntervalDetail] = Field(
        ...,
        description="Frozen Split Conformal prediction intervals for 80% and 90% confidence levels",
    )


class ForecastResponse(BaseModel):
    status: str = Field("SUCCESS", description="Execution status code")
    model_scope: str = Field("station_level_pilot", description="Model scope descriptor")
    canonical_station_id: str = Field(..., description="Canonical station identifier (ANAND_VIHAR_8118)")
    requested_station_id: str = Field(..., description="Station ID provided in request")
    prediction_timestamp: str = Field(..., description="Normalized UTC prediction timestamp")
    feature_count: int = Field(..., description="Number of validated feature columns used")
    forecasts: List[HorizonForecastResult] = Field(..., description="List of forecast results for requested horizons")
