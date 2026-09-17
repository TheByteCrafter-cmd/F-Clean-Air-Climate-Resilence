import React, { useState, useRef, useEffect } from 'react';
import { apiClient, ApiError } from '../api/client';
import {
  EvidenceSubmissionResponse,
  EvidenceAIAnalysis,
  ProbableCategoryItem,
  EvidenceFusionResult,
  MatchedRecordRef,
} from '../types/api';

export const CitizenIntake: React.FC = () => {
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

  // Remarks & Category
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
  const [manualLat, setManualLat] = useState<string>('28.6320');
  const [manualLon, setManualLon] = useState<string>('77.1180');

  // Consent & Submission states
  const [consentGiven, setConsentGiven] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submissionResult, setSubmissionResult] = useState<EvidenceSubmissionResponse | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Photo change handler
  const handlePhotoSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 10 * 1024 * 1024) {
      setSubmitError('Selected photo exceeds the 10 MB limit.');
      return;
    }

    setPhotoFile(file);
    setSubmitError(null);
    const previewUrl = URL.createObjectURL(file);
    setPhotoPreview(previewUrl);
  };

  const handleRemovePhoto = () => {
    if (photoPreview) URL.revokeObjectURL(photoPreview);
    setPhotoFile(null);
    setPhotoPreview(null);
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
        const url = URL.createObjectURL(audioBlob);
        setVoiceUrl(url);
        // Stop audio tracks
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
        setVoiceError('Microphone permission was denied.');
      } else {
        setVoiceError('Failed to access microphone.');
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
          setLocationError('Location permission denied. You may use manual location below.');
        } else {
          setLocationError('Unable to retrieve location. Please check your GPS signal.');
        }
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  };

  const handleApplyManualLocation = () => {
    const lat = parseFloat(manualLat);
    const lon = parseFloat(manualLon);
    if (isNaN(lat) || isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      setLocationError('Please enter valid coordinates (-90 to 90 lat, -180 to 180 lon).');
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

  // Cleanup on unmount
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
      setSubmitError('Consent is required before submitting your report.');
      return;
    }

    const hasPhoto = Boolean(photoFile);
    const hasVoice = Boolean(voiceBlob);
    const hasText = Boolean(description.trim());

    if (!hasPhoto && !hasVoice && !hasText) {
      setSubmitError('Please attach a photo, record a voice memo, or type an observation description.');
      return;
    }

    setIsSubmitting(true);
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
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setSubmitError(`[${err.code}] ${err.message}`);
      } else if (err instanceof Error) {
        setSubmitError(err.message);
      } else {
        setSubmitError('Submission failed due to an unexpected network error.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // AI Analysis states
  const [aiAnalysis, setAiAnalysis] = useState<EvidenceAIAnalysis | null>(null);
  const [aiLoading, setAiLoading] = useState<boolean>(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [lookupEvidenceId, setLookupEvidenceId] = useState<string>('');

  // Multi-Source Evidence Fusion states
  const [fusionResult, setFusionResult] = useState<EvidenceFusionResult | null>(null);
  const [fusionLoading, setFusionLoading] = useState<boolean>(false);
  const [fusionError, setFusionError] = useState<string | null>(null);

  const handleAnalyzeEvidence = async (targetId?: string) => {
    const id = targetId || submissionResult?.evidence_id || lookupEvidenceId.trim();
    if (!id) return;
    setAiLoading(true);
    setAiError(null);
    try {
      const res = await apiClient.analyzeEvidence(id);
      setAiAnalysis(res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setAiError(`[${err.code}] ${err.message}`);
      } else if (err instanceof Error) {
        setAiError(err.message);
      } else {
        setAiError('Gemini evidence analysis failed.');
      }
    } finally {
      setAiLoading(false);
    }
  };

  const handleFuseEvidence = async (targetId?: string) => {
    const id = targetId || submissionResult?.evidence_id || lookupEvidenceId.trim();
    if (!id) return;
    setFusionLoading(true);
    setFusionError(null);
    try {
      const res = await apiClient.fuseEvidence(id);
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
  };

  // Success Confirmation Screen
  if (submissionResult) {
    return (
      <div className="civic-card" role="region" aria-label="Submission confirmation">
        <div className="confirmation-header">
          <div className="confirmation-icon">✓</div>
          <h2 className="title">Evidence Report Received</h2>
          <p className="subtitle">Thank you for contributing to your community's environmental health.</p>
        </div>

        <div className="receipt-box">
          <div className="receipt-row">
            <span className="receipt-label">Evidence ID:</span>
            <span className="receipt-code">{submissionResult.evidence_id}</span>
          </div>
          <div className="receipt-row">
            <span className="receipt-label">Status:</span>
            <span className="badge-success">Received & Registered</span>
          </div>
          <div className="receipt-row">
            <span className="receipt-label">Timestamp:</span>
            <span>{new Date(submissionResult.submitted_at).toLocaleString()}</span>
          </div>
          <div className="receipt-row">
            <span className="receipt-label">Media Attached:</span>
            <span>{submissionResult.media_count} item(s) ({submissionResult.media_types.join(', ') || 'text observation'})</span>
          </div>
          {submissionResult.location && (
            <div className="receipt-row">
              <span className="receipt-label">Location:</span>
              <span>
                {submissionResult.location.latitude}°, {submissionResult.location.longitude}°
                {submissionResult.location.accuracy_m ? ` (±${submissionResult.location.accuracy_m}m)` : ''}
              </span>
            </div>
          )}
        </div>

        {/* Phase 1E-G Gemini AI Analysis Control */}
        <div style={{ marginTop: '20px', borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#1f2937', marginBottom: '8px' }}>
            Gemini Multimodal Evidence Analysis
          </h3>
          {!aiAnalysis ? (
            <div>
              <p style={{ fontSize: '0.875rem', color: '#4b5563', marginBottom: '12px' }}>
                Trigger server-side Gemini AI analysis to verify visual indicators, emission categories, and evidence relevance.
              </p>
              <button
                type="button"
                className="action-btn-primary"
                onClick={() => handleAnalyzeEvidence(submissionResult.evidence_id)}
                disabled={aiLoading}
              >
                {aiLoading ? 'Analyzing Evidence...' : 'Run Gemini Evidence Analysis'}
              </button>
            </div>
          ) : (
            <div className="ai-analysis-card" style={{ backgroundColor: '#f9fafb', padding: '14px', borderRadius: '8px', border: '1px solid #e5e7eb', marginTop: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#111827' }}>
                  Model: {aiAnalysis.model_name}
                </span>
                <span className="badge-success" style={{ textTransform: 'capitalize' }}>
                  Relevance: {aiAnalysis.relevance.replace('_', ' ')}
                </span>
              </div>

              <p style={{ fontSize: '0.875rem', color: '#374151', margin: '8px 0' }}>
                <strong>Explanation:</strong> {aiAnalysis.explanation}
              </p>

              {aiAnalysis.probable_categories.length > 0 && (
                <div style={{ margin: '8px 0' }}>
                  <strong style={{ fontSize: '0.85rem', color: '#4b5563' }}>Probable Categories:</strong>
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                    {aiAnalysis.probable_categories.map((c: ProbableCategoryItem, idx: number) => (
                      <span key={idx} className="preset-chip" style={{ fontSize: '0.8rem', backgroundColor: '#eff6ff', color: '#1e40af' }}>
                        {c.category} (Confidence: {c.confidence_level})
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {aiAnalysis.visual_indicators.length > 0 && (
                <div style={{ margin: '8px 0' }}>
                  <strong style={{ fontSize: '0.85rem', color: '#4b5563' }}>Visual Indicators:</strong>
                  <span style={{ fontSize: '0.85rem', color: '#1f2937', marginLeft: '6px' }}>
                    {aiAnalysis.visual_indicators.join(', ')}
                  </span>
                </div>
              )}

              <div style={{ display: 'flex', gap: '16px', fontSize: '0.8rem', color: '#6b7280', marginTop: '10px' }}>
                <span>Audio Status: {aiAnalysis.audio_status}</span>
                <span>Quality: {aiAnalysis.evidence_quality}</span>
              </div>
            </div>
          )}

          {aiError && (
            <div className="response-box" style={{ color: '#991b1b', backgroundColor: '#fef2f2', marginTop: '12px' }}>
              {aiError}
            </div>
          )}
        </div>

        {/* Phase 1E-H Multi-Source Evidence Fusion Control */}
        <div style={{ marginTop: '20px', borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#1f2937', marginBottom: '8px' }}>
            Multi-Source Evidence Fusion Engine
          </h3>
          {!fusionResult ? (
            <div>
              <p style={{ fontSize: '0.875rem', color: '#4b5563', marginBottom: '12px' }}>
                Correlate report against OpenAQ, Open-Meteo weather, NASA FIRMS thermal signals, Sentinel-5P NO2 satellite scans, and OSM context.
              </p>
              <button
                type="button"
                className="action-btn-primary"
                onClick={() => handleFuseEvidence(submissionResult.evidence_id)}
                disabled={fusionLoading}
                style={{ backgroundColor: '#4f46e5' }}
              >
                {fusionLoading ? 'Fusing Multi-Source Signals...' : 'Run Evidence Fusion Engine'}
              </button>
            </div>
          ) : (
            <div className="ai-analysis-card" style={{ backgroundColor: '#f8fafc', padding: '14px', borderRadius: '8px', border: '1px solid #cbd5e1', marginTop: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <div>
                  <span style={{ fontWeight: 600, fontSize: '0.95rem', color: '#0f172a' }}>
                    Support Score: {fusionResult.support_score} / 100.0
                  </span>
                  <span style={{ fontSize: '0.8rem', color: '#64748b', marginLeft: '8px' }}>
                    (ID: {fusionResult.fusion_id})
                  </span>
                </div>
                <span className={`badge-success`} style={{
                  backgroundColor: fusionResult.confidence_tier === 'HIGH_SUPPORT' ? '#dcfce7' : fusionResult.confidence_tier === 'MODERATE_SUPPORT' ? '#fef9c3' : '#fee2e2',
                  color: fusionResult.confidence_tier === 'HIGH_SUPPORT' ? '#166534' : fusionResult.confidence_tier === 'MODERATE_SUPPORT' ? '#854d0e' : '#991b1b',
                  fontWeight: 600,
                  fontSize: '0.8rem'
                }}>
                  {fusionResult.confidence_tier}
                </span>
              </div>

              <p style={{ fontSize: '0.875rem', color: '#334155', margin: '8px 0', lineHeight: '1.4' }}>
                <strong>Explanation:</strong> {fusionResult.explanation}
              </p>

              {fusionResult.supporting_signals.length > 0 && (
                <div style={{ margin: '10px 0' }}>
                  <strong style={{ fontSize: '0.85rem', color: '#475569' }}>Supporting Signals ({fusionResult.supporting_signals.length}):</strong>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
                    {fusionResult.supporting_signals.map((s: MatchedRecordRef, idx: number) => (
                      <div key={idx} style={{ fontSize: '0.8rem', backgroundColor: '#f1f5f9', padding: '6px 10px', borderRadius: '4px', color: '#1e293b' }}>
                        <strong>{s.source_type} ({s.source_family})</strong> — {s.distance_km != null ? `${s.distance_km} km away` : 'co-located'}
                        {s.time_difference_minutes != null ? `, ${s.time_difference_minutes > 0 ? '+' : ''}${s.time_difference_minutes}m offset` : ''}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {fusionResult.unavailable_signals.length > 0 && (
                <div style={{ margin: '8px 0', fontSize: '0.8rem', color: '#64748b' }}>
                  <strong>Unavailable Signals:</strong> {fusionResult.unavailable_signals.join(', ')}
                </div>
              )}

              {fusionResult.conflicting_signals.length > 0 && (
                <div style={{ margin: '8px 0', fontSize: '0.8rem', color: '#b91c1c' }}>
                  <strong>Conflicting Signals:</strong> {fusionResult.conflicting_signals.map(c => c.source_family).join(', ')}
                </div>
              )}
            </div>
          )}

          {fusionError && (
            <div className="response-box" style={{ color: '#991b1b', backgroundColor: '#fef2f2', marginTop: '12px' }}>
              {fusionError}
            </div>
          )}
        </div>

        <p className="civic-privacy-note" style={{ marginTop: '16px' }}>
          Your report has been stored securely in the local civic repository. No personal identity was collected.
        </p>

        <button type="button" className="action-btn" onClick={handleResetForm} style={{ marginTop: '12px' }}>
          Submit Another Observation
        </button>
      </div>
    );
  }

  const hasModality = Boolean(photoFile || voiceBlob || description.trim());
  const canSubmit = consentGiven && hasModality && !isSubmitting;

  return (
    <div className="civic-card" role="region" aria-label="Citizen evidence submission form">
      <div className="header">
        <h1 className="title">VayuDrishti</h1>
        <p className="subtitle">Citizen Pollution Evidence Intake ? Community Air Quality Reporting</p>
      </div>

      <form onSubmit={handleSubmit} noValidate>
        {/* Error Notification */}
        {submitError && (
          <div className="alert-error" role="alert">
            <span className="alert-icon">?</span>
            <span>{submitError}</span>
          </div>
        )}

        {/* Section 1: Photo Evidence */}
        <fieldset className="civic-fieldset">
          <legend className="fieldset-legend">1. Photographic Evidence</legend>
          <p className="fieldset-hint">
            Upload or capture an image of the visible pollution plume, scrap fire, dust cloud, or smokestack (Max 10 MB).
          </p>

          {!photoPreview ? (
            <div className="upload-container">
              <label htmlFor="photo-input" className="file-upload-label">
                <span className="upload-btn-text">?? Take Photo or Select File</span>
                <span className="upload-subtext">Supports JPEG, PNG, WebP</span>
                <input
                  id="photo-input"
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
              <img src={photoPreview} alt="Captured pollution evidence preview" className="photo-thumbnail" />
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

        {/* Section 2: Voice Memo (Optional) */}
        <fieldset className="civic-fieldset">
          <legend className="fieldset-legend">2. Voice Memo (Optional)</legend>
          <p className="fieldset-hint">
            Record a short audio memo describing the odor, irritation, or activity (Max 60 seconds).
          </p>

          {voiceError && <div className="hint-warning">{voiceError}</div>}

          {!voiceUrl ? (
            <div className="voice-controls">
              {!isRecording ? (
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={startRecording}
                  disabled={isSubmitting}
                >
                  ??? Start Voice Recording
                </button>
              ) : (
                <div className="recording-active-box">
                  <span className="recording-pulse">? Recording ({recordingSeconds}s / 60s)</span>
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

        {/* Section 3: Observation Details */}
        <fieldset className="civic-fieldset">
          <legend className="fieldset-legend">3. Observation Details</legend>

          <div className="form-group">
            <label htmlFor="category-select" className="form-label">
              Suspected Emission Type
            </label>
            <select
              id="category-select"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="form-select"
            >
              <option value="biomass_burning">Biomass / Leaf / Garbage Burning</option>
              <option value="construction_dust">Construction & Road Dust Cloud</option>
              <option value="industrial_smoke">Industrial Smoke / Factory Flaring</option>
              <option value="vehicular_exhaust">Heavy Freight / Diesel Exhaust</option>
              <option value="other">Other Localized Source</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="description-input" className="form-label">
              Text Observation Remarks (Optional)
            </label>
            <textarea
              id="description-input"
              rows={3}
              maxLength={1000}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. Thick black smoke rising from open scrap burning near Mayapuri industrial corridor..."
              className="form-textarea"
            />
            <span className="char-count">{description.length} / 1000 characters</span>
          </div>
        </fieldset>

        {/* Section 4: Location */}
        <fieldset className="civic-fieldset">
          <legend className="fieldset-legend">4. Location Context</legend>
          <p className="fieldset-hint">
            Associating your GPS coordinates allows correlation with nearby air quality sensors and wind vectors.
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
                  {locationLoading ? 'Detecting Location...' : '?? Detect Current Location'}
                </button>
                <button
                  type="button"
                  className="btn-link"
                  onClick={() => setShowManualLocation(!showManualLocation)}
                >
                  {showManualLocation ? 'Hide Manual Options' : 'Use Known Area Instead'}
                </button>
              </div>
            ) : (
              <div className="location-confirmed-row">
                <span className="badge-success">
                  ?? {location.source === 'gps' ? 'GPS' : 'Manual'}: {location.latitude}?, {location.longitude}?
                  {location.accuracy_m ? ` (?${location.accuracy_m}m)` : ''}
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
                <p className="manual-title">Manual Pilot Corridor Presets:</p>
                <div className="preset-buttons">
                  <button
                    type="button"
                    className="preset-chip"
                    onClick={() => {
                      setManualLat('28.6320');
                      setManualLon('77.1180');
                      setLocation({ latitude: 28.632, longitude: 77.118, accuracy_m: null, source: 'manual' });
                    }}
                  >
                    Delhi Mayapuri (28.632°, 77.118°)
                  </button>
                  <button
                    type="button"
                    className="preset-chip"
                    onClick={() => {
                      setManualLat('28.6940');
                      setManualLon('77.1640');
                      setLocation({ latitude: 28.694, longitude: 77.164, accuracy_m: null, source: 'manual' });
                    }}
                  >
                    Delhi Wazirpur (28.694°, 77.164°)
                  </button>
                  <button
                    type="button"
                    className="preset-chip"
                    onClick={() => {
                      setManualLat('13.0280');
                      setManualLon('77.5190');
                      setLocation({ latitude: 13.028, longitude: 77.519, accuracy_m: null, source: 'manual' });
                    }}
                  >
                    Bengaluru Peenya (13.028°, 77.519°)
                  </button>
                </div>
                <div className="manual-custom-inputs" style={{ marginTop: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <input
                    type="text"
                    placeholder="Lat (e.g. 28.6320)"
                    value={manualLat}
                    onChange={(e) => setManualLat(e.target.value)}
                    className="form-input-sm"
                    style={{ width: '120px', padding: '6px', fontSize: '0.85rem' }}
                  />
                  <input
                    type="text"
                    placeholder="Lon (e.g. 77.1180)"
                    value={manualLon}
                    onChange={(e) => setManualLon(e.target.value)}
                    className="form-input-sm"
                    style={{ width: '120px', padding: '6px', fontSize: '0.85rem' }}
                  />
                  <button
                    type="button"
                    className="btn-secondary-sm"
                    onClick={handleApplyManualLocation}
                    style={{ padding: '6px 12px', fontSize: '0.85rem' }}
                  >
                    Set Custom Coords
                  </button>
                </div>
              </div>
            )}
          </div>
        </fieldset>

        {/* Section 5: Review & Explicit Consent */}
        <div className="consent-container">
          <label htmlFor="consent-checkbox" className="consent-label">
            <input
              id="consent-checkbox"
              type="checkbox"
              checked={consentGiven}
              onChange={(e) => setConsentGiven(e.target.checked)}
              className="consent-checkbox"
            />
            <span className="consent-text">
              <strong>Mandatory Consent:</strong> I voluntarily submit this environmental report. I understand that
              the photo, audio, description, and location provided will be used for community air quality and climate
              resilience analysis. No personal identity is collected.
            </span>
          </label>
        </div>

        {/* Submit Action */}
        <div className="submit-row">
          <button type="submit" className="action-btn-primary" disabled={!canSubmit}>
            {isSubmitting ? 'Submitting Evidence...' : 'Submit Evidence Report'}
          </button>
        </div>
      </form>

      {/* Manual Evidence AI Analysis & Evidence Fusion Lookup Control */}
      <div style={{ marginTop: '24px', borderTop: '1px solid #e5e7eb', paddingTop: '16px' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#374151', marginBottom: '8px' }}>
          Dev / Test Tool: Trigger AI Analysis or Evidence Fusion by Evidence ID
        </h3>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <input
            type="text"
            placeholder="ev_..."
            value={lookupEvidenceId}
            onChange={(e) => setLookupEvidenceId(e.target.value)}
            className="form-input-sm"
            style={{ width: '260px', padding: '6px 10px', fontSize: '0.85rem' }}
          />
          <button
            type="button"
            className="btn-secondary-sm"
            onClick={() => handleAnalyzeEvidence()}
            disabled={aiLoading || !lookupEvidenceId.trim()}
            style={{ padding: '6px 12px', fontSize: '0.85rem' }}
          >
            {aiLoading ? 'Analyzing...' : 'Analyze Evidence'}
          </button>
          <button
            type="button"
            className="btn-secondary-sm"
            onClick={() => handleFuseEvidence()}
            disabled={fusionLoading || !lookupEvidenceId.trim()}
            style={{ padding: '6px 12px', fontSize: '0.85rem', backgroundColor: '#eff6ff', color: '#1d4ed8' }}
          >
            {fusionLoading ? 'Fusing...' : 'Run Fusion Engine'}
          </button>
        </div>
      </div>
    </div>
  );
};
