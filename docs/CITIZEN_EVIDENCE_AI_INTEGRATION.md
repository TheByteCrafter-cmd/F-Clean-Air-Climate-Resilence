# VayuDrishti — Citizen Evidence & AI Insight Integration Specification

**Phase**: 1E-J2E.4.8  
**Component**: `frontend/src/components/CitizenEvidencePanel.tsx`  
**Endpoints Integrated**: `POST /api/v1/evidence`, `GET /api/v1/evidence/{id}`, `POST /api/v1/evidence/{id}/analyze`, `GET /api/v1/evidence/{id}/analysis`  
**Status**: OPERATIONAL  

---

## 1. Executive Summary & Evidence Pipeline Architecture

The Citizen Evidence & AI Insight Integration provides a trusted civic environmental evidence reporting and AI analysis interface. It allows community members to report localized environmental observations and view validated, server-side Gemini multimodal AI analysis results and multi-source fusion corroboration.

```
       ┌─────────────────────────────────────────────────────────────┐
       │             CitizenEvidencePanel.tsx (React UI)             │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
                         apiClient.submitEvidence()
                                      │
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │     POST /api/v1/evidence  (CitizenEvidenceStorage)        │
       └──────────────────────────────┬──────────────────────────────┘
                                      │
                         apiClient.analyzeEvidence()
                                      │
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │  POST /api/v1/evidence/{id}/analyze (GeminiEvidenceAnalyzer)│
       └──────────────────────────────┬──────────────────────────────┘
                                      │
                         apiClient.fuseEvidence()
                                      │
                                      ▼
       ┌─────────────────────────────────────────────────────────────┐
       │  POST /api/v1/fusion/evidence/{id} (EvidenceFusionEngine)   │
       └─────────────────────────────────────────────────────────────┘
```

---

## 2. Integrated Public Contracts & Modalities

1. **Submission Endpoint (`POST /api/v1/evidence`)**:
   - **Form Fields**: `photo` (UploadFile, JPEG/PNG/WebP), `voice` (UploadFile, WebM/WAV/OGG), `description` (Form text), `category` (Form tag), `latitude` & `longitude` (WGS84 float), `accuracy` (float meters), `location_source` ("gps" | "manual"), `consent` (boolean).
   - **Response**: `EvidenceSubmissionResponse` (`evidence_id`, `status: "received"`, `submitted_at`, `media_count`, `media_types`).

2. **Server-Side AI Analysis (`POST /api/v1/evidence/{id}/analyze`)**:
   - **Response**: `EvidenceAIAnalysis` (`analysis_id`, `evidence_id`, `model_name`, `relevance`, `observed_phenomena`, `probable_categories`, `visual_indicators`, `evidence_quality`, `audio_status`, `explanation`, `uncertainty`).

3. **Multi-Source Fusion (`POST /api/v1/fusion/evidence/{id}`)**:
   - **Response**: `EvidenceFusionResult` (`fusion_id`, `support_score`, `confidence_tier`, `supporting_signals`, `explanation`).

---

## 3. Mandatory Privacy & Consent Standard

- **Explicit Consent**: Mandatory checkbox (`consent=true`) enforced before form submission.
- **Privacy Notice**: Informs citizens that evidence is registered for civic air quality monitoring without collecting personal identity.
- **Client Security**: Zero API keys or internal file paths exposed to browser runtime.

---

## 4. Humanized AI Language & Non-Causal Safeguards

- **Observational Terminology**: AI findings are presented strictly using grounded observation phrasing:
  - `"AI-assisted observation"`
  - `"Reported environmental condition"`
  - `"AI analysis suggests the following observable features"`
  - `"Evidence requires review"`
- **Prohibited Phrasing**: Avoids unsupported claims such as `"AI confirmed pollution source"` or `"AI proved factory caused pollution"`.

---

## 5. Processing States & Error Handling

- **Processing State Lifecycle**: `IDLE` -> `SELECTED` -> `SUBMITTING` -> `PROCESSING` -> `COMPLETE` / `FAILED`.
- **Data Quality Handling**:
  - `READY`: Full evidence intake, AI analysis display, and fusion trace.
  - `PARTIAL`: Displays registered report with notice detailing unverified factors.
  - `BLOCKED`: Displays notice that operational decision evaluation is currently blocked.

---

## 6. Verification & Build Standard

- **Frontend Build**: `npm --prefix frontend run build` (Exit Code 0).
- **Backend Regression**: `.venv\Scripts\pytest.exe -v` (374 passed, 1 skipped).
- **Model Hashes**: Verified LightGBM model hashes intact.
