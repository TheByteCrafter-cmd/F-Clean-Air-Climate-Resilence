import React, { useEffect, useState } from 'react';
import { apiClient, ApiError } from './api/client';
import { ApiStatusResponse, HealthResponse } from './types/api';
import { CitizenIntake } from './components/CitizenIntake';
import { DecisionIntelligenceView } from './components/DecisionIntelligenceView';

const App: React.FC = () => {
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [v1Data, setV1Data] = useState<ApiStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const checkConnectivity = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthRes, v1Res] = await Promise.all([
        apiClient.getHealth(),
        apiClient.getV1Status(),
      ]);
      setHealthData(healthRes);
      setV1Data(v1Res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(`[${err.code}] ${err.message}`);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Unknown communication failure');
      }
      setHealthData(null);
      setV1Data(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkConnectivity();
  }, []);

  return (
    <div style={{ maxWidth: '780px', margin: '0 auto', padding: '16px' }}>
      <DecisionIntelligenceView />
      <CitizenIntake />

      <div className="card" style={{ marginTop: '24px' }}>
        <div className="header">
          <h2 className="title" style={{ fontSize: '1.25rem' }}>System Status & API Health</h2>
          <p className="subtitle">Phase 1B & 1E-F Verification Hub</p>
        </div>

        <div className="status-group">
          <div className="status-item">
            <span>Frontend Layer (Vite + React + TS)</span>
            <span className="badge-success">
              <span className="dot"></span>
              Operational
            </span>
          </div>

          <div className="status-item">
            <span>Backend Health (/api/health)</span>
            {loading ? (
              <span className="badge-warning">
                <span className="dot"></span>
                Checking...
              </span>
            ) : error ? (
              <span className="badge-error">
                <span className="dot"></span>
                Unreachable
              </span>
            ) : (
              <span className="badge-success">
                <span className="dot"></span>
                Connected ({healthData?.status})
              </span>
            )}
          </div>

          <div className="status-item">
            <span>Versioned API (/api/v1/status)</span>
            {loading ? (
              <span className="badge-warning">
                <span className="dot"></span>
                Checking...
              </span>
            ) : error ? (
              <span className="badge-error">
                <span className="dot"></span>
                Unreachable
              </span>
            ) : (
              <span className="badge-success">
                <span className="dot"></span>
                Active ({v1Data?.version})
              </span>
            )}
          </div>
        </div>

        {v1Data && healthData && (
          <div className="response-box">
            <pre>{JSON.stringify({ health: healthData, v1_status: v1Data }, null, 2)}</pre>
          </div>
        )}

        {error && (
          <div className="response-box" style={{ color: '#991b1b', backgroundColor: '#fef2f2' }}>
            API Connection Error: {error}
          </div>
        )}

        <button className="action-btn" onClick={checkConnectivity} disabled={loading} style={{ marginTop: '12px' }}>
          {loading ? 'Validating Contracts...' : 'Re-verify API Contracts'}
        </button>
      </div>
    </div>
  );
};

export default App;
