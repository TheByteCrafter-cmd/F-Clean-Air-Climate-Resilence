"""
VayuDrishti - Clean Air and Climate Resilience
Phase 1B: Architecture Contract and API Skeleton
"""

import os
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.v1.router import api_v1_router
from backend.api.v1.schemas.common import HealthResponse, ErrorResponse, ErrorDetail

app = FastAPI(
    title="VayuDrishti API",
    description="Hyper-Local Climate Intelligence and Action Platform API",
    version="0.2.0",
)

# Configure CORS so local frontend can communicate with backend
allowed_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
)
allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Standardized Error Handling
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
            )
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request payload validation failed.",
                details=exc.errors(),
            )
        ).model_dump(),
    )


# Backward-compatible Phase 1A health endpoint
@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health_check():
    """
    Basic health check endpoint to confirm backend availability.
    Preserved for Phase 1A backward compatibility.
    """
    return HealthResponse(
        status="ok",
        service="VayuDrishti API",
        phase="1b",
        timestamp=datetime.now(timezone.utc),
    )


# Register Version 1 API router
app.include_router(api_v1_router)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("backend.main:app", host=host, port=port, reload=True)
