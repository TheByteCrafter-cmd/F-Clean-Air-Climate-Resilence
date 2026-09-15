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

export interface GeospatialFeature {
  feature_id: string;
  feature_type: 'road' | 'industrial' | 'sensitive_receptor' | 'ward_boundary';
  name?: string | null;
  city_code: string;
  geometry: Record<string, unknown>;
  properties: Record<string, unknown>;
  source: string;
  license: string;
  attribution: string;
  valid_from?: string | null;
  valid_to?: string | null;
  provenance?: Record<string, unknown> | null;
}

export interface RoadContextFeature extends GeospatialFeature {
  feature_type: 'road';
  osm_id: number;
  highway: string;
  ref?: string | null;
  surface?: string | null;
  classification: string;
  traffic_density_rank?: number | null;
}

export interface IndustrialContextFeature extends GeospatialFeature {
  feature_type: 'industrial';
  osm_id: number;
  landuse: 'industrial';
  industrial_type?: string | null;
  zone_classification: string;
}

export interface SensitiveReceptorFeature extends GeospatialFeature {
  feature_type: 'sensitive_receptor';
  osm_id: number;
  amenity: 'hospital' | 'clinic' | 'school';
  receptor_type: 'HEALTHCARE' | 'EDUCATION' | 'VULNERABLE_COMMUNITY';
  operator?: string | null;
}

export interface WardBoundaryFeature extends GeospatialFeature {
  feature_type: 'ward_boundary';
  ward_id: string;
  ward_no: string;
  ward_name: string;
  admin_level: string;
  source_ward_id?: string | number | null;
  source_properties: Record<string, unknown>;
}

export interface GeoJSONFeature {
  type: 'Feature';
  id?: string | null;
  geometry: Record<string, unknown>;
  properties: Record<string, unknown>;
}

export interface GeospatialMetadata {
  source: string;
  retrieval_timestamp: string;
  crs: string;
  geometry_types: string[];
  feature_count: number;
  bounding_box: {
    lat_min: number;
    lat_max: number;
    lon_min: number;
    lon_max: number;
  };
  normalization_version: string;
  license: string;
  attribution: string;
  query_filter?: string | null;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
  metadata?: GeospatialMetadata | null;
}

export interface EvidenceLocation {
  latitude: number;
  longitude: number;
  accuracy_m?: number | null;
  source: 'gps' | 'manual';
  timestamp?: string | null;
}

export interface MediaItem {
  media_id: string;
  media_type: 'photo' | 'voice';
  mime_type: string;
  file_size_bytes: number;
  filename: string;
  captured_at?: string | null;
}

export interface EvidenceManifest {
  evidence_id: string;
  submitted_at: string;
  location?: EvidenceLocation | null;
  media: MediaItem[];
  description?: string | null;
  category?: string | null;
  consent_given: boolean;
  status: 'RECEIVED' | 'VALIDATED' | 'REJECTED' | 'READY_FOR_AI_ANALYSIS' | string;
  source: string;
  schema_version: string;
}

export interface EvidenceSubmissionResponse {
  evidence_id: string;
  status: string;
  submitted_at: string;
  location?: EvidenceLocation | null;
  media_count: number;
  media_types: string[];
  message: string;
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
