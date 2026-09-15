import logging
from pathlib import Path
from typing import Optional, Set

from backend.ingestion.exceptions import (
    ConsentRequiredError,
    EmptyEvidenceError,
    FileSizeLimitExceededError,
    LocationValidationError,
    UnsupportedMediaFormatError,
)

logger = logging.getLogger(__name__)

# Security and format constraints
MAX_PHOTO_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
MAX_VOICE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB
MAX_DESCRIPTION_LENGTH: int = 1000

ALLOWED_PHOTO_MIME_TYPES: Set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

ALLOWED_PHOTO_EXTENSIONS: Set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

ALLOWED_VOICE_MIME_TYPES: Set[str] = {
    "audio/webm",
    "audio/wav",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/x-m4a",
    "audio/aac",
}

ALLOWED_VOICE_EXTENSIONS: Set[str] = {
    ".webm",
    ".wav",
    ".ogg",
    ".mp4",
    ".m4a",
    ".mp3",
    ".aac",
}

DANGEROUS_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".sh", ".py", ".js", ".php",
    ".vbs", ".msi", ".dll", ".com", ".scr", ".pif", ".jar",
}


class CitizenEvidenceValidator:
    """Validates citizen evidence submissions for consent, physical boundaries, and security constraints."""

    @staticmethod
    def validate_consent(consent: bool) -> None:
        """Enforces mandatory explicit citizen consent."""
        if not consent:
            raise ConsentRequiredError("Explicit citizen consent is mandatory before evidence submission.")

    @staticmethod
    def validate_modality_presence(has_photo: bool, has_voice: bool, has_text: bool) -> None:
        """Ensures that at least one evidence modality exists."""
        if not (has_photo or has_voice or has_text):
            raise EmptyEvidenceError(
                "Submission must include at least one evidence item (photo, voice memo, or text description)."
            )

    @staticmethod
    def validate_location(
        latitude: Optional[float],
        longitude: Optional[float],
        accuracy: Optional[float] = None,
    ) -> None:
        """Validates that location coordinates and accuracy adhere to physical WGS84 ranges."""
        if latitude is None and longitude is None:
            return  # Location is optional in citizen intake

        if (latitude is None and longitude is not None) or (latitude is not None and longitude is None):
            raise LocationValidationError("Both latitude and longitude must be provided together.")

        if not (-90.0 <= latitude <= 90.0):
            raise LocationValidationError(f"Latitude out of physical range [-90, 90]: {latitude}")

        if not (-180.0 <= longitude <= 180.0):
            raise LocationValidationError(f"Longitude out of physical range [-180, 180]: {longitude}")

        if accuracy is not None and accuracy < 0.0:
            raise LocationValidationError(f"Location accuracy radius cannot be negative: {accuracy}")

    @staticmethod
    def validate_photo(content_type: str, file_size: int, filename: Optional[str] = None) -> None:
        """Validates photo MIME type, size limit, and safe extension."""
        if file_size > MAX_PHOTO_SIZE_BYTES:
            raise FileSizeLimitExceededError(
                f"Photo file size ({file_size / (1024*1024):.2f} MB) exceeds maximum limit of 10 MB."
            )

        clean_mime = (content_type or "").split(";")[0].strip().lower()
        if clean_mime not in ALLOWED_PHOTO_MIME_TYPES:
            raise UnsupportedMediaFormatError(
                f"Unsupported photo MIME type '{clean_mime}'. Allowed: {sorted(list(ALLOWED_PHOTO_MIME_TYPES))}"
            )

        if filename:
            ext = Path(filename).suffix.lower()
            if ext in DANGEROUS_EXTENSIONS:
                raise UnsupportedMediaFormatError(f"Prohibited executable file extension: '{ext}'")

    @staticmethod
    def validate_voice(content_type: str, file_size: int, filename: Optional[str] = None) -> None:
        """Validates voice recording MIME type, size limit, and safe extension."""
        if file_size > MAX_VOICE_SIZE_BYTES:
            raise FileSizeLimitExceededError(
                f"Voice memo file size ({file_size / (1024*1024):.2f} MB) exceeds maximum limit of 10 MB."
            )

        clean_mime = (content_type or "").split(";")[0].strip().lower()
        if clean_mime not in ALLOWED_VOICE_MIME_TYPES:
            raise UnsupportedMediaFormatError(
                f"Unsupported audio MIME type '{clean_mime}'. Allowed: {sorted(list(ALLOWED_VOICE_MIME_TYPES))}"
            )

        if filename:
            ext = Path(filename).suffix.lower()
            if ext in DANGEROUS_EXTENSIONS:
                raise UnsupportedMediaFormatError(f"Prohibited executable file extension: '{ext}'")

    @staticmethod
    def validate_description(description: Optional[str]) -> None:
        """Validates optional text description length."""
        if description and len(description) > MAX_DESCRIPTION_LENGTH:
            raise EmptyEvidenceError(
                f"Description length ({len(description)} characters) exceeds maximum limit of {MAX_DESCRIPTION_LENGTH}."
            )
