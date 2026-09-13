/**
 * VayuDrishti - Phase 1B Shared API Contracts
 */

export interface Location {
  latitude: number;
  longitude: number;
  address?: string | null;
}

export interface TimeRange {
  start_time: string;
  end_time: string;
}

export interface HealthResponse {
  status: string;
  service: string;
  phase: string;
  timestamp?: string | null;
}

export interface ApiStatusResponse {
  status: string;
  version: string;
  message: string;
}

export interface ErrorDetail {
  code: string;
  message: string;
  details?: unknown;
}

export interface ErrorResponse {
  error: ErrorDetail;
}

export interface EnvironmentalObservation {
  timestamp: string;
  location: Location;
  pollutant: string;
  value: number;
  unit: string;
  source: string;
  station_id?: string | null;
  source_record_id?: string | null;
  retrieved_at?: string | null;
  source_url?: string | null;
  normalization_version?: string | null;
}

export interface WeatherObservation {
  weather_id?: string | null;
  timestamp: string;
  location: Location;
  temperature_c: number;
  relative_humidity_pct: number;
  surface_pressure_hpa: number;
  wind_speed_ms: number;
  wind_direction_deg: number;
  precipitation_mm?: number | null;
  boundary_layer_height_m?: number | null;
  wind_u_ms?: number | null;
  wind_v_ms?: number | null;
  source: string;
  retrieved_at?: string | null;
  source_url?: string | null;
  normalization_version?: string | null;
}

export interface SatelliteSignal {
  signal_id: string;
  acquisition_time: string;
  satellite: string;
  instrument: string;
  signal_type: string;
  geometry: Record<string, unknown>;
  value: number;
  unit: string;
  quality_indicator: 'HIGH' | 'NOMINAL' | 'LOW' | string;
  processing_level?: string | null;
}

export interface FireSignal extends SatelliteSignal {
  latitude: number;
  longitude: number;
  acquisition_date: string;
  acquisition_time_str: string;
  confidence: string;
  raw_confidence?: string | null;
  frp_mw?: number | null;
  bright_ti4_k?: number | null;
  bright_ti5_k?: number | null;
  daynight?: string | null;
  scan?: number | null;
  track?: number | null;
  version?: string | null;
  source: string;
  provenance?: Record<string, unknown> | null;
}

export interface Sentinel5PNO2Signal extends SatelliteSignal {
  latitude: number;
  longitude: number;
  tropospheric_no2_mol_m2: number;
  cloud_fraction?: number | null;
  qa_value?: number | null;
  stratospheric_no2_mol_m2?: number | null;
  total_no2_mol_m2?: number | null;
  approx_resolution_km?: number | null;
  source: string;
  provenance?: Record<string, unknown> | null;
}


export interface CitizenEvidenceMetadata {
  evidence_id: string;
  timestamp: string;
  location: Location;
  media_type: string;
  description?: string | null;
  source: string;
  category?: string | null;
}

export interface HotspotSummary {
  hotspot_id: string;
  location: Location;
  severity: 'LOW' | 'MODERATE' | 'HIGH' | 'SEVERE' | string;
  confidence: number;
  detected_at: string;
  radius_meters?: number | null;
}

export interface ForecastSummary {
  location: Location;
  pollutant: string;
  forecast_horizon: string;
  predicted_value: number;
  confidence: number;
  lower_bound?: number | null;
  upper_bound?: number | null;
}

export interface RiskSummary {
  risk_level: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL' | string;
  confidence: number;
  contributing_signals: string[];
  affected_zone?: string | null;
}

export interface AuthorityRecommendation {
  recommendation_id: string;
  priority: 'P1_URGENT' | 'P2_ELEVATED' | 'P3_ROUTINE' | string;
  action: string;
  reason: string;
  grap_stage?: string | null;
}
