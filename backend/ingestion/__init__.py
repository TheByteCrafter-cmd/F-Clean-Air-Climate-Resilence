"""
VayuDrishti - Ingestion Package
Air Quality (OpenAQ) & Meteorology (Open-Meteo) ingestion pipelines.
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

# OpenAQ Ingestion Components
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

# Open-Meteo Weather Ingestion Components
from backend.ingestion.weather_client import (
    DELHI_LATITUDE,
    DELHI_LONGITUDE,
    OpenMeteoClient,
)
from backend.ingestion.weather_normalizer import (
    OpenMeteoNormalizer,
    WeatherNormalizationResult,
)
from backend.ingestion.weather_pipeline import OpenMeteoIngestionPipeline
from backend.ingestion.weather_validator import (
    WeatherQualityReport,
    WeatherValidationOutcome,
    WeatherValidator,
)

__all__ = [
    # OpenAQ
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
    # Open-Meteo Weather
    "OpenMeteoClient",
    "OpenMeteoNormalizer",
    "WeatherValidator",
    "WeatherQualityReport",
    "OpenMeteoIngestionPipeline",
    "WeatherNormalizationResult",
    "WeatherValidationOutcome",
    "DELHI_LATITUDE",
    "DELHI_LONGITUDE",
    # Exceptions
    "IngestionError",
    "OpenAQError",
    "MissingCredentialError",
    "AuthenticationError",
    "RateLimitError",
    "OpenAQAPIError",
    "NetworkError",
]
