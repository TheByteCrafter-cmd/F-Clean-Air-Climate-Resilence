import React, { useEffect, useState } from 'react';

interface HealthResponse {
  status: string;
  service?: string;
  phase?: string;
}

const App: React.FC = () => {
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/health`);
      if (!response.ok) {
        throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
      }
      const data: HealthResponse = await response.json();
      setHealthData(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      setError(message);
      setHealthData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  return (
    <div className="card">
      <div className="header">
        <h1 className="title">VayuDrishti</h1>
        <p className="subtitle">Phase 1A: Foundation & Development Skeleton</p>
      </div>

      <div className="status-group">
        <div className="status-item">
          <span>Frontend Layer (Vite + React + TypeScript)</span>
          <span className="badge-success">
            <span className="dot"></span>
            Operational
          </span>
        </div>

        <div className="status-item">
          <span>Backend API ({apiBaseUrl}/api/health)</span>
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
      </div>

      {healthData && (
        <div className="response-box">
          <pre>{JSON.stringify(healthData, null, 2)}</pre>
        </div>
      )}

      {error && (
        <div className="response-box" style={{ color: '#991b1b', backgroundColor: '#fef2f2' }}>
          Backend connection check failed: {error}
        </div>
      )}

      <button className="action-btn" onClick={checkHealth} disabled={loading}>
        {loading ? 'Testing Connection...' : 'Re-check Connection'}
      </button>

      <p className="footer-note">
        Minimal development placeholder to verify frontend ↔ backend connectivity.
      </p>
    </div>
  );
};

export default App;
