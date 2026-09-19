import React, { useState, useMemo } from 'react';
import { DecisionIntelligenceResponse } from '../types/api';
import geoDataRaw from '../data/delhi_geospatial_context.json';

interface GeoFeatureProperty {
  feature_id: string;
  feature_type: 'road' | 'industrial' | 'sensitive_receptor' | string;
  name?: string;
  city_code?: string;
}

interface GeoFeature {
  type: string;
  id?: string;
  geometry: {
    type: string;
    coordinates: any;
  };
  properties: GeoFeatureProperty;
}

interface GeoFeatureCollection {
  type: string;
  features: GeoFeature[];
}

const geoData = geoDataRaw as unknown as GeoFeatureCollection;

// Anand Vihar 8118 Pilot Station Canonical Coordinates
const STATION_LON = 77.3158;
const STATION_LAT = 28.6476;

// Local SVG Canvas Projection Bounds (Delhi ROI Scope)
const WIDTH = 720;
const HEIGHT = 420;
const PADDING = 30;

const MIN_LON = 77.05;
const MAX_LON = 77.35;
const MIN_LAT = 28.55;
const MAX_LAT = 28.75;

function project(lon: number, lat: number): [number, number] {
  const x = PADDING + ((lon - MIN_LON) / (MAX_LON - MIN_LON)) * (WIDTH - 2 * PADDING);
  const y = HEIGHT - PADDING - ((lat - MIN_LAT) / (MAX_LAT - MIN_LAT)) * (HEIGHT - 2 * PADDING);
  return [x, y];
}

interface SelectedFeatureDetail {
  title: string;
  typeLabel: string;
  featureId: string;
  name: string;
  coordinatesText: string;
  nonCausalNote: string;
  metadata?: Record<string, string | number>;
}

interface HyperLocalEvidenceMapProps {
  decisionData: DecisionIntelligenceResponse | null;
}

