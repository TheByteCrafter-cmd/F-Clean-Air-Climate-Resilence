import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from backend.api.v1.schemas.common import ErrorDetail, ErrorResponse
from backend.api.v1.schemas.fusion import EvidenceFusionResult
from backend.ingestion.citizen_evidence_storage import validate_safe_id
from backend.ingestion.evidence_fusion_engine import EvidenceFusionEngine
from backend.ingestion.exceptions import (
    AnchorMetadataNotFoundError,
    EvidenceFusionError,
    FusionPersistenceError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fusion", tags=["fusion"])
engine = EvidenceFusionEngine()


@router.post(
    "/evidence/{evidence_id}",
    response_model=EvidenceFusionResult,
    status_code=status.HTTP_200_OK,
    summary="Trigger multi-source evidence fusion",
    description="""
    Correlates an ingested citizen evidence event anchor against available air quality,
    meteorological, thermal anomaly, satellite, and geospatial data sources.
    """,
)
def fuse_citizen_evidence(evidence_id: str):
    if not validate_safe_id(evidence_id):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INVALID_EVIDENCE_ID",
                    message=f"Malformatted or unsafe evidence ID: '{evidence_id}'",
                )
            ).model_dump(),
        )

    try:
        result = engine.fuse_evidence(evidence_id=evidence_id)
        return result
    except AnchorMetadataNotFoundError as e:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="ANCHOR_NOT_FOUND",
                    message=str(e),
                )
            ).model_dump(),
        )
    except EvidenceFusionError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="FUSION_ERROR",
                    message=str(e),
                )
            ).model_dump(),
        )
    except FusionPersistenceError as e:
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
        logger.error(f"Unexpected error during fusion for evidence '{evidence_id}': {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_FUSION_ERROR",
                    message=f"Evidence fusion failed: {str(e)}",
                )
            ).model_dump(),
        )


@router.get(
    "/{fusion_id}",
    response_model=EvidenceFusionResult,
    summary="Retrieve multi-source evidence fusion result",
    description="Fetches a previously calculated multi-source evidence fusion result artifact by fusion ID.",
)
def get_fusion_result(fusion_id: str):
    # If fusion_id starts with ev_, check if user requested lookup by evidence_id
    if fusion_id.startswith("ev_"):
        result = engine.get_fusion_result_by_evidence_id(fusion_id)
    else:
        result = engine.get_fusion_result(fusion_id)

    if not result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="FUSION_RESULT_NOT_FOUND",
                    message=f"Evidence fusion result artifact '{fusion_id}' not found.",
                )
            ).model_dump(),
        )

    return result
