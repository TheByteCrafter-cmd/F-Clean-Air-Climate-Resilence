"""
VayuDrishti - Open-Meteo Weather Client
Controlled HTTP client for Open-Meteo Forecast & Reanalysis API.
"""

import logging
import time
from typing import Any, Dict, List, Optional
import httpx

from backend.ingestion.exceptions import (
    NetworkError,
    OpenAQAPIError as OpenMeteoAPIError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_RETRIES = 2

# Delhi central reference point (approved pilot coordinate)
DELHI_LATITUDE = 28.6139
DELHI_LONGITUDE = 77.2090

DEFAULT_HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "surface_pressure",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
    "boundary_layer_height",
]


class OpenMeteoClient:
    """Controlled Open-Meteo HTTP Client.
    
    Characteristics:
    - Open public access (zero authentication required).
    - Hourly resolution requesting m/s wind speed directly.
    - Explicit 15-second timeout with bounded transient retry.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.Client] = None,
    ):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self._custom_client = http_client

    def fetch_weather(
        self,
        latitude: float = DELHI_LATITUDE,
        longitude: float = DELHI_LONGITUDE,
        hourly_variables: Optional[List[str]] = None,
        forecast_days: int = 1,
        past_days: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a controlled request to Open-Meteo forecast API."""
        variables = hourly_variables or DEFAULT_HOURLY_VARIABLES
        params: Dict[str, Any] = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "hourly": ",".join(variables),
            "wind_speed_unit": "ms",
            "timezone": "UTC",
        }

        if start_date and end_date:
            params["start_date"] = start_date
            params["end_date"] = end_date
        else:
            params["forecast_days"] = forecast_days
            if past_days > 0:
                params["past_days"] = past_days

        headers = {
            "User-Agent": "VayuDrishti-WeatherIngestion/1.0 (Hackathon Civic Tech)",
            "Accept": "application/json",
        }

        logger.info(f"Open-Meteo request: GET {self.base_url} lat={latitude}, lon={longitude}, vars={len(variables)}")

        attempts = 0
        while attempts <= self.max_retries:
            try:
                attempts += 1
                if self._custom_client:
                    response = self._custom_client.get(
                        self.base_url, headers=headers, params=params, timeout=self.timeout
                    )
                else:
                    with httpx.Client(timeout=self.timeout) as client:
                        response = client.get(
                            self.base_url, headers=headers, params=params
                        )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    logger.warning("Open-Meteo rate limit exceeded (HTTP 429)")
                    raise RateLimitError("Open-Meteo API rate limit exceeded.")
                elif response.status_code >= 500:
                    logger.warning(f"Open-Meteo server error {response.status_code}, attempt {attempts}/{self.max_retries + 1}")
                    if attempts <= self.max_retries:
                        time.sleep(0.5 * (2 ** (attempts - 1)))
                        continue
                    raise OpenMeteoAPIError(
                        f"Open-Meteo server error HTTP {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )
                else:
                    raise OpenMeteoAPIError(
                        f"Open-Meteo request failed with HTTP {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(f"Open-Meteo network error on attempt {attempts}/{self.max_retries + 1}: {type(e).__name__}")
                if attempts <= self.max_retries:
                    time.sleep(0.5 * (2 ** (attempts - 1)))
                    continue
                raise NetworkError(f"Open-Meteo connection failed after {self.max_retries + 1} attempts: {e}") from e

    def fetch_delhi_sample(self, forecast_days: int = 1, past_days: int = 0) -> Dict[str, Any]:
        """Convenience controlled request for Delhi pilot center."""
        retrieval_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        raw_response = self.fetch_weather(
            latitude=DELHI_LATITUDE,
            longitude=DELHI_LONGITUDE,
            forecast_days=forecast_days,
            past_days=past_days,
        )

        return {
            "metadata": {
                "source": "Open-Meteo Forecast & Reanalysis API",
                "endpoint": self.base_url,
                "retrieved_at": retrieval_timestamp,
                "target_location": {
                    "city": "Delhi NCR Pilot Reference",
                    "latitude": DELHI_LATITUDE,
                    "longitude": DELHI_LONGITUDE,
                },
                "request_parameters": {
                    "forecast_days": forecast_days,
                    "past_days": past_days,
                    "wind_speed_unit": "ms",
                    "timezone": "UTC",
                    "variables": DEFAULT_HOURLY_VARIABLES,
                },
            },
            "raw_response": raw_response,
        }