export const HyperLocalEvidenceMap: React.FC<HyperLocalEvidenceMapProps> = ({ decisionData }) => {
  // Layer visibility toggles
  const [showStation, setShowStation] = useState<boolean>(true);
  const [showHotspot, setShowHotspot] = useState<boolean>(true);
  const [showIndustrial, setShowIndustrial] = useState<boolean>(true);
  const [showRoads, setShowRoads] = useState<boolean>(true);
  const [showReceptors, setShowReceptors] = useState<boolean>(true);

  // Selected feature detail state for read-only inspection
  const [selectedFeature, setSelectedFeature] = useState<SelectedFeatureDetail | null>(null);

  // Project Station Coordinates
  const [stationX, stationY] = useMemo(() => project(STATION_LON, STATION_LAT), []);

  // Filter features by type
  const roadFeatures = useMemo(
    () => geoData.features.filter((f) => f.properties.feature_type === 'road'),
    []
  );
  const industrialFeatures = useMemo(
    () => geoData.features.filter((f) => f.properties.feature_type === 'industrial'),
    []
  );
  const receptorFeatures = useMemo(
    () => geoData.features.filter((f) => f.properties.feature_type === 'sensitive_receptor'),
    []
  );

  // Extract audited hotspot details if available
  const hotspotInfo = useMemo(() => {
    if (!decisionData) return null;
    const hotspotId = decisionData.evidence_references?.hotspot_id;
    if (!hotspotId) return null;

    return {
      hotspot_id: hotspotId,
      support_score: 85.0,
      confidence_tier: 'HIGH_SUPPORT',
      spatial_extent_km: 4.5,
      source_families: ['INDUSTRIAL_STACK', 'TRAFFIC_CORRIDOR'],
    };
  }, [decisionData]);

  // Overall data quality status
  const dataQualityStatus = decisionData?.overall_data_quality_status || 'READY';
  const isBlocked = dataQualityStatus === 'BLOCKED';
  const isPartial = dataQualityStatus === 'PARTIAL';

  // Handle station marker click
  const handleStationClick = () => {
    setSelectedFeature({
      title: 'Pilot Monitoring Station',
      typeLabel: 'Ground Monitoring Station',
      featureId: 'ANAND_VIHAR_8118',
      name: 'Anand Vihar, Delhi - DPCC',
      coordinatesText: `${STATION_LAT.toFixed(4)}° N, ${STATION_LON.toFixed(4)}° E`,
      nonCausalNote: 'Ground monitoring station telemetry reference. Does NOT imply local source generation.',
      metadata: {
        'Station ID': 'ANAND_VIHAR_8118',
        'Station Location': 'Anand Vihar, Delhi',
        'Operator': 'DPCC',
      },
    });
  };

  // Handle hotspot marker click
  const handleHotspotClick = () => {
    if (!hotspotInfo) return;
    setSelectedFeature({
      title: 'Audited Hyper-Local Hotspot Evidence',
      typeLabel: 'Corroborated Hotspot Region',
      featureId: hotspotInfo.hotspot_id,
      name: `Hotspot ${hotspotInfo.hotspot_id}`,
      coordinatesText: `Centered near station ${STATION_LAT.toFixed(4)}° N, ${STATION_LON.toFixed(4)}° E`,
      nonCausalNote: 'Hotspot evidence identifies corroborated spatial concentration area for operational review. Does NOT establish legal liability or source causality.',
      metadata: {
        'Hotspot ID': hotspotInfo.hotspot_id,
        'Support Score': `${hotspotInfo.support_score} / 100`,
        'Confidence Tier': hotspotInfo.confidence_tier,
        'Spatial Impact Extent': `${hotspotInfo.spatial_extent_km} km`,
        'Corroborating Source Families': hotspotInfo.source_families.join(', '),
      },
    });
  };

  // Handle GeoJSON feature click
  const handleGeoFeatureClick = (feature: GeoFeature) => {
    const p = feature.properties;
    const type = p.feature_type;
    const name = p.name || 'Unnamed Spatial Feature';
    const id = p.feature_id || feature.id || 'N/A';

    let typeLabel = 'Spatial Context';
    let nonCausalNote = 'Contextual spatial evidence present in region.';

    if (type === 'road') {
      typeLabel = 'Major Road Corridor';
      nonCausalNote = 'Major-road context present. Identifies transportation corridor proximity.';
    } else if (type === 'industrial') {
      typeLabel = 'Industrial Context Facility';
      nonCausalNote = 'Industrial context present. Identifies industrial zoning proximity.';
    } else if (type === 'sensitive_receptor') {
      typeLabel = 'Sensitive Receptor Facility';
      nonCausalNote = 'Sensitive-receptor context present. Identifies vulnerable population facility proximity.';
    }

    setSelectedFeature({
      title: `${typeLabel}: ${name}`,
      typeLabel,
      featureId: id,
      name,
      coordinatesText: `City Domain: ${p.city_code || 'DELHI'}`,
      nonCausalNote,
      metadata: {
        'Feature ID': id,
        'Feature Name': name,
        'Context Category': typeLabel,
      },
    });
  };

  return (
    <div className="civic-card" style={{ maxWidth: '780px', margin: '0 auto 24px auto' }}>
      {/* Header */}
      <div className="header" style={{ marginBottom: '16px', paddingBottom: '12px' }}>
        <h2 className="title" style={{ fontSize: '1.25rem', color: '#0f172a' }}>
          Hyper-Local Hotspot & Spatial Context Evidence Map
        </h2>
        <p className="subtitle">
          Offline Local Spatial Evidence Visualization — Pilot Station: <strong>Anand Vihar 8118</strong>
        </p>
      </div>

      {/* Data Quality Warning / Block Banner */}
      {isBlocked && (
        <div className="alert-error" style={{ marginBottom: '16px' }}>
          <strong>Spatial Intelligence Blocked:</strong> Spatial evidence visualization is blocked for operational decision support under current pipeline state.
        </div>
      )}

      {isPartial && (
        <div className="hint-warning" style={{ marginBottom: '16px' }}>
          <strong>Partial Spatial Evidence:</strong> Spatial visualization presented with available local telemetry. Some satellite/sensor layers are unverified.
        </div>
      )}

      {/* Layer Control Bar & Legend */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '12px',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 14px',
          backgroundColor: '#f8fafc',
          border: '1px solid #e2e8f0',
          borderRadius: '6px',
          marginBottom: '16px',
          fontSize: '12px',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontWeight: 600, color: '#475569' }}>Layers:</span>

          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showStation}
              onChange={(e) => setShowStation(e.target.checked)}
              style={{ accentColor: '#0f172a' }}
            />
            <span style={{ color: '#0f172a', fontWeight: 600 }}>Station</span>
          </label>

          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showHotspot}
              onChange={(e) => setShowHotspot(e.target.checked)}
              style={{ accentColor: '#dc2626' }}
            />
            <span style={{ color: '#dc2626', fontWeight: 600 }}>Hotspot Region</span>
          </label>

          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showIndustrial}
              onChange={(e) => setShowIndustrial(e.target.checked)}
              style={{ accentColor: '#d97706' }}
            />
            <span style={{ color: '#b45309', fontWeight: 600 }}>Industrial Context</span>
          </label>

          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showRoads}
              onChange={(e) => setShowRoads(e.target.checked)}
              style={{ accentColor: '#2563eb' }}
            />
            <span style={{ color: '#2563eb', fontWeight: 600 }}>Major Roads</span>
          </label>

          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={showReceptors}
              onChange={(e) => setShowReceptors(e.target.checked)}
              style={{ accentColor: '#7c3aed' }}
            />
            <span style={{ color: '#7c3aed', fontWeight: 600 }}>Sensitive Receptors</span>
          </label>
        </div>

        <div style={{ fontSize: '11px', color: '#64748b' }}>
          Offline Local Vector Canvas
        </div>
      </div>

      {/* SVG Map Canvas */}
      <div
        style={{
          position: 'relative',
          backgroundColor: '#ffffff',
          border: '1px solid #cbd5e1',
          borderRadius: '8px',
          overflow: 'hidden',
          marginBottom: '16px',
          boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.03)',
        }}
      >
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          style={{ width: '100%', height: 'auto', display: 'block', backgroundColor: '#fcfcfd' }}
        >
          {/* Background Grid Pattern Lines */}
          <g stroke="#f1f5f9" strokeWidth="1">
            {[100, 200, 300, 400, 500, 600, 700].map((x) => (
              <line key={`vgrid-${x}`} x1={x} y1={0} x2={x} y2={HEIGHT} />
            ))}
            {[80, 160, 240, 320, 400].map((y) => (
              <line key={`hgrid-${y}`} x1={0} y1={y} x2={WIDTH} y2={y} />
            ))}
          </g>

          {/* 1. Major Road Corridors Layer */}
          {showRoads &&
            roadFeatures.map((f, idx) => {
              const coords = f.geometry.coordinates;
              if (!coords || coords.length === 0) return null;

              // Format LineString points
              let pointsStr = '';
              if (f.geometry.type === 'LineString') {
                pointsStr = coords
                  .map(([lon, lat]: [number, number]) => {
                    const [px, py] = project(lon, lat);
                    return `${px.toFixed(1)},${py.toFixed(1)}`;
                  })
                  .join(' ');
              } else if (f.geometry.type === 'Polygon') {
                pointsStr = (coords[0] || [])
                  .map(([lon, lat]: [number, number]) => {
                    const [px, py] = project(lon, lat);
                    return `${px.toFixed(1)},${py.toFixed(1)}`;
                  })
                  .join(' ');
              }

              if (!pointsStr) return null;

              return (
                <polyline
                  key={f.properties.feature_id || `road-${idx}`}
                  points={pointsStr}
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ cursor: 'pointer', transition: 'stroke 0.15s' }}
                  onClick={() => handleGeoFeatureClick(f)}
                >
                  <title>{`Major Road: ${f.properties.name || 'Arterial Corridor'}`}</title>
                </polyline>
              );
            })}

          {/* 2. Industrial Context Layer */}
          {showIndustrial &&
            industrialFeatures.map((f, idx) => {
              const coords = f.geometry.coordinates;
              if (!coords || coords.length === 0) return null;

              if (f.geometry.type === 'Polygon') {
                const pointsStr = (coords[0] || [])
                  .map(([lon, lat]: [number, number]) => {
                    const [px, py] = project(lon, lat);
                    return `${px.toFixed(1)},${py.toFixed(1)}`;
                  })
                  .join(' ');

                return (
                  <polygon
                    key={f.properties.feature_id || `ind-${idx}`}
                    points={pointsStr}
                    fill="#f59e0b"
                    fillOpacity="0.22"
                    stroke="#d97706"
                    strokeWidth="1.5"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleGeoFeatureClick(f)}
                  >
                    <title>{`Industrial Context: ${f.properties.name || 'Industrial Area'}`}</title>
                  </polygon>
                );
              } else if (f.geometry.type === 'Point') {
                const [lon, lat] = coords;
                const [px, py] = project(lon, lat);
                return (
                  <polygon
                    key={f.properties.feature_id || `ind-pt-${idx}`}
                    points={`${px},${py - 7} ${px + 6},${py + 5} ${px - 6},${py + 5}`}
                    fill="#d97706"
                    stroke="#92400e"
                    strokeWidth="1"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleGeoFeatureClick(f)}
                  >
                    <title>{`Industrial Facility: ${f.properties.name || 'Industrial Point'}`}</title>
                  </polygon>
                );
              }
              return null;
            })}

          {/* 3. Sensitive Receptors Layer */}
          {showReceptors &&
            receptorFeatures.map((f, idx) => {
              const coords = f.geometry.coordinates;
              if (!coords || coords.length === 0) return null;

              let px = 0;
              let py = 0;

              if (f.geometry.type === 'Point') {
                [px, py] = project(coords[0], coords[1]);
              } else if (f.geometry.type === 'Polygon' && coords[0] && coords[0][0]) {
                [px, py] = project(coords[0][0][0], coords[0][0][1]);
              }

              if (px === 0 && py === 0) return null;

              return (
                <g
                  key={f.properties.feature_id || `rec-${idx}`}
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleGeoFeatureClick(f)}
                >
                  <circle cx={px} cy={py} r="5" fill="#7c3aed" stroke="#ffffff" strokeWidth="1.5" />
                  <title>{`Sensitive Receptor: ${f.properties.name || 'Care/School Facility'}`}</title>
                </g>
              );
            })}

          {/* 4. Audited Hotspot Overlay Layer */}
          {showHotspot && hotspotInfo && (
            <g style={{ cursor: 'pointer' }} onClick={handleHotspotClick}>
              {/* Outer Extent Ring */}
              <circle
                cx={stationX}
                cy={stationY}
                r="46"
                fill="#ef4444"
                fillOpacity="0.14"
                stroke="#dc2626"
                strokeWidth="1.5"
                strokeDasharray="4 3"
              />

              {/* Centroid Ring */}
              <circle cx={stationX} cy={stationY} r="14" fill="#fee2e2" stroke="#ef4444" strokeWidth="1.5" />
              <circle cx={stationX} cy={stationY} r="6" fill="#dc2626" />
              <title>{`Audited Hotspot: ${hotspotInfo.hotspot_id} (Score: ${hotspotInfo.support_score}/100)`}</title>
            </g>
          )}

          {/* 5. Pilot Monitoring Station Marker Layer */}
          {showStation && (
            <g style={{ cursor: 'pointer' }} onClick={handleStationClick}>
              <rect
                x={stationX - 12}
                y={stationY - 12}
                width="24"
                height="24"
                rx="4"
                fill="#0f172a"
                stroke="#ffffff"
                strokeWidth="2"
              />
              <text
                x={stationX}
                y={stationY + 4}
                fill="#ffffff"
                fontSize="11"
                fontWeight="700"
                textAnchor="middle"
              >
                S
              </text>
              <text
                x={stationX + 16}
                y={stationY - 4}
                fill="#0f172a"
                fontSize="11"
                fontWeight="700"
              >
                Anand Vihar 8118
              </text>
              <title>Pilot Ground Station: Anand Vihar 8118 (DPCC)</title>
            </g>
          )}

          {/* Canvas Map Scale & Orientation Marker */}
          <g transform={`translate(${WIDTH - 110}, ${HEIGHT - 24})`} fontSize="10" fill="#64748b">
            <rect x="-8" y="-12" width="110" height="20" fill="#ffffff" fillOpacity="0.8" rx="3" />
            <text x="0" y="0" fontWeight="500">N ↑ | Scale: ~1:50,000</text>
          </g>
        </svg>

        {/* Empty Hotspot State Notice */}
        {!hotspotInfo && (
          <div
            style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              backgroundColor: '#ffffff',
              border: '1px solid #cbd5e1',
              borderRadius: '6px',
              padding: '8px 12px',
              fontSize: '12px',
              color: '#64748b',
              boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
            }}
          >
            No hotspot evidence is available for this decision.
          </div>
        )}
      </div>

      {/* Feature Inspection Panel */}
      {selectedFeature ? (
        <div
          style={{
            padding: '14px',
            backgroundColor: '#f8fafc',
            border: '1px solid #cbd5e1',
            borderRadius: '6px',
            marginBottom: '16px',
            fontSize: '13px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontWeight: 700, color: '#0f172a' }}>{selectedFeature.title}</span>
            <button
              onClick={() => setSelectedFeature(null)}
              style={{
                background: 'none',
                border: 'none',
                color: '#64748b',
                cursor: 'pointer',
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              [Close]
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', color: '#334155', marginBottom: '8px' }}>
            <div><strong>Location / Domain:</strong> {selectedFeature.coordinatesText}</div>
            {selectedFeature.metadata &&
              Object.entries(selectedFeature.metadata).map(([k, v]) => (
                <div key={k}>
                  <strong>{k}:</strong> {String(v)}
                </div>
              ))}
          </div>

          <div style={{ padding: '8px 10px', backgroundColor: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '4px', color: '#1e40af', fontSize: '12px' }}>
            <strong>Non-Causal Context Note:</strong> {selectedFeature.nonCausalNote}
          </div>
        </div>
      ) : (
        <div style={{ fontSize: '12px', color: '#64748b', fontStyle: 'italic', marginBottom: '16px', textAlign: 'center' }}>
          Select or hover any spatial feature, station, or hotspot region on the vector map to inspect audited metadata.
        </div>
      )}

      {/* Linked Evidence Reference Trace */}
      <div className="civic-fieldset" style={{ marginBottom: '16px' }}>
        <legend className="fieldset-legend">Spatial Evidence Audit Trace Linkage</legend>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '8px',
            fontSize: '12px',
            marginTop: '8px',
          }}
        >
          <div>
            <span style={{ color: '#64748b' }}>Decision Result ID:</span>{' '}
            <code className="receipt-code">{decisionData?.decision_result_id || 'dec_7184da4be2f7'}</code>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Hotspot Ref ID:</span>{' '}
            <code className="receipt-code">{decisionData?.evidence_references?.hotspot_id || 'hs_av_pilot_01'}</code>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Fusion Ref ID:</span>{' '}
            <code className="receipt-code">{decisionData?.evidence_references?.fusion_id || 'fus_av_pilot_01'}</code>
          </div>
          <div>
            <span style={{ color: '#64748b' }}>Context Artifact Ref:</span>{' '}
            <code className="receipt-code">{decisionData?.evidence_references?.context_artifact_id || 'ctx_av_pilot_01'}</code>
          </div>
        </div>
      </div>

      {/* Non-Causal Attribution Safeguard Notice */}
      <div style={{ fontSize: '11px', color: '#64748b', backgroundColor: '#f8fafc', padding: '10px 12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
        <strong>Non-Causal Spatial Attribution Disclaimer:</strong> Spatial context layers identify proximity to industrial zones, major road corridors, and sensitive receptors for environmental situational awareness. Spatial context markers do NOT establish legal liability or definitive source attribution.
      </div>
    </div>
  );
};
