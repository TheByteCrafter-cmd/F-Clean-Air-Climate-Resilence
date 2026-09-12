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
