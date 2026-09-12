# Development Setup Guide
## VayuDrishti — Phase 1B Foundation & Contracts

This document covers the local development setup for the VayuDrishti foundation skeleton.

---

## 1. Required Software

- **Python:** 3.10+ (tested on Python 3.12)
- **Node.js:** 18+ (tested on Node.js v24)
- **npm:** 9+ (tested on npm 10.8)
- **Git:** 2.30+

---

## 2. Repository & Working Directory

All commands must be run from inside the project root:

```bash
cd "F:\CLEAN AIR & CLIMATE RESILIENCE"
```

---

## 3. Backend Setup (FastAPI)

### 3.1 Virtual Environment
Create and activate the Python virtual environment inside the project root:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3.2 Install Backend Dependencies
```bash
pip install -r backend/requirements.txt
```

### 3.3 Run Contract Test Suite
```bash
pytest
```

### 3.4 Start the Backend Development Server
From the project root:
```bash
python -m uvicorn main:app --app-dir backend --port 8000 --reload
```
The backend API will be available at:
- **Interactive Swagger Docs:** `http://localhost:8000/docs`
- **Health Check Endpoint:** `http://localhost:8000/api/health`
- **Versioned API Status Endpoint:** `http://localhost:8000/api/v1/status`

Expected health response:
```json
{
  "status": "ok",
  "service": "VayuDrishti API",
  "phase": "1b"
}
```

Expected v1 status response:
```json
{
  "status": "ok",
  "version": "v1",
  "message": "VayuDrishti API v1 skeleton is operational."
}
```

---

## 4. Frontend Setup (React + TypeScript + Vite)

### 4.1 Install Frontend Dependencies
```bash
cd frontend
npm install
```

### 4.2 Start Frontend Development Server
```bash
npm run dev
```
The frontend will be available at:
- **Local URL:** `http://localhost:5173`

### 4.3 Build Frontend for Production
```bash
npm run build
```
Build output is generated in `frontend/dist/`.

---

## 5. Environment Variables

A template file `.env.example` is located in the project root. Copy it to `.env` if local overrides are needed:

```bash
copy .env.example .env
```

Default local endpoints:
- `VITE_API_BASE_URL=http://localhost:8000`
- `PORT=8000`
- `HOST=0.0.0.0`

---

## 6. Basic Troubleshooting

1. **PowerShell Script Execution Policy:**  
   If `.\.venv\Scripts\Activate.ps1` produces a script execution restriction error, run:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
   ```
   Or invoke Python directly via:
   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --port 8000 --reload
   ```

2. **Port 8000 or 5173 already in use:**  
   - For backend: specify another port via `--port <PORT>` and update `VITE_API_BASE_URL` in frontend.
   - For frontend: specify another port via `npm run dev -- --port <PORT>`.

3. **CORS Error in Browser Console:**  
   Ensure the backend is running with `CORS_ORIGINS` containing `http://localhost:5173` (configured by default in `backend/main.py`).
