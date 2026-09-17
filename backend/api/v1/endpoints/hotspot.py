import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from backend.api.v1.schemas.common import ErrorDetail, ErrorResponse
from backend.api.v1.schemas.hotspot import (
    HotspotCollectionResponse,
    HotspotDetectionRequest,
    HotspotDetectionResult,
    HotspotSummary,
)
from backend.ingestion.citizen_evidence_storage import validate_safe_id
from backend.ingestion.exceptions import (
    HotspotDetectionError,
    HotspotPersistenceError,
    InsufficientSpatialDataError,
)
from backend.ingestion.hotspot_detector import (
    HotspotDetectorConfiguration,
    HyperLocalHotspotDetector,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hotspots", tags=["hotspots"])
detector = HyperLocalHotspotDetector()


@router.post(
    "/detect",
    response_model=List[HotspotDetectionResult],
    status_code=status.HTTP_200_OK,
    summary="Trigger hyper-local hotspot detection",
    description="""
    Executes IDW spatial interpolation and contiguous grid cell aggregation over local
    observations and corroborating evidence to detect potential hyper-local pollution hotspots.
    """,
)
def detect_hotspots(payload: Optional[HotspotDetectionRequest] = None):
    try:
        pollutant = payload.pollutant if payload else None
        target_timestamp = payload.analysis_timestamp if payload else None
        time_window = payload.time_window_minutes if payload else None

        if time_window:
            detector.config.time_window_minutes = time_window
        if payload and payload.roi_bbox and len(payload.roi_bbox) == 4:
            detector.config.roi_bbox = payload.roi_bbox

        results = detector.detect_hotspots(
            pollutant=pollutant,
            analysis_timestamp=target_timestamp,
        )
        return results
    except InsufficientSpatialDataError as e:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INSUFFICIENT_SPATIAL_DATA",
                    message=str(e),
                )
            ).model_dump(),
        )
    except HotspotDetectionError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="HOTSPOT_DETECTION_ERROR",
                    message=str(e),
                )
            ).model_dump(),
        )
    except HotspotPersistenceError as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="PERSISTENCE_ERROR",
                    message=str(e),
                )
            ).model_dump(),
        )
    except Exception as e:
        logger.error(f"Unexpected error during hotspot detection: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_HOTSPOT_ERROR",
                    message=f"Hotspot detection failed: {str(e)}",
                )
            ).model_dump(),
        )


@router.get(
    "",
    response_model=HotspotCollectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve detected hotspots collection",
    description="Fetches a collection of summaries for all currently persisted hyper-local hotspots.",
)
def list_hotspots(pollutant: Optional[str] = "PM2.5"):
    summaries = detector.list_hotspot_summaries()
    if pollutant:
        summaries = [s for s in summaries if s.pollutant.upper() == pollutant.upper()]

    return HotspotCollectionResponse(
        total_count=len(summaries),
        pollutant=pollutant or "ALL",
        analysis_timestamp=summaries[0].detected_at if summaries else None,
        hotspots=summaries,
    )


@router.get(
    "/{hotspot_id}",
    response_model=HotspotDetectionResult,
    summary="Retrieve hyper-local hotspot detail",
    description="Fetches full machine-readable HotspotDetectionResult artifact by hotspot ID.",
)
def get_hotspot_detail(hotspot_id: str):
    if not validate_safe_id(hotspot_id):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_HOTSPOT_ID",
                    message=f"Malformatted or unsafe hotspot ID: '{hotspot_id}'",
                )
            ).model_dump(),
        )

    result = detector.get_hotspot_result(hotspot_id)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="HOTSPOT_NOT_FOUND",
                    message=f"Hotspot detection artifact '{hotspot_id}' not found.",
                )
            ).model_dump(),
        )

    return result
