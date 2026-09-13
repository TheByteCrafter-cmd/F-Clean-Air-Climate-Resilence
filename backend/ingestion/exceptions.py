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
