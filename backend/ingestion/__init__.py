"""
VayuDrishti - Ingestion Package
"""

from backend.ingestion.exceptions import (
    AuthenticationError,
    IngestionError,
    MissingCredentialError,
    NetworkError,
    OpenAQAPIError,
    OpenAQError,
    RateLimitError,
)
from backend.ingestion.normalizer import (
    CANONICAL_UNIT,
    NORMALIZATION_VERSION,
    POLLUTANT_MAP,
    NormalizationResult,
    OpenAQNormalizer,
)
from backend.ingestion.openaq_client import OpenAQClient
from backend.ingestion.pipeline import OpenAQIngestionPipeline
from backend.ingestion.validator import (
    CANONICAL_POLLUTANTS,
    DataQualityReport,
    ObservationValidator,
    ValidationOutcome,
)

__all__ = [
    "OpenAQClient",
    "OpenAQNormalizer",
    "ObservationValidator",
    "DataQualityReport",
    "OpenAQIngestionPipeline",
    "NormalizationResult",
    "ValidationOutcome",
    "CANONICAL_POLLUTANTS",
    "CANONICAL_UNIT",
    "POLLUTANT_MAP",
    "NORMALIZATION_VERSION",
    "IngestionError",
    "OpenAQError",
    "MissingCredentialError",
    "AuthenticationError",
    "RateLimitError",
    "OpenAQAPIError",
    "NetworkError",
]
