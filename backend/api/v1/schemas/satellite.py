from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class SatelliteSignal(BaseModel):
    """Canonical base schema for satellite and earth observation signals.
    
    Adheres to docs/DATA_ARCHITECTURE.md Section 3.3.
    """
    signal_id: str = Field(..., description="Canonical unique satellite signal identifier")
    acquisition_time: datetime = Field(..., description="Observation overpass / acquisition timestamp in UTC")
    satellite: str = Field(..., description="Satellite platform name (e.g., 'Suomi-NPP', 'NOAA-20', 'Sentinel-5P')")
    instrument: str = Field(..., description="Sensor or instrument name (e.g., 'VIIRS', 'MODIS', 'TROPOMI')")
    signal_type: str = Field(..., description="Signal domain (e.g., 'THERMAL_FIRE_PIXEL', 'TROPOSPHERIC_NO2_COLUMN')")
    geometry: Dict[str, Any] = Field(..., description="GeoJSON Point or Polygon representation")
    value: float = Field(..., description="Quantitative signal magnitude (e.g., FRP in MW, column density)")
    unit: str = Field(..., description="Measurement unit (e.g., 'MW', 'mol/m?', 'K')")
    quality_indicator: str = Field(..., description="Standardized quality or confidence indicator ('HIGH', 'NOMINAL', 'LOW')")
    processing_level: Optional[str] = Field("NRT", description="Processing tier (e.g., 'NRT', 'L2', 'L3')")


class FireSignal(SatelliteSignal):
    """Specialized satellite thermal anomaly and active fire signal.
    
    Inherits from SatelliteSignal and preserves all verified NASA FIRMS attributes
    including Fire Radiative Power (MW), dual-band brightness temperatures (K),
    categorical confidence, Day/Night orbit flag, and pixel dimensions.
    
    SCIENTIFIC INTEGRITY NOTE:
    This model represents a detected thermal/fire anomaly. It does NOT represent
    direct particulate (PM2.5) concentrations, emissions plume volume, or population
    exposure. Any correlation with air quality belongs strictly to evidence fusion.
    """
    latitude: float = Field(..., ge=-90.0, le=90.0, description="WGS84 centroid latitude of thermal pixel")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="WGS84 centroid longitude of thermal pixel")
    acquisition_date: str = Field(..., description="Source acquisition date in YYYY-MM-DD")
    acquisition_time_str: str = Field(..., description="Source acquisition time in UTC HHMM format")
    confidence: str = Field(..., description="Reported confidence category ('low', 'nominal', 'high') or level")
    raw_confidence: Optional[str] = Field(None, description="Exact raw confidence string preserved for audit provenance")
    frp_mw: Optional[float] = Field(None, ge=0.0, description="Fire Radiative Power in Megawatts (MW)")
    bright_ti4_k: Optional[float] = Field(None, ge=150.0, le=600.0, description="VIIRS I-4 thermal brightness temperature in Kelvin")
    bright_ti5_k: Optional[float] = Field(None, ge=150.0, le=500.0, description="VIIRS I-5 thermal brightness temperature in Kelvin")
    daynight: Optional[str] = Field(None, description="Orbit pass flag: 'D' for daytime, 'N' for nighttime")
    scan: Optional[float] = Field(None, description="Along-scan pixel footprint dimension in km")
    track: Optional[float] = Field(None, description="Along-track pixel footprint dimension in km")
    version: Optional[str] = Field(None, description="FIRMS data collection/processing version (e.g., '2.0NRT')")
    source: str = Field("NASA_FIRMS", description="Source data provider")
    provenance: Optional[Dict[str, Any]] = Field(None, description="Retrieval metadata, source endpoint, bounding box, timestamp")
    raw_payload: Optional[Dict[str, Any]] = Field(None, description="Preserved minimal raw record dict for auditability")
