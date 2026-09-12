from fastapi import APIRouter
from backend.api.v1.schemas.common import ApiStatusResponse

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
