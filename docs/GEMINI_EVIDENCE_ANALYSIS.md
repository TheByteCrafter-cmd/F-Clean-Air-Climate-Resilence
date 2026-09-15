# VayuDrishti — Phase 1E-G Gemini Multimodal Citizen Evidence Analysis

## 1. Executive Summary & Purpose
Phase 1E-G implements the **Gemini Multimodal Analysis Engine** for citizen-submitted environmental evidence in VayuDrishti (*Clean Air & Climate Resilience*). 

Building upon the raw multi-modal evidence intake established in Phase 1E-F, this layer consumes stored citizen photo evidence, text remarks, and contextual metadata, sending them to Google's official `google-genai` SDK. Gemini extracts structured, evidence-grounded insights—classifying emission phenomena, reporting observable visual indicators, assigning qualitative confidence levels, documenting uncertainty, and returning Pydantic-validated JSON artifacts.

---

## 2. Technical Architecture & Data Flow

```
+-------------------------------------------------------------------------+
| Stored Citizen Evidence Report (Phase 1E-F)                             |
| - Photo File: data/raw/citizen_evidence/<evidence_id>/photo_01.jpg      |
| - Text Remarks & Category Selection                                     |
| - Manifest: data/processed/citizen_evidence/manifests/<evidence_id>.json|
+------------------------------------+------------------------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
| POST /api/v1/evidence/{evidence_id}/analyze                             |
| (Backend Execution — Never in Frontend / Client)                        |
+------------------------------------+------------------------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
| GeminiEvidenceAnalyzer Engine                                           |
| - Validates GEMINI_API_KEY & GEMINI_MODEL                               |
| - Idempotency Check (returns cached artifact if already analyzed)       |
| - Construct System & Context Prompt with Security Guardrails            |
| - Instantiates google.genai.Client                                      |
+------------------------------------+------------------------------------+
                                     |
                          Structured Output Request
                                     |
                                     v
+------------------------------------+------------------------------------+
| Google Gemini API (gemini-2.5-flash / configured Flash model)           |
| - Structured JSON Generation (response_schema=EvidenceAIAnalysis)       |
+------------------------------------+------------------------------------+
                                     |
                           Structured JSON Output
                                     |
                                     v
+------------------------------------+------------------------------------+
| Pydantic Schema Validation & Local Persistence                          |
| - Validates EvidenceAIAnalysis model                                    |
| - Persists artifact: data/processed/citizen_evidence/analysis/<id>.json|
| - Updates Manifest status: AI_ANALYZED                                  |
+-------------------------------------------------------------------------+
```

---

## 3. Official Google GenAI SDK & Model Configuration

- **SDK Package:** `google-genai>=2.0.0` (`google.genai.Client`)
- **Environment Configuration:**
  - `GEMINI_API_KEY`: Secrets management via environment configuration ONLY. Never exposed in frontend, git, HTTP payloads, or log files.
  - `GEMINI_MODEL`: Configurable via environment, defaulting to `"gemini-2.5-flash"`.

---

## 4. Prompt Engineering & Prompt Injection Security

The server-side system prompt enforces strict evidence-grounding:
1. **Grounding:** Analysis must be strictly based on observable visual and text evidence.
2. **Causation Guardrail:** Refrains from making legal or unsupported causal claims (e.g. states "visible dark plume near industrial facility", NOT "this factory is violating pollution standards").
3. **Qualitative Confidence:** Probable categories are assigned qualitative confidence levels (`"high"`, `"medium"`, `"low"`). Arbitrary numeric probabilities (e.g. 94.7%) are strictly forbidden.
4. **Uncertainty:** Explicitly documents obscuration, low resolution, dark lighting, or ambiguity.
5. **Prompt Injection Guard:** User text remarks are treated strictly as **DATA**, never as instructions. Commands embedded in remarks (e.g. "ignore previous instructions") are safely neutralized.

---

## 5. Input Modalities & Audio Handling Strategy

