"""
VayuDrishti - Clean Air & Climate Resilience
Phase 1A: Backend Foundation
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="VayuDrishti API",
    description="Hyper-Local Climate Intelligence & Action Platform API",
    version="0.1.0",
)

# Configure CORS so local frontend can communicate with backend
allowed_origins_env = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000")
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    """
    Basic health check endpoint to confirm backend availability.
    """
    return {
        "status": "ok",
        "service": "VayuDrishti API",
        "phase": "1a"
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
