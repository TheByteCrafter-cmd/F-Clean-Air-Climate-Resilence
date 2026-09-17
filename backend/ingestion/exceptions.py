"""
VayuDrishti - Ingestion Exceptions
"""


class IngestionError(Exception):
    """Base exception for data ingestion failures."""
    pass


class OpenAQError(IngestionError):
    """Base exception for OpenAQ operations."""
    pass


class MissingCredentialError(OpenAQError):
    """Raised when required API credentials (e.g. OPENAQ_API_KEY) are absent."""
    pass


class AuthenticationError(OpenAQError):
    """Raised when upstream rejects authentication credentials (HTTP 401/403)."""
    pass


class RateLimitError(OpenAQError):
    """Raised when upstream API rate limits are exceeded (HTTP 429)."""
    pass


class OpenAQAPIError(OpenAQError):
    """Raised on general HTTP or REST API failure from OpenAQ."""
    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class NetworkError(OpenAQError):
    """Raised when network connection drops or times out."""
    pass


class FIRMSError(IngestionError):
    """Base exception for NASA FIRMS operations."""
    pass


class FIRMSAPIError(FIRMSError):
    """Raised on HTTP failure from NASA FIRMS."""
    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class FIRMSParsingError(FIRMSError):
    """Raised when CSV structure or format cannot be parsed."""
    pass


class Sentinel5PError(IngestionError):
    """Base exception for Sentinel-5P / Earth Engine operations."""
    pass


class GEEAuthenticationError(Sentinel5PError):
    """Raised when Google Earth Engine runtime authentication is unconfigured or failed."""
    pass


class GEEExtractionError(Sentinel5PError):
    """Raised when GEE data extraction, filtering, or raster sampling fails."""
    pass


class GeospatialError(IngestionError):
    """Base exception for geospatial and administrative boundary operations."""
    pass


class OverpassAPIError(GeospatialError):
    """Raised on HTTP failure or unexpected response from OpenStreetMap Overpass API."""
    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class OverpassRateLimitError(GeospatialError):
    """Raised when OpenStreetMap Overpass rate limit or slot availability is exceeded (HTTP 429)."""
    def __init__(self, message: str = "Overpass API rate limit reached (HTTP 429)", retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class BoundaryRetrievalError(GeospatialError):
    """Raised when municipal boundary source retrieval fails or returns invalid HTTP status."""
    def __init__(self, message: str, status_code: int = None):
        super().__init__(message)
        self.status_code = status_code


class GeospatialValidationError(GeospatialError):
    """Raised when geospatial geometry, coordinates, or GeoJSON structure fails validation."""
    pass


class CitizenEvidenceError(IngestionError):
    """Base exception for citizen evidence intake and validation."""
    pass


class ConsentRequiredError(CitizenEvidenceError):
    """Raised when explicit citizen consent is absent or false."""
    pass


class EmptyEvidenceError(CitizenEvidenceError):
    """Raised when no evidence modality (photo, voice, or text) is provided in submission."""
    pass


class UnsupportedMediaFormatError(CitizenEvidenceError):
    """Raised when uploaded file MIME type or format is unsupported or dangerous."""
    pass


class FileSizeLimitExceededError(CitizenEvidenceError):
    """Raised when uploaded media file exceeds the allowed size limit."""
    pass


class LocationValidationError(CitizenEvidenceError):
    """Raised when location coordinates or accuracy values fail physical or format validation."""
    pass


class EvidenceStorageError(CitizenEvidenceError):
    """Raised when writing evidence media or manifest to filesystem fails."""
    pass


class GeminiAnalysisError(IngestionError):
    """Base exception for Gemini multimodal analysis failures."""
    pass


class GeminiCredentialError(GeminiAnalysisError):
    """Raised when GEMINI_API_KEY environment variable is missing or unconfigured."""
    pass


class GeminiAuthenticationError(GeminiAnalysisError):
    """Raised when Gemini API rejects authentication credentials (e.g. invalid key)."""
    pass


class GeminiRateLimitError(GeminiAnalysisError):
    """Raised when Gemini API rate limits or quota are exceeded (HTTP 429)."""
    def __init__(self, message: str = "Gemini API rate limit reached", retry_after: int = None):
        super().__init__(message)
        self.retry_after = retry_after


class GeminiResponseValidationError(GeminiAnalysisError):
    """Raised when Gemini structured JSON output fails Pydantic schema validation."""
    pass


class GeminiTimeoutError(GeminiAnalysisError):
    """Raised when request to Gemini API times out."""
    pass


class EvidenceFusionError(IngestionError):
    """Base exception for multi-source evidence fusion failures."""
    pass


class AnchorMetadataNotFoundError(EvidenceFusionError):
    """Raised when event anchor (citizen report or location) is missing required metadata."""
    pass


class FusionPersistenceError(EvidenceFusionError):
    """Raised when writing fusion result artifact to filesystem fails."""
    pass




