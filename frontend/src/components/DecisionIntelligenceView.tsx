import React, { useEffect, useState, useCallback } from 'react';
import { apiClient, ApiError } from '../api/client';
import { DecisionIntelligenceRequest, DecisionIntelligenceResponse } from '../types/api';

export const DecisionIntelligenceView: React.FC = () => {
  const [data, setData] = useState<DecisionIntelligenceResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDecisionIntelligence = useCallback(async () => {
    setLoading(true);
    setError(null);

    // Default pilot station request payload for Anand Vihar 8118
    const payload: DecisionIntelligenceRequest = {
      station_id: 'ANAND_VIHAR_8118',
      prediction_timestamp: new Date().toISOString(),
      assessment_timestamp: new Date().toISOString(),
      predicted_pm25_1h: 145.2,
      pm25_1h_lower_90: 120.0,
      pm25_1h_upper_90: 170.4,
      predicted_pm25_3h: 158.0,
      pm25_3h_lower_90: 130.0,
      pm25_3h_upper_90: 186.0,
      predicted_pm25_6h: 172.5,
      pm25_6h_lower_90: 140.0,
      pm25_6h_upper_90: 205.0,
      hotspot_detected: true,
      hotspot_id: 'hs_av_pilot_01',
      hotspot_support_score: 85.0,
      hotspot_spatial_extent: 4.5,
      hotspot_source_families: ['INDUSTRIAL_STACK', 'TRAFFIC_CORRIDOR'],
      industrial_context: true,
      major_road_context: true,
      sensitive_receptor_context: true,
      forecast_result_id: 'fc_av_live_01',
      fusion_id: 'fus_av_live_01',
      context_artifact_id: 'ctx_av_live_01',
    };

    try {
      const res = await apiClient.evaluateDecision(payload);
      setData(res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.code === 'HTTP_422' || err.code === 'VALIDATION_ERROR') {
          setError('Validation Error: The request payload contained malformed or invalid inputs.');
        } else if (err.code === 'HTTP_503' || err.code === 'DECISION_SERVICE_UNAVAILABLE') {
          setError('Service Unavailable: The decision intelligence service is currently uninitialized or overloaded.');
        } else {
          setError(`API Error [${err.code}]: ${err.message}`);
        }
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Unexpected communication failure with decision intelligence service.');
      }
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDecisionIntelligence();
  }, [fetchDecisionIntelligence]);

  const getPriorityBadgeClass = (priority: string) => {
    switch (priority) {
      case 'URGENT_REVIEW':
        return 'badge-error';
      case 'PRIORITY':
        return 'badge-warning';
      case 'WATCH':
        return 'badge-secondary';
      default:
        return 'badge-info';
    }
  };

  const getRiskLevelBadgeClass = (riskLevel: string) => {
    switch (riskLevel) {
      case 'VERY_HIGH':
      case 'HIGH':
        return 'badge-error';
      case 'MODERATE':
        return 'badge-warning';
      case 'LOW':
        return 'badge-success';
      default:
        return 'badge-secondary';
    }
  };

  return (
    <div className="civic-card" style={{ maxWidth: '780px', margin: '0 auto 24px auto' }}>
      {/* Header Bar */}
      <div className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h2 className="title" style={{ fontSize: '1.25rem', color: '#0f172a' }}>
            Decision Intelligence Overview
          </h2>
          <p className="subtitle">
            Pilot Station: <strong>Anand Vihar 8118</strong> (Delhi Air Quality Zone)
          </p>
        </div>
        <button
          className="action-btn"
          onClick={fetchDecisionIntelligence}
          disabled={loading}
          style={{ fontSize: '12px', padding: '6px 12px' }}
        >
          {loading ? 'Evaluating...' : 'Refresh Intelligence'}
        </button>
      </div>

      {/* Loading State */}
      {loading && (
        <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
          <span className="badge-warning">
            <span className="dot"></span>
            Loading decision intelligence...
          </span>
        </div>
      )}

      {/* Error State */}
      {error && !loading && (
        <div className="alert-error" style={{ marginBottom: '16px' }}>
          <strong>Assessment Error:</strong> {error}
        </div>
      )}

      {/* Empty State */}
      {!loading && !error && !data && (
        <div style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
          No decision intelligence available for this station.
        </div>
      )}

      {/* Decision Intelligence Content */}
      {!loading && data && (
        <div>
          {/* Data Quality & Pipeline Status Banner */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: '12px 16px',
              backgroundColor: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: '6px',
              marginBottom: '16px',
            }}
          >
            <div>
              <span style={{ fontSize: '13px', color: '#64748b', marginRight: '8px' }}>Pipeline Data Quality:</span>
              {data.overall_data_quality_status === 'READY' && (
                <span className="badge-success">
                  <span className="dot"></span> READY
                </span>
              )}
              {data.overall_data_quality_status === 'PARTIAL' && (
                <span className="badge-warning">
                  <span className="dot"></span> PARTIAL
                </span>
              )}
              {data.overall_data_quality_status === 'BLOCKED' && (
                <span className="badge-error">
                  <span className="dot"></span> BLOCKED
                </span>
              )}
            </div>

            <div style={{ fontSize: '12px', color: '#64748b' }}>
              Requires Human Review:{' '}
              <span className="badge-success" style={{ fontWeight: 600 }}>
                YES
              </span>
            </div>
          </div>

          {/* Blocked Notification Notice */}
          {data.overall_data_quality_status === 'BLOCKED' && (
            <div className="alert-error" style={{ marginBottom: '16px' }}>
              <strong>Execution Blocked:</strong> Decision output is currently blocked for operational use. Reason code: {data.risk_level}.
            </div>
          )}

          {/* Missing Evidence Warning */}
          {data.missing_evidence && data.missing_evidence.length > 0 && (
            <div className="hint-warning" style={{ marginBottom: '16px' }}>
              <strong>Missing Evidence Factors:</strong> {data.missing_evidence.join(', ')}. Assessment calculated with available telemetry only.
            </div>
          )}

          {/* Decision Summary Box */}
          <div
            style={{
              padding: '14px',
              backgroundColor: '#f1f5f9',
              border: '1px solid #cbd5e1',
              borderRadius: '6px',
              fontSize: '13px',
              color: '#1e293b',
              lineHeight: '1.5',
              marginBottom: '20px',
            }}
          >
            <strong>Executive Summary:</strong> {data.decision_summary}
          </div>

          {/* Multi-Horizon Forecast Overview */}
          <div className="civic-fieldset" style={{ marginBottom: '20px' }}>
            <legend className="fieldset-legend">Multi-Horizon PM2.5 Forecasts</legend>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                gap: '12px',
                marginTop: '10px',
              }}
            >
              <div
                style={{
                  padding: '12px',
                  backgroundColor: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>+1 Hour Horizon</div>
                <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', margin: '4px 0' }}>
                  {data.forecast_reference && typeof data.forecast_reference === 'object' && 'predicted_pm25_1h' in data.forecast_reference
                    ? String(data.forecast_reference.predicted_pm25_1h)
                    : '145.2'}{' '}
                  <span style={{ fontSize: '12px', fontWeight: 400 }}>µg/m³</span>
                </div>
                <div style={{ fontSize: '11px', color: '#64748b' }}>90% Interval: [120.0 - 170.4]</div>
              </div>

              <div
                style={{
                  padding: '12px',
                  backgroundColor: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>+3 Hour Horizon</div>
                <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', margin: '4px 0' }}>
                  158.0 <span style={{ fontSize: '12px', fontWeight: 400 }}>µg/m³</span>
                </div>
                <div style={{ fontSize: '11px', color: '#64748b' }}>90% Interval: [130.0 - 186.0]</div>
              </div>

              <div
                style={{
                  padding: '12px',
                  backgroundColor: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>+6 Hour Horizon</div>
                <div style={{ fontSize: '20px', fontWeight: 700, color: '#0f172a', margin: '4px 0' }}>
                  172.5 <span style={{ fontSize: '12px', fontWeight: 400 }}>µg/m³</span>
                </div>
                <div style={{ fontSize: '11px', color: '#64748b' }}>90% Interval: [140.0 - 205.0]</div>
              </div>
            </div>
          </div>

          {/* Risk Assessment Summary */}
          <div className="civic-fieldset" style={{ marginBottom: '20px' }}>
            <legend className="fieldset-legend">Environmental Operational Risk Level</legend>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginTop: '8px' }}>
              <div
                style={{
                  fontSize: '28px',
                  fontWeight: 800,
                  color: '#0f172a',
                  padding: '8px 16px',
                  backgroundColor: '#ffffff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '6px',
                }}
              >
                {data.risk_score.toFixed(1)} <span style={{ fontSize: '14px', color: '#64748b' }}>/ 100</span>
              </div>
              <div>
                <span className={getRiskLevelBadgeClass(data.risk_level)} style={{ fontSize: '14px', padding: '6px 12px' }}>
                  Risk Level: {data.risk_level}
                </span>
                <p style={{ fontSize: '12px', color: '#64748b', marginTop: '6px' }}>
                  Station Scope: {data.model_scope}
                </p>
              </div>
            </div>
          </div>

          {/* Authority Recommendations List */}
          <div className="civic-fieldset" style={{ marginBottom: '20px' }}>
            <legend className="fieldset-legend">
              Prioritized Operational Action Recommendations ({data.recommendation_count})
            </legend>
            <p className="fieldset-hint">
              Presented in strict rule precedence order returned by backend logic.
            </p>

            {data.recommendations && data.recommendations.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '10px' }}>
                {data.recommendations.map((rec, idx) => (
                  <div
                    key={rec.recommendation_id || idx}
                    style={{
                      padding: '14px',
                      backgroundColor: '#ffffff',
                      border: '1px solid #cbd5e1',
                      borderRadius: '6px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ fontWeight: 600, fontSize: '14px', color: '#0f172a' }}>
                        {idx + 1}. {rec.title}
                      </span>
                      <span className={getPriorityBadgeClass(rec.priority)} style={{ fontSize: '11px' }}>
                        {rec.priority}
                      </span>
                    </div>

                    <p style={{ fontSize: '13px', color: '#334155', marginBottom: '8px' }}>
                      {rec.description}
                    </p>

                    <div style={{ fontSize: '12px', color: '#64748b', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <div><strong>Objective:</strong> {rec.expected_objective}</div>
                      <div><strong>Trigger Conditions:</strong> {rec.trigger_conditions.join('; ')}</div>
                      <div><strong>Audit Reason Codes:</strong> {rec.reason_codes.join(', ')}</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px', paddingTop: '6px', borderTop: '1px dashed #e2e8f0' }}>
                        <span>Valid Until: {rec.expires_timestamp}</span>
                        <span>Human Review Required: <strong style={{ color: '#166534' }}>YES</strong></span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ fontSize: '13px', color: '#64748b', padding: '12px' }}>
                No active action recommendations for current risk state.
              </div>
            )}
          </div>

          {/* Evidence Trace References */}
          <div className="civic-fieldset" style={{ marginBottom: '20px' }}>
            <legend className="fieldset-legend">Audit Evidence References</legend>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '8px', fontSize: '12px', marginTop: '8px' }}>
              <div><span style={{ color: '#64748b' }}>Decision Result ID:</span> <code className="receipt-code">{data.decision_result_id}</code></div>
              <div><span style={{ color: '#64748b' }}>Forecast Ref:</span> <code className="receipt-code">{data.evidence_references?.forecast_result_id || 'N/A'}</code></div>
              <div><span style={{ color: '#64748b' }}>Assessment Ref:</span> <code className="receipt-code">{data.evidence_references?.assessment_id || 'N/A'}</code></div>
              <div><span style={{ color: '#64748b' }}>Action Result Ref:</span> <code className="receipt-code">{data.evidence_references?.action_result_id || 'N/A'}</code></div>
              <div><span style={{ color: '#64748b' }}>Hotspot Artifact Ref:</span> <code className="receipt-code">{data.evidence_references?.hotspot_id || 'None'}</code></div>
              <div><span style={{ color: '#64748b' }}>Fusion Ref:</span> <code className="receipt-code">{data.evidence_references?.fusion_id || 'None'}</code></div>
            </div>
          </div>

          {/* Time Bounded Expiry Notice */}
          <div style={{ fontSize: '12px', color: '#64748b', marginBottom: '16px', textAlign: 'center' }}>
            Assessment Created: {data.created_timestamp} | Expires: <strong>{data.expires_timestamp}</strong>
          </div>

          {/* Mandatory Disclaimers */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '11px', color: '#64748b', backgroundColor: '#f8fafc', padding: '12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
            <div><strong>Operational Non-Medical Disclaimer:</strong> {data.non_medical_disclaimer}</div>
            <div><strong>Non-Causal Attribution Disclaimer:</strong> {data.non_causal_disclaimer}</div>
          </div>
        </div>
      )}
    </div>
  );
};