| Modality | Processing Method | Status / Handling |
| :--- | :--- | :--- |
| **Photo Evidence** | PIL Image stream sent directly to Gemini multimodal endpoint | Primary visual analysis |
| **Text Remarks** | Formatted into server-side evidence context prompt | Analyzed as contextual data |
| **Audio Voice Memos** | Kept intact; tagged as `audio_status = "AUDIO_ANALYSIS_DEFERRED"` | Deferred cleanly without fake transcription |

---

## 6. Structured Output Schema (`EvidenceAIAnalysis`)

```typescript
interface ProbableCategoryItem {
  category: string;                       // e.g. "industrial_smoke", "biomass_burning"
  confidence_level: 'high' | 'medium' | 'low'; // Qualitative confidence
}

interface EvidenceAIAnalysis {
  analysis_id: string;                    // Canonical ID: an_<uuid_hex>
  evidence_id: string;                    // Associated ID: ev_<uuid_hex>
  model_name: string;                     // e.g. "gemini-2.5-flash"
  model_version: string;                  // e.g. "2026-09"
  analyzed_at: string;                    // ISO 8601 UTC
  relevance: 'relevant' | 'partially_relevant' | 'irrelevant' | 'insufficient_evidence';
  observed_phenomena: string[];           // e.g. ["visible_dark_smoke_plume"]
  probable_categories: ProbableCategoryItem[];
  visual_indicators: string[];            // e.g. ["dark plume", "dense cloud"]
  evidence_quality: string;               // e.g. "clear", "partially_obscured"
  audio_status: string;                   // "AUDIO_ANALYSIS_DEFERRED"
  uncertainty: string[];                  // Explicit obscuration/ambiguity notes
  explanation: string;                    // Evidence-grounded summary
  recommended_followup: string[];         // e.g. ["Obtain wider angle photo"]
  safety_note?: string | null;
  schema_version: string;                 // "1.0"
}
```

---

## 7. Storage Model & Idempotency Strategy

- **Persisted AI Artifact Path:** `data/processed/citizen_evidence/analysis/<evidence_id>.json`
- **Idempotency Rule:** Re-submitting an analysis request for an already analyzed `evidence_id` returns the existing cached `EvidenceAIAnalysis` artifact unless `force_reanalyze=true` is explicitly specified.
- **Manifest Lifecycle Update:** Evidence manifest status transitions from `RECEIVED` / `VALIDATED` -> `AI_ANALYZED` (or `AI_ANALYSIS_FAILED` upon unrecoverable error).

---

## 8. API Endpoints

### `POST /api/v1/evidence/{evidence_id}/analyze`
- **Query Params:** `force_reanalyze` (boolean, default: `false`)
- **Response (200 OK):** Returns structured `EvidenceAIAnalysis` payload.
- **Error Codes:**
  - `400 BAD_REQUEST`: Invalid evidence ID format or evidence status is REJECTED.
  - `404 NOT_FOUND`: Evidence ID manifest does not exist.
  - `429 TOO_MANY_REQUESTS`: Gemini API rate limit reached.
  - `502 BAD_GATEWAY`: Gemini authentication failure or output validation error.
  - `503 SERVICE_UNAVAILABLE`: Unconfigured `GEMINI_API_KEY`.
  - `504 GATEWAY_TIMEOUT`: Gemini API request timed out.

### `GET /api/v1/evidence/{evidence_id}/analysis`
- **Response (200 OK):** Returns existing persisted `EvidenceAIAnalysis` artifact.
- **Error Codes:** `404 NOT_FOUND` if analysis artifact has not been generated yet.

---

## 9. Explicit No-Fusion & Scope Notice

> [!IMPORTANT]
> **No Multi-Source Fusion Notice:**
> Phase 1E-G performs **isolated evidence interpretation ONLY**. It does NOT send OpenAQ readings, Open-Meteo weather data, NASA FIRMS hotspots, Sentinel-5P signals, or OSM geographic context to Gemini. Multi-source evidence fusion will be implemented in subsequent phases.
