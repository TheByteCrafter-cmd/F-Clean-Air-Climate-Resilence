import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from backend.api.v1.schemas.common import ErrorDetail, ErrorResponse
from backend.api.v1.schemas.evidence import (
    EvidenceLocation,
    EvidenceManifest,
    EvidenceSubmissionResponse,
    MediaItem,
)
from backend.ingestion.citizen_evidence_storage import (
    CitizenEvidenceStorage,
    generate_evidence_id,
    validate_safe_id,
)
from backend.ingestion.citizen_evidence_validator import CitizenEvidenceValidator
from backend.ingestion.exceptions import (
    ConsentRequiredError,
    EmptyEvidenceError,
    FileSizeLimitExceededError,
    LocationValidationError,
    UnsupportedMediaFormatError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evidence", tags=["evidence"])
storage = CitizenEvidenceStorage()


@router.post(
    "",
    response_model=EvidenceSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit citizen pollution evidence report",
    description="""
    Intakes citizen environmental observations including photo, optional voice memo,
    optional text remark, and geolocation coordinates.
    """,
)
async def submit_citizen_evidence(
    photo: Optional[UploadFile] = File(None, description="Citizen photo upload (JPEG, PNG, WebP)"),
    voice: Optional[UploadFile] = File(None, description="Optional audio memo (WebM, WAV, OGG, MP4)"),
    description: Optional[str] = Form(None, description="Optional text observation remarks"),
    category: Optional[str] = Form(None, description="Suspected pollution category"),
    latitude: Optional[float] = Form(None, description="WGS84 latitude coordinate"),
    longitude: Optional[float] = Form(None, description="WGS84 longitude coordinate"),
    accuracy: Optional[float] = Form(None, description="Location horizontal accuracy in meters"),
    location_source: Optional[str] = Form("gps", description="Location source: 'gps' or 'manual'"),
    consent: bool = Form(False, description="Mandatory explicit citizen consent"),
):
    # Step 1: Consent Verification
    if not consent:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="CONSENT_REQUIRED",
                    message="Explicit citizen consent is mandatory before evidence submission.",
                )
            ).model_dump(),
        )

    # Step 2: Modality Presence Verification
    has_photo = photo is not None and bool(photo.filename)
    has_voice = voice is not None and bool(voice.filename)
    has_text = bool(description and description.strip())

    if not (has_photo or has_voice or has_text):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="EMPTY_EVIDENCE",
                    message="Submission must include at least one evidence item (photo, voice memo, or text description).",
                )
            ).model_dump(),
        )

    # Step 3: Location Validation
    if latitude is not None or longitude is not None:
        if latitude is None or longitude is None:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code="INVALID_COORDINATES",
                        message="Both latitude and longitude must be provided together.",
                    )
                ).model_dump(),
            )
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code="INVALID_COORDINATES",
                        message=f"Coordinates out of physical WGS84 range: lat={latitude}, lon={longitude}",
                    )
                ).model_dump(),
            )
        if accuracy is not None and accuracy < 0.0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code="INVALID_ACCURACY",
                        message="Location accuracy radius cannot be negative.",
                    )
                ).model_dump(),
            )

    # Step 4: Text Description Validation
    try:
        CitizenEvidenceValidator.validate_description(description)
    except EmptyEvidenceError as desc_err:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="DESCRIPTION_TOO_LONG",
                    message=str(desc_err),
                )
            ).model_dump(),
        )

    # Step 5: Read & Validate Media
    media_items: List[MediaItem] = []
    evidence_id = generate_evidence_id()
    now_utc = datetime.now(timezone.utc)

    # Handle Photo
    if has_photo:
        photo_bytes = await photo.read()
        try:
            CitizenEvidenceValidator.validate_photo(
                content_type=photo.content_type,
                file_size=len(photo_bytes),
                filename=photo.filename,
            )
            saved_photo = storage.save_media_file(
                evidence_id=evidence_id,
                media_type="photo",
                content=photo_bytes,
                mime_type=photo.content_type,
                client_filename=photo.filename,
                sequence_index=1,
            )
            media_items.append(saved_photo)
        except (UnsupportedMediaFormatError, FileSizeLimitExceededError) as err:
            err_code = "FILE_TOO_LARGE" if isinstance(err, FileSizeLimitExceededError) else "UNSUPPORTED_MEDIA_TYPE"
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code=err_code,
                        message=str(err),
                    )
                ).model_dump(),
            )

    # Handle Voice
    if has_voice:
        voice_bytes = await voice.read()
        try:
            CitizenEvidenceValidator.validate_voice(
                content_type=voice.content_type,
                file_size=len(voice_bytes),
                filename=voice.filename,
            )
            saved_voice = storage.save_media_file(
                evidence_id=evidence_id,
                media_type="voice",
                content=voice_bytes,
                mime_type=voice.content_type,
                client_filename=voice.filename,
                sequence_index=1,
            )
            media_items.append(saved_voice)
        except (UnsupportedMediaFormatError, FileSizeLimitExceededError) as err:
            err_code = "FILE_TOO_LARGE" if isinstance(err, FileSizeLimitExceededError) else "UNSUPPORTED_MEDIA_TYPE"
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=ErrorResponse(
                    error=ErrorDetail(
                        code=err_code,
                        message=str(err),
                    )
                ).model_dump(),
            )

    # Step 6: Construct and Save Evidence Manifest
    loc_obj = None
    if latitude is not None and longitude is not None:
        loc_obj = EvidenceLocation(
            latitude=latitude,
            longitude=longitude,
            accuracy_m=accuracy,
            source="manual" if location_source == "manual" else "gps",
            timestamp=now_utc,
        )

    manifest = EvidenceManifest(
        evidence_id=evidence_id,
        submitted_at=now_utc,
        location=loc_obj,
        media=media_items,
        description=description.strip() if description else None,
        category=category.strip() if category else None,
        consent_given=True,
        status="RECEIVED",
        source="citizen_web",
        schema_version="1.0",
    )

    storage.save_manifest(manifest)

    # Step 7: Build Structured Response
    return EvidenceSubmissionResponse(
        evidence_id=evidence_id,
        status="received",
        submitted_at=now_utc,
        location=loc_obj,
        media_count=len(media_items),
        media_types=[m.media_type for m in media_items],
        message="Citizen evidence submitted and registered successfully.",
    )


@router.get(
    "/{evidence_id}",
    response_model=EvidenceManifest,
    summary="Retrieve citizen evidence manifest",
    description="Fetches the machine-readable manifest for a previously submitted evidence report.",
)
def get_citizen_evidence_manifest(evidence_id: str):
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

    manifest = storage.get_manifest(evidence_id)
    if not manifest:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="EVIDENCE_NOT_FOUND",
                    message=f"Evidence report '{evidence_id}' not found.",
                )
            ).model_dump(),
        )

    return manifest
