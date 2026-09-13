"""
VayuDrishti - Ingestion Package
Air Quality (OpenAQ) & Meteorology (Open-Meteo) ingestion pipelines.
"""

from backend.ingestion.exceptions import (
    AuthenticationError,
    FIRMSAPIError,
    FIRMSError,
    FIRMSParsingError,
    GEEAuthenticationError,
    GEEExtractionError,
    IngestionError,
    MissingCredentialError,
    NetworkError,
    OpenAQAPIError,
    OpenAQError,
    RateLimitError,
    Sentinel5PError,
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

# NASA FIRMS Thermal Anomaly Components
from backend.ingestion.firms_client import (
    DEFAULT_REGIONAL_URL,
    FIRMSClient,
)
from backend.ingestion.firms_normalizer import (
    FIRMSNormalizationResult,
    FIRMSNormalizer,
)
from backend.ingestion.firms_pipeline import FIRMSIngestionPipeline
from backend.ingestion.firms_validator import (
    DELHI_NCR_BBOX,
    NORTH_INDIA_BBOX,
    FIRMSQualityReport,
    FIRMSValidationOutcome,
    FIRMSValidator,
)

# Sentinel-5P TROPOMI Satellite Components
from backend.ingestion.sentinel5p_client import (
    DEFAULT_DELHI_ROI,
    GEE_COLLECTION_ID,
    PRIMARY_BAND as S5P_PRIMARY_BAND,
    Sentinel5PClient,
)
from backend.ingestion.sentinel5p_normalizer import (
    Sentinel5PNormalizationResult,
    Sentinel5PNormalizer,
)
from backend.ingestion.sentinel5p_pipeline import Sentinel5PPipeline
from backend.ingestion.sentinel5p_validator import (
    Sentinel5PQualityReport,
    Sentinel5PValidationOutcome,
    Sentinel5PValidator,
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
    # NASA FIRMS
    "FIRMSClient",
    "FIRMSNormalizer",
    "FIRMSValidator",
    "FIRMSQualityReport",
    "FIRMSIngestionPipeline",
    "FIRMSNormalizationResult",
    "FIRMSValidationOutcome",
    "DEFAULT_REGIONAL_URL",
    "DELHI_NCR_BBOX",
    "NORTH_INDIA_BBOX",
    # Sentinel-5P
    "Sentinel5PClient",
    "Sentinel5PNormalizer",
    "Sentinel5PValidator",
    "Sentinel5PQualityReport",
    "Sentinel5PPipeline",
    "Sentinel5PNormalizationResult",
    "Sentinel5PValidationOutcome",
    "GEE_COLLECTION_ID",
    "S5P_PRIMARY_BAND",
    "DEFAULT_DELHI_ROI",
    # Exceptions
    "IngestionError",
    "OpenAQError",
    "MissingCredentialError",
    "AuthenticationError",
    "RateLimitError",
    "OpenAQAPIError",
    "NetworkError",
    "FIRMSError",
    "FIRMSAPIError",
    "FIRMSParsingError",
    "Sentinel5PError",
    "GEEAuthenticationError",
    "GEEExtractionError",
]
