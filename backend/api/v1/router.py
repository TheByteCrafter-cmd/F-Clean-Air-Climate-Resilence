from fastapi import APIRouter
from backend.api.v1.schemas.common import ApiStatusResponse
from backend.api.v1.endpoints.evidence import router as evidence_router
from backend.api.v1.endpoints.fusion import router as fusion_router
from backend.api.v1.endpoints.hotspot import router as hotspot_router
from backend.api.v1.endpoints.forecast import router as forecast_router
from backend.api.v1.endpoints.risk import router as risk_router

api_v1_router = APIRouter(prefix="/api/v1", tags=["v1"])


@api_v1_router.get("/status", response_model=ApiStatusResponse)
def get_api_v1_status():
    """
    Confirms operational status of VayuDrishti API v1 skeleton.
    """
    return ApiStatusResponse(
        status="ok",
        version="v1",
        message="VayuDrishti API v1 skeleton is operational."
    )


# Register Citizen Evidence, Evidence Fusion, Hotspot Detection, Forecasting, and Risk Sub-Routers
api_v1_router.include_router(evidence_router)
api_v1_router.include_router(fusion_router)
api_v1_router.include_router(hotspot_router)
api_v1_router.include_router(forecast_router)
api_v1_router.include_router(risk_router)
