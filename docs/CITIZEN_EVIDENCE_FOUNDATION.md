# VayuDrishti — Phase 1E-F Citizen Evidence Ingestion Foundation

## Executive Summary
Phase 1E-F implements the **Citizen Evidence Intake Foundation** for VayuDrishti (*Clean Air & Climate Resilience*). It provides a secure, privacy-preserving, multi-modal intake pipeline allowing citizens to submit ground-level environmental observations.

Citizens can upload photos (camera/gallery), record optional voice memos (browser MediaRecorder up to 60s), provide text remarks ($\le 1000$ characters), and attach location context (HTML5 GPS or manual pilot corridor coordinates). Every submission undergoes strict security, MIME type, file size, and location validation before generating a canonical evidence ID (`ev_<uuid>`), persisting raw media in local storage, and saving a structured JSON manifest.

---

## Technical Architecture

```
                                    +------------------------------------------+
                                    | Citizen Intake UI (React + TypeScript)   |
                                    | - Camera/Photo Upload                    |
                                    | - Voice Recorder (WebM/OGG/WAV <= 60s)  |
                                    | - Text Remark (<= 1000 chars)            |
                                    | - GPS / Manual Location Presets          |
                                    | - Mandatory Voluntary Consent Checkbox   |
                                    +--------------------+---------------------+
                                                         |
                                             multipart/form-data POST
                                                         |
                                                         v
                                    +--------------------+---------------------+
                                    | POST /api/v1/evidence (FastAPI)          |
                                    +--------------------+---------------------+
                                                         |
                                                         v
                                    +--------------------+---------------------+
                                    | Ingestion Validation Layer               |
                                    | - Mandatory Consent Verification         |
                                    | - Modality Presence Check (Photo/Voice/  |
                                    |   Text)                                  |
                                    | - MIME & File Size (10MB limit)         |
                                    | - Filename Sanitization & Anti-Path     |
                                    |   Traversal                              |
                                    | - WGS84 Geolocation & Accuracy Guard     |
                                    +--------------------+---------------------+
                                                         |
                                                         v
                                    +--------------------+---------------------+
                                    | Evidence Storage Engine                  |
                                    | - Generates canonical ID: ev_<uuid>      |
                                    | - Raw Media:                             |
                                    |   data/raw/citizen_evidence/<id>/        |
                                    | - Manifest JSON:                         |
                                    |   data/processed/citizen_evidence/       |
                                    |   manifests/<id>.json                    |
                                    +------------------------------------------+
```

---

## Modalities & Validation Rules

| Modality / Component | Format / MIME Whitelist | Constraints & Limits |
| :--- | :--- | :--- |
| **Photo Upload** | `image/jpeg`, `image/png`, `image/webp` | Max file size: **10 MB**. Filename sanitized to `photo_01.<ext>`. |
| **Voice Memo** | `audio/webm`, `audio/ogg`, `audio/wav`, `audio/mp4`, `audio/mpeg`, `audio/x-m4a` | Max duration: **60 seconds**. Max file size: **10 MB**. Filename sanitized to `voice_01.<ext>`. |
| **Text Remarks** | Plain text | Length limit: **1000 characters**. Stripped of dangerous HTML/scripts. |
| **Location Context** | Latitude & Longitude in WGS84 (`EPSG:4326`) | Latitude: $-90.0$ to $+90.0$, Longitude: $-180.0$ to $+180.0$. `accuracy_m` must be non-negative if provided. |
| **Explicit Consent** | Boolean flag | **Mandatory**. Rejection HTTP 400 if `False` or omitted. |

---

## API Endpoints

### 1. `POST /api/v1/evidence`
**Description:** Accepts multi-modal citizen evidence submissions as `multipart/form-data`.

- **Headers:** `Content-Type: multipart/form-data`
- **Form Fields:**
  - `consent` (`bool`, required): Must be `true`.
  - `photo` (`file`, optional): Image file.
  - `voice` (`file`, optional): Audio file.
  - `description` (`str`, optional): Text remark ($\le 1000$ chars).
  - `category` (`str`, default `"industrial_smoke"`): Emission category (`biomass_burning`, `construction_dust`, `industrial_smoke`, `vehicular_exhaust`, `other`).
  - `latitude` (`float`, optional): WGS84 latitude.
  - `longitude` (`float`, optional): WGS84 longitude.
  - `accuracy_m` (`float`, optional): GPS accuracy in meters.
  - `location_source` (`str`, default `"gps"`): `"gps"` or `"manual"`.

- **Success Response (HTTP 201 Created):**
```json
{
  "success": true,
  "data": {
    "evidence_id": "ev_a1b2c3d4e5f67890a1b2c3d4e5f67890",
    "received_at": "2026-09-16T00:00:00Z",
    "media_count": 2,
    "manifest_path": "data/processed/citizen_evidence/manifests/ev_a1b2c3d4e5f67890a1b2c3d4e5f67890.json",
    "status": "received"
  },
  "error": null,
  "timestamp": "2026-09-16T00:00:00Z"
}
```

- **Error Responses:**
  - `400 Bad Request`: Missing consent, empty submission, invalid coordinates, file size limit exceeded, unsupported media format, or path traversal attempt.

---

### 2. `GET /api/v1/evidence/{evidence_id}`
**Description:** Retrieves stored manifest metadata for a submitted evidence report.

- **Success Response (HTTP 200 OK):** Returns the canonical `EvidenceManifest` envelope.
- **Error Responses:**
  - `400 Bad Request`: Malformed evidence ID (must start with `ev_` followed by 32 hex chars).
  - `404 Not Found`: Evidence ID manifest does not exist.

---

## File System Storage Structure

```
F:\CLEAN AIR & CLIMATE RESILIENCE\
├── data/
│   ├── raw/
│   │   └── citizen_evidence/
│   │       └── ev_<uuid>/
│   │           ├── photo_01.jpg
│   │           └── voice_01.webm
│   └── processed/
│       └── citizen_evidence/
│           └── manifests/
│               └── ev_<uuid>.json
```

---

## Security & Privacy Protocol

1. **Explicit Informed Consent:** Citizens must explicitly check a consent box confirming voluntary submission.
2. **No PII Collection:** No IP addresses, device serial numbers, or user identity metadata are recorded in the manifest.
3. **Filename Sanitization:** Input filenames are completely replaced with deterministic internal basenames (`photo_01.<ext>`, `voice_01.<ext>`) to eliminate path traversal attacks (`../`, `\`, leading dots).
4. **Local File Isolation:** Media and manifests are strictly confined within the locked local root under `data/raw/` and `data/processed/`.

---

## Explicit AI Deferral Notice

> [!IMPORTANT]
> **AI / Vision / Voice Analysis Deferral:**
> In compliance with project guidelines, Phase 1E-F focuses exclusively on **intake, validation, storage, and confirmation**. No Gemini API call, vision classification, smoke detection, audio transcription, or automated risk scoring is performed during intake. Downstream AI processing will consume stored manifests and raw media files in future phases.
