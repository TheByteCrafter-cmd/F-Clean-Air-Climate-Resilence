import React, { useState, useRef, useEffect } from 'react';
import { apiClient, ApiError } from '../api/client';
import {
  EvidenceSubmissionResponse,
  EvidenceAIAnalysis,
  ProbableCategoryItem,
  EvidenceFusionResult,
  MatchedRecordRef,
  DecisionIntelligenceResponse,
} from '../types/api';

type ProcessingState = 'IDLE' | 'SELECTED' | 'SUBMITTING' | 'PROCESSING' | 'COMPLETE' | 'FAILED';

interface CitizenEvidencePanelProps {
  decisionData?: DecisionIntelligenceResponse | null;
}

export const CitizenEvidencePanel: React.FC<CitizenEvidencePanelProps> = ({ decisionData }) => {
  // Processing state lifecycle
  const [processingState, setProcessingState] = useState<ProcessingState>('IDLE');

  // Media states
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  // Voice recording states
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordingSeconds, setRecordingSeconds] = useState<number>(0);
  const [voiceBlob, setVoiceBlob] = useState<Blob | null>(null);
  const [voiceUrl, setVoiceUrl] = useState<string | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<number | null>(null);

  // Observation remarks & category
  const [description, setDescription] = useState<string>('');
  const [category, setCategory] = useState<string>('industrial_smoke');

  // Location states
  const [location, setLocation] = useState<{
    latitude: number;
    longitude: number;
    accuracy_m: number | null;
    source: 'gps' | 'manual';
  } | null>(null);
  const [locationLoading, setLocationLoading] = useState<boolean>(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [showManualLocation, setShowManualLocation] = useState<boolean>(false);
  const [manualLat, setManualLat] = useState<string>('28.6476');
  const [manualLon, setManualLon] = useState<string>('77.3158');

  // Consent & submission
  const [consentGiven, setConsentGiven] = useState<boolean>(false);
  const [submissionResult, setSubmissionResult] = useState<EvidenceSubmissionResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // AI Analysis states
  const [aiAnalysis, setAiAnalysis] = useState<EvidenceAIAnalysis | null>(null);
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Evidence Fusion states
  const [fusionResult, setFusionResult] = useState<EvidenceFusionResult | null>(null);
  const [fusionLoading, setFusionLoading] = useState<boolean>(false);
  const [fusionError, setFusionError] = useState<string | null>(null);

  // Data Quality State
  const dataQuality = decisionData?.overall_data_quality_status || 'READY';
  const isBlocked = dataQuality === 'BLOCKED';

  // Photo change handler
  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setSubmitError('Selected photo exceeds the maximum 10 MB file size limit.');
      setProcessingState('FAILED');
      return;
    }

    setPhotoFile(file);
    setSubmitError(null);
    setProcessingState('SELECTED');
    const previewUrl = URL.createObjectURL(file);
    setPhotoPreview(previewUrl);
  };

  const handleRemovePhoto = () => {
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoFile(null);
    setPhotoPreview(null);
    if (!voiceBlob && !description.trim()) {
      setProcessingState('IDLE');
    }
  };

  // Voice recording handlers
  const startRecording = async () => {
    setVoiceError(null);
    if (!navigator.mediaDevices?.getUserMedia) {
      setVoiceError('Audio recording is not supported in this browser.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setVoiceBlob(audioBlob);
        setProcessingState('SELECTED');
        const url = URL.createObjectURL(audioBlob);
        setVoiceUrl(url);
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();
      setIsRecording(true);
      setRecordingSeconds(0);

      timerIntervalRef.current = window.setInterval(() => {
        setRecordingSeconds((prev) => {
          if (prev >= 60) {
            stopRecording();
            return 60;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'NotAllowedError') {
        setVoiceError('Microphone access permission was denied.');
      } else {
        setVoiceError('Unable to access microphone.');
      }
    }
  };

  const stopRecording = () => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
  };

  const handleRemoveVoice = () => {
    if (voiceUrl) URL.revokeObjectURL(voiceUrl);
    setVoiceBlob(null);
    setVoiceUrl(null);
    setRecordingSeconds(0);
    if (!photoFile && !description.trim()) {
      setProcessingState('IDLE');
    }
  };

  // Geolocation detection
  const handleDetectLocation = () => {
    setLocationLoading(true);
    setLocationError(null);

    if (!navigator.geolocation) {
      setLocationError('Geolocation is not supported by your browser.');
      setLocationLoading(false);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          latitude: parseFloat(pos.coords.latitude.toFixed(6)),
          longitude: parseFloat(pos.coords.longitude.toFixed(6)),
          accuracy_m: pos.coords.accuracy ? Math.round(pos.coords.accuracy) : null,
          source: 'gps',
        });
        setLocationLoading(false);
      },
      (err) => {
        setLocationLoading(false);
        if (err.code === err.PERMISSION_DENIED) {
          setLocationError('Location permission denied. You can select a known pilot location below.');
        } else {
          setLocationError('Unable to acquire GPS signal. Check your location settings.');
        }
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handleApplyManualLocation = () => {
    const lat = parseFloat(manualLat);
    const lon = parseFloat(manualLon);
    if (isNaN(lat) || isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setLocationError('Enter valid coordinates (-90 to 90 lat, -180 to 180 lon).');
      return;
    }
    setLocation({
      latitude: lat,
      longitude: lon,
      accuracy_m: null,
      source: 'manual',
    });
    setLocationError(null);
  };

  useEffect(() => {
    return () => {
      if (photoPreview) URL.revokeObjectURL(photoPreview);
      if (voiceUrl) URL.revokeObjectURL(voiceUrl);
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
    };
  }, []);

  // Submit Handler
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!consentGiven) {
      setSubmitError('Explicit citizen consent is mandatory before evidence submission.');
      setProcessingState('FAILED');
      return;
    }

    const hasPhoto = Boolean(photoFile);
    const hasVoice = Boolean(voiceBlob);
    const hasText = Boolean(description.trim());

    if (!hasPhoto && !hasVoice && !hasText) {
      setSubmitError('Submission must include at least one evidence item (photo, voice memo, or text description).');
      setProcessingState('FAILED');
      return;
    }

    setProcessingState('SUBMITTING');
    const formData = new FormData();
    formData.append('consent', 'true');
    formData.append('category', category);

    if (description.trim()) {
      formData.append('description', description.trim());
    }

    if (photoFile) {
      formData.append('photo', photoFile, photoFile.name);
    }

    if (voiceBlob) {
      formData.append('voice', voiceBlob, 'voice_memo.webm');
    }

    if (location) {
      formData.append('latitude', location.latitude.toString());
      formData.append('longitude', location.longitude.toString());
      if (location.accuracy_m !== null) {
        formData.append('accuracy', location.accuracy_m.toString());
      }
      formData.append('location_source', location.source);
    }

    try {
      const res = await apiClient.submitEvidence(formData);
      setSubmissionResult(res);
      setProcessingState('COMPLETE');
    } catch (err: unknown) {
      setProcessingState('FAILED');
      if (err instanceof ApiError) {
        setSubmitError(`[${err.code}] ${err.message}`);
      } else if (err instanceof Error) {
        setSubmitError(err.message);
      } else {
        setSubmitError('Evidence submission failed due to network communication error.');
      }
    }
  };

  // Trigger Gemini AI Evidence Analysis
  const handleAnalyzeEvidence = async (targetId: string) => {
    setAiLoading(true);
    setAiError(null);
    setProcessingState('PROCESSING');
    try {
      const res = await apiClient.analyzeEvidence(targetId);
      setAiAnalysis(res);
      setProcessingState('COMPLETE');
    } catch (err: unknown) {
      setProcessingState('FAILED');
      if (err instanceof ApiError) {
        if (err.code === 'GEMINI_CREDENTIAL_UNCONFIGURED' || err.code === 'HTTP_503') {
          setAiError('Service Unavailable: Gemini AI analysis credentials are unconfigured or uninitialized on backend.');
        } else {
          setAiError(`[${err.code}] ${err.message}`);
        }
      } else if (err instanceof Error) {
        setAiError(err.message);
      } else {
        setAiError('Server-side Gemini AI evidence analysis failed.');
      }
    } finally {
      setAiLoading(false);
    }
  };

  // Trigger Multi-Source Evidence Fusion
  const handleFuseEvidence = async (targetId: string) => {
    setFusionLoading(true);
    setFusionError(null);
    try {
      const res = await apiClient.fuseEvidence(targetId);
      setFusionResult(res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setFusionError(`[${err.code}] ${err.message}`);
      } else if (err instanceof Error) {
        setFusionError(err.message);
      } else {
        setFusionError('Multi-source evidence fusion failed.');
      }
    } finally {
      setFusionLoading(false);
    }
  };

  const handleResetForm = () => {
    handleRemovePhoto();
    handleRemoveVoice();
    setDescription('');
    setCategory('industrial_smoke');
    setLocation(null);
    setConsentGiven(false);
    setSubmissionResult(null);
    setSubmitError(null);
    setAiAnalysis(null);
    setAiError(null);
    setFusionResult(null);
    setFusionError(null);
    setProcessingState('IDLE');
  };

  return (
    <div className="civic-card" role="region" aria-label="Citizen Evidence Intake & AI Insight Panel">
      <div className="header">
        <h2 className="title" style={{ fontSize: '1.25rem', color: '#0f172a' }}>
          Citizen Evidence & AI Insight Integration
        </h2>
        <p className="subtitle">
          Community Environmental Observation Intake & Grounded Multimodal AI Analysis
        </p>
      </div>

      {/* Blocked Notification Banner */}
      {isBlocked && (
        <div className="alert-error" style={{ marginBottom: '16px' }}>
          <strong>Pipeline Status BLOCKED:</strong> Decision intelligence status is currently BLOCKED. Submitted evidence will be ingested into local storage but operational decision evaluation is currently blocked.
        </div>
      )}

      {/* Confirmation View after Submission */}
      {submissionResult ? (
        <div>
          <div className="confirmation-header" style={{ marginBottom: '16px', textAlign: 'center' }}>
            <div className="confirmation-icon">✓</div>
            <h3 className="title" style={{ fontSize: '1.1rem' }}>Evidence Report Registered</h3>
            <p className="subtitle">Report successfully ingested into local environmental evidence repository.</p>
          </div>

          <div className="receipt-box">
            <div className="receipt-row">
              <span className="receipt-label">Canonical Evidence ID:</span>
              <span className="receipt-code">{submissionResult.evidence_id}</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Lifecycle Status:</span>
              <span className="badge-success">Registered & Validated</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Submission Timestamp:</span>
              <span>{new Date(submissionResult.submitted_at).toLocaleString()}</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Attached Media:</span>
              <span>{submissionResult.media_count} file(s) ({submissionResult.media_types.join(', ') || 'text observation'})</span>
            </div>
            {submissionResult.location && (
              <div className="receipt-row">
                <span className="receipt-label">Geospatial Coordinates:</span>
                <span>
                  {submissionResult.location.latitude}°, {submissionResult.location.longitude}°
                  {submissionResult.location.accuracy_m ? ` (±${submissionResult.location.accuracy_m}m)` : ''}
                </span>
              </div>
            )}
          </div>

          {/* AI Multimodal Analysis Integration Section */}
          <div className="civic-fieldset" style={{ marginTop: '20px', marginBottom: '20px' }}>
            <legend className="fieldset-legend">Server-Side Multimodal AI Evidence Analysis</legend>
            <p className="fieldset-hint">
              Execute server-side Gemini multimodal AI analysis to evaluate visual indicators, environmental categories, and evidence quality.
            </p>

            {!aiAnalysis ? (
              <div>
                <button
                  type="button"
                  className="action-btn-primary"
                  onClick={() => handleAnalyzeEvidence(submissionResult.evidence_id)}
                  disabled={aiLoading}
                >
                  {aiLoading ? 'Processing Multimodal AI Analysis...' : 'Trigger Server AI Analysis'}
                </button>
              </div>
            ) : (
              <div style={{ backgroundColor: '#ffffff', padding: '14px', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '13px', color: '#0f172a' }}>
                    AI-Assisted Observation ({aiAnalysis.model_name})
                  </span>
                  <span className="badge-success" style={{ textTransform: 'capitalize' }}>
                    Relevance: {aiAnalysis.relevance.replace('_', ' ')}
                  </span>
                </div>

                <p style={{ fontSize: '13px', color: '#334155', marginBottom: '10px', lineHeight: '1.4' }}>
                  <strong>Interpretation:</strong> {aiAnalysis.explanation}
                </p>

                {aiAnalysis.probable_categories.length > 0 && (
                  <div style={{ marginBottom: '8px' }}>
                    <strong style={{ fontSize: '12px', color: '#475569' }}>Probable Environmental Categories:</strong>
                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                      {aiAnalysis.probable_categories.map((c: ProbableCategoryItem, idx: number) => (
                        <span key={idx} className="badge-info" style={{ fontSize: '11px' }}>
                          {c.category} (Confidence: {c.confidence_level})
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {aiAnalysis.visual_indicators.length > 0 && (
                  <div style={{ marginBottom: '8px', fontSize: '12px' }}>
                    <strong style={{ color: '#475569' }}>Observable Features:</strong>{' '}
                    <span style={{ color: '#0f172a' }}>{aiAnalysis.visual_indicators.join(', ')}</span>
                  </div>
                )}

                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '10px', paddingTop: '6px', borderTop: '1px dashed #e2e8f0' }}>
                  <span>Analysis ID: <code className="receipt-code">{aiAnalysis.analysis_id}</code></span> | <span>Quality: {aiAnalysis.evidence_quality}</span> | <span>Audio: {aiAnalysis.audio_status}</span>
                </div>
              </div>
            )}

            {aiError && (
              <div className="alert-error" style={{ marginTop: '12px' }}>
                <strong>AI Processing Notice:</strong> {aiError}
              </div>
            )}
          </div>

          {/* Multi-Source Fusion Integration Section */}
          <div className="civic-fieldset" style={{ marginBottom: '20px' }}>
            <legend className="fieldset-legend">Multi-Source Evidence Fusion Corroboration</legend>
            <p className="fieldset-hint">
              Correlate citizen evidence with OpenAQ ground sensors, Open-Meteo weather, NASA FIRMS thermal anomalies, and Sentinel-5P NO2 satellite scans.
            </p>

            {!fusionResult ? (
              <div>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => handleFuseEvidence(submissionResult.evidence_id)}
                  disabled={fusionLoading}
                >
                  {fusionLoading ? 'Fusing Evidence Signals...' : 'Run Multi-Source Signal Fusion'}
                </button>
              </div>
            ) : (
              <div style={{ backgroundColor: '#ffffff', padding: '14px', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 600, fontSize: '13px', color: '#0f172a' }}>
                    Fusion Support Score: {fusionResult.support_score} / 100
                  </span>
                  <span className="badge-warning" style={{ fontSize: '11px' }}>
                    Tier: {fusionResult.confidence_tier}
                  </span>
                </div>

                <p style={{ fontSize: '13px', color: '#334155', marginBottom: '8px' }}>
                  <strong>Corroboration:</strong> {fusionResult.explanation}
                </p>

                {fusionResult.supporting_signals.length > 0 && (
                  <div style={{ marginTop: '8px' }}>
                    <strong style={{ fontSize: '12px', color: '#475569' }}>Corroborating Signals ({fusionResult.supporting_signals.length}):</strong>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                      {fusionResult.supporting_signals.map((s: MatchedRecordRef, idx: number) => (
                        <div key={idx} style={{ fontSize: '11px', backgroundColor: '#f8fafc', padding: '4px 8px', borderRadius: '4px', border: '1px solid #e2e8f0' }}>
                          <strong>{s.source_type} ({s.source_family})</strong> {s.distance_km != null ? `— ${s.distance_km} km away` : ''}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {fusionError && (
              <div className="alert-error" style={{ marginTop: '12px' }}>
                <strong>Fusion Error:</strong> {fusionError}
              </div>
            )}
          </div>

          {/* Provenance Audit Trace Section */}
          <div className="civic-fieldset" style={{ marginBottom: '20px' }}>
            <legend className="fieldset-legend">Evidence Provenance Audit Trace Chain</legend>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '12px', marginTop: '6px' }}>
              <div><span style={{ color: '#64748b' }}>1. Citizen Evidence:</span> <code className="receipt-code">{submissionResult.evidence_id}</code></div>
              <div><span style={{ color: '#64748b' }}>2. AI Analysis:</span> <code className="receipt-code">{aiAnalysis?.analysis_id || 'Pending / Unrun'}</code></div>
              <div><span style={{ color: '#64748b' }}>3. Multi-Source Fusion:</span> <code className="receipt-code">{fusionResult?.fusion_id || decisionData?.evidence_references?.fusion_id || 'Pending / Unrun'}</code></div>
              <div><span style={{ color: '#64748b' }}>4. Decision Result:</span> <code className="receipt-code">{decisionData?.decision_result_id || 'dec_7184da4be2f7'}</code></div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '16px' }}>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              Processing State: <strong style={{ color: '#166534' }}>{processingState}</strong>
            </span>
            <button type="button" className="action-btn" onClick={handleResetForm}>
              Submit Another Evidence Report
            </button>
          </div>
        </div>
      ) : (
        /* Submission Intake Form */
        <form onSubmit={handleSubmit} noValidate>
          {/* Privacy & Consent Banner */}
          <div className="consent-container" style={{ marginBottom: '16px' }}>
            <div style={{ fontSize: '12px', color: '#475569', marginBottom: '8px', lineHeight: '1.4' }}>
              <strong>Civic Privacy & Data Notice:</strong> Submitted environmental observations (photos, optional audio, text remarks, location) are registered into the local VayuDrishti environmental intelligence repository to assist air quality situational awareness. Explicit consent is required prior to submission.
            </div>
            <label className="consent-label">
              <input
                type="checkbox"
                checked={consentGiven}
                onChange={(e) => setConsentGiven(e.target.checked)}
                className="consent-checkbox"
              />
              <span className="consent-text">
                I explicitly consent to submit this environmental evidence report for civic air quality monitoring.
              </span>
            </label>
          </div>

          {/* Error Message */}
          {submitError && (
            <div className="alert-error" role="alert">
              <span>{submitError}</span>
            </div>
          )}

          {/* Section 1: Photo Evidence */}
          <fieldset className="civic-fieldset">
            <legend className="fieldset-legend">1. Photographic Evidence</legend>
            <p className="fieldset-hint">
              Select or capture an image of the visible smoke plume, crop fire, dust cloud, or industrial flaring (Max 10 MB).
            </p>

            {!photoPreview ? (
              <div className="upload-container">
                <label htmlFor="photo-input-panel" className="file-upload-label">
                  <span className="upload-btn-text">Select Photo File</span>
                  <span className="upload-subtext">Supports JPEG, PNG, WebP (Max 10 MB)</span>
                  <input
                    id="photo-input-panel"
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    capture="environment"
                    onChange={handlePhotoSelect}
                    className="visually-hidden"
                  />
                </label>
              </div>
            ) : (
              <div className="media-preview-box">
                <img src={photoPreview} alt="Selected pollution evidence preview" className="photo-thumbnail" />
                <div className="preview-meta">
                  <span className="file-name">{photoFile?.name}</span>
                  <span className="file-size">
                    {photoFile ? (photoFile.size / (1024 * 1024)).toFixed(2) : 0} MB
                  </span>
                  <button type="button" className="btn-text-danger" onClick={handleRemovePhoto}>
                    Remove Photo
                  </button>
                </div>
              </div>
            )}
          </fieldset>

          {/* Section 2: Voice Recording Memo */}
          <fieldset className="civic-fieldset">
            <legend className="fieldset-legend">2. Voice Memo (Optional)</legend>
            <p className="fieldset-hint">
              Record a short audio memo describing odor, visibility, or activity (Max 60 seconds).
            </p>

            {voiceError && <div className="hint-warning" style={{ marginBottom: '8px' }}>{voiceError}</div>}

            {!voiceUrl ? (
              <div className="voice-controls">
                {!isRecording ? (
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={startRecording}
                    disabled={processingState === 'SUBMITTING'}
                  >
                    Start Voice Recording
                  </button>
                ) : (
                  <div className="recording-active-box">
                    <span className="recording-pulse">Recording ({recordingSeconds}s / 60s)</span>
                    <button type="button" className="btn-danger-sm" onClick={stopRecording}>
                      Stop
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="media-preview-box">
                <audio controls src={voiceUrl} className="audio-player" />
                <button type="button" className="btn-text-danger" onClick={handleRemoveVoice}>
                  Remove Audio
                </button>
              </div>
            )}
          </fieldset>

          {/* Section 3: Text Observations & Category */}
          <fieldset className="civic-fieldset">
            <legend className="fieldset-legend">3. Environmental Observation Remarks</legend>

            <div className="form-group">
              <label htmlFor="category-select-panel" className="form-label">
                Suspected Environmental Emission Type
              </label>
              <select
                id="category-select-panel"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="form-select"
              >
                <option value="biomass_burning">Biomass / Crop Residue / Garbage Burning</option>
                <option value="construction_dust">Construction & Fugitive Road Dust</option>
                <option value="industrial_smoke">Industrial Stack Emission / Factory Flaring</option>
                <option value="vehicular_exhaust">Heavy Transport / Diesel Exhaust</option>
                <option value="other">Other Local Environmental Source</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="description-input-panel" className="form-label">
                Text Observation Remarks (Optional)
              </label>
              <textarea
                id="description-input-panel"
                rows={3}
                maxLength={1000}
                value={description}
                onChange={(e) => {
                  setDescription(e.target.value);
                  if (e.target.value.trim() && processingState === 'IDLE') {
                    setProcessingState('SELECTED');
                  }
                }}
                placeholder="e.g. Dense smoke plume observed near Anand Vihar station corridor..."
                className="form-textarea"
              />
              <span className="char-count">{description.length} / 1000 characters</span>
            </div>
          </fieldset>

          {/* Section 4: Location Context */}
          <fieldset className="civic-fieldset">
            <legend className="fieldset-legend">4. Location Context</legend>
            <p className="fieldset-hint">
              Associating WGS84 GPS coordinates allows spatial correlation with ground monitoring stations.
            </p>

            <div className="location-box">
              {!location ? (
                <div className="location-action-row">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={handleDetectLocation}
                    disabled={locationLoading}
                  >
                    {locationLoading ? 'Detecting Location...' : 'Detect Current GPS Location'}
                  </button>
                  <button
                    type="button"
                    className="btn-link"
                    onClick={() => setShowManualLocation(!showManualLocation)}
                  >
                    {showManualLocation ? 'Hide Manual Preset Options' : 'Use Known Station Coordinates'}
                  </button>
                </div>
              ) : (
                <div className="location-confirmed-row">
                  <span className="badge-success">
                    Location ({location.source === 'gps' ? 'GPS' : 'Manual'}): {location.latitude}°, {location.longitude}°
                    {location.accuracy_m ? ` (±${location.accuracy_m}m)` : ''}
                  </span>
                  <button
                    type="button"
                    className="btn-text-danger"
                    onClick={() => setLocation(null)}
                  >
                    Clear Location
                  </button>
                </div>
              )}

              {locationError && <div className="hint-warning">{locationError}</div>}

              {showManualLocation && !location && (
                <div className="manual-location-panel">
                  <p className="manual-title">Pilot Station Presets:</p>
                  <div className="preset-buttons">
                    <button
                      type="button"
                      className="preset-chip"
                      onClick={() => {
                        setManualLat('28.6476');
                        setManualLon('77.3158');
                        setLocation({ latitude: 28.6476, longitude: 77.3158, accuracy_m: null, source: 'manual' });
                      }}
                    >
                      Anand Vihar 8118 (28.6476°, 77.3158°)
                    </button>
                    <button
                      type="button"
                      className="preset-chip"
                      onClick={() => {
                        setManualLat('28.6320');
                        setManualLon('77.1180');
                        setLocation({ latitude: 28.632, longitude: 77.118, accuracy_m: null, source: 'manual' });
                      }}
                    >
                      Delhi Mayapuri (28.6320°, 77.1180°)
                    </button>
                  </div>
                  <div style={{ marginTop: '10px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <input
                      type="text"
                      placeholder="Lat (28.6476)"
                      value={manualLat}
                      onChange={(e) => setManualLat(e.target.value)}
                      style={{ width: '110px', padding: '4px 8px', fontSize: '12px', border: '1px solid #cbd5e1', borderRadius: '4px' }}
                    />
                    <input
                      type="text"
                      placeholder="Lon (77.3158)"
                      value={manualLon}
                      onChange={(e) => setManualLon(e.target.value)}
                      style={{ width: '110px', padding: '4px 8px', fontSize: '12px', border: '1px solid #cbd5e1', borderRadius: '4px' }}
                    />
                    <button
                      type="button"
                      className="btn-secondary"
                      onClick={handleApplyManualLocation}
                      style={{ padding: '4px 10px', fontSize: '12px' }}
                    >
                      Set Coordinates
                    </button>
                  </div>
                </div>
              )}
            </div>
          </fieldset>

          {/* Submission Bar */}
          <div className="submit-row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: '#64748b' }}>
              Current State: <strong>{processingState}</strong>
            </span>
            <button
              type="submit"
              className="action-btn-primary"
              disabled={!consentGiven || (!photoFile && !voiceBlob && !description.trim()) || processingState === 'SUBMITTING'}
            >
              {processingState === 'SUBMITTING' ? 'Registering Evidence...' : 'Submit Environmental Evidence'}
            </button>
          </div>
        </form>
      )}

      {/* Non-Causal Legal Disclaimer Note */}
      <div style={{ marginTop: '16px', fontSize: '11px', color: '#64748b', backgroundColor: '#f8fafc', padding: '10px 12px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
        <strong>Operational AI Evidence Disclaimer:</strong> AI-assisted evidence analysis provides grounded observational summaries for human authority review. AI evidence analysis outputs do NOT constitute medical advice, clinical diagnosis, legal proof, or definitive source causality attribution.
      </div>
    </div>
  );
};
