"""
VayuDrishti - OpenAQ v3 API Client
Controlled, credential-safe HTTP client for OpenAQ REST API v3.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional
import httpx

from backend.ingestion.exceptions import (
    AuthenticationError,
    MissingCredentialError,
    NetworkError,
    OpenAQAPIError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openaq.org/v3"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_RETRIES = 2
DELHI_COORDINATES = "28.6139,77.2090"
DELHI_DEFAULT_RADIUS_METERS = 25000


class OpenAQClient:
    """Controlled OpenAQ v3 API Client.

    Strict security guarantees:
    - Never prints, logs, or returns OPENAQ_API_KEY.
    - Fails gracefully with MissingCredentialError if API key is absent.
    - Retries only transient 5xx/network errors with backoff.
    - Strictly bounds query radius and result limits.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.Client] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAQ_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self._custom_client = http_client

    def has_credentials(self) -> bool:
        """Check if a valid API key string is present."""
        return bool(self.api_key and self.api_key.strip())

    def _get_headers(self) -> Dict[str, str]:
        """Construct request headers. Raises MissingCredentialError if key is unset."""
        if not self.has_credentials():
            raise MissingCredentialError(
                "OPENAQ_API_KEY is not configured in the environment. "
                "Live OpenAQ v3 queries require a valid API key. "
                "Configure OPENAQ_API_KEY in .env or run with a local fixture."
            )
        return {
            "X-API-Key": self.api_key.strip(),
            "User-Agent": "VayuDrishti-Ingestion/1.0 (Hackathon Civic Tech)",
            "Accept": "application/json",
        }

    def _execute_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a GET request with retry backoff and structured exception mapping."""
        headers = self._get_headers()
        url = f"{self.base_url}{endpoint}"
        
        # Log request path without credentials or query secrets
        logger.info(f"OpenAQ request: GET {endpoint} with params={params}")

        attempts = 0
        while attempts <= self.max_retries:
            try:
                attempts += 1
                if self._custom_client:
                    response = self._custom_client.get(url, headers=headers, params=params, timeout=self.timeout)
                else:
                    with httpx.Client(timeout=self.timeout) as client:
                        response = client.get(url, headers=headers, params=params)

                # Check HTTP status codes
                if response.status_code == 200:
                    return response.json()
                elif response.status_code in (401, 403):
                    logger.error(f"OpenAQ authentication rejected (HTTP {response.status_code})")
                    raise AuthenticationError(
                        f"OpenAQ rejected credentials with HTTP {response.status_code}: {response.text[:200]}"
                    )
                elif response.status_code == 429:
                    logger.warning("OpenAQ rate limit exceeded (HTTP 429)")
                    raise RateLimitError("OpenAQ API rate limit exceeded. Back off requests.")
                elif response.status_code >= 500:
                    logger.warning(f"OpenAQ transient server error {response.status_code}, attempt {attempts}/{self.max_retries + 1}")
                    if attempts <= self.max_retries:
                        time.sleep(0.5 * (2 ** (attempts - 1)))
                        continue
                    raise OpenAQAPIError(
                        f"OpenAQ server error HTTP {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )
                else:
                    raise OpenAQAPIError(
                        f"OpenAQ request failed with HTTP {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(f"OpenAQ network error on attempt {attempts}/{self.max_retries + 1}: {type(e).__name__}")
                if attempts <= self.max_retries:
                    time.sleep(0.5 * (2 ** (attempts - 1)))
                    continue
                raise NetworkError(f"OpenAQ network connection failed after {self.max_retries + 1} attempts: {e}") from e

    def get_locations(
        self,
        coordinates: str = DELHI_COORDINATES,
        radius: int = DELHI_DEFAULT_RADIUS_METERS,
        limit: int = 3,
        iso: str = "IN",
    ) -> Dict[str, Any]:
        """Fetch a small, controlled sample of monitoring locations around coordinates."""
        params = {
            "coordinates": coordinates,
            "radius": radius,
            "limit": limit,
            "iso": iso,
        }
        return self._execute_request("/locations", params=params)

    def get_location_latest(self, locations_id: int) -> Dict[str, Any]:
        """Fetch the latest measurements for a specific location ID."""
        return self._execute_request(f"/locations/{locations_id}/latest")

    def get_location_sensors(self, locations_id: int) -> Dict[str, Any]:
        """Fetch sensors for a specific location ID."""
        return self._execute_request(f"/locations/{locations_id}/sensors")

    def get_location_measurements(
        self,
        locations_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 1000,
        page: int = 1,
    ) -> Dict[str, Any]:
        """Fetch historical measurements for a location by traversing location -> sensors -> hours."""
        combined_results: List[Dict[str, Any]] = []
        meta_info: Dict[str, Any] = {"found": 0, "page": page, "limit": limit}

        try:
            sensors_res = self.get_location_sensors(locations_id)
            sensor_items = sensors_res.get("results", [])
            target_sensors = [
                s for s in sensor_items
                if s.get("parameter", {}).get("name") in ["pm25", "pm2.5", "pm10", "pm_10"]
            ]
            if not target_sensors:
                target_sensors = sensor_items  # Fallback to all sensors

            for s in target_sensors:
                s_id = s.get("id")
                if not s_id:
                    continue
                try:
                    s_res = self.get_sensor_measurements(
                        sensors_id=s_id,
                        date_from=date_from,
                        date_to=date_to,
                        limit=limit,
                        page=page,
                    )
                    items = s_res.get("results", [])
                    param_info = s.get("parameter", {})
                    for item in items:
                        if "parameter" not in item and param_info:
                            item["parameter"] = param_info
                        item["locationsId"] = locations_id
                        item["sensorsId"] = s_id
                        combined_results.append(item)
                except OpenAQAPIError as err:
                    logger.warning(f"Could not fetch measurements for sensor {s_id}: {err}")

            meta_info["found"] = len(combined_results)
            return {"results": combined_results, "meta": meta_info}

        except Exception as e:
            logger.warning(f"Sensor traversal failed for location {locations_id}: {e}")
            # Direct fallback attempt if endpoint exists
            params: Dict[str, Any] = {"limit": limit, "page": page}
            if date_from:
                params["datetime_from"] = date_from
            if date_to:
                params["datetime_to"] = date_to
            return self._execute_request(f"/locations/{locations_id}/measurements", params=params)

    def get_sensor_measurements(
        self,
        sensors_id: int,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 1000,
        page: int = 1,
    ) -> Dict[str, Any]:
        """Fetch historical measurements for a specific sensor ID."""
        params: Dict[str, Any] = {
            "limit": limit,
            "page": page,
        }
        if date_from:
            params["datetime_from"] = date_from
        if date_to:
            params["datetime_to"] = date_to
        return self._execute_request(f"/sensors/{sensors_id}/hours", params=params)

    def discover_sensors(self, locations_id: int) -> List[Dict[str, Any]]:
        """Discovers all sensors for a location and parses metadata (parameter, units, datetimeFirst, datetimeLast)."""
        res = self.get_location_sensors(locations_id)
        sensors = []
        for item in res.get("results", []):
            param = item.get("parameter", {})
            dt_first = item.get("datetimeFirst", {}).get("utc") if isinstance(item.get("datetimeFirst"), dict) else item.get("datetimeFirst")
            dt_last = item.get("datetimeLast", {}).get("utc") if isinstance(item.get("datetimeLast"), dict) else item.get("datetimeLast")
            sensors.append({
                "sensor_id": item.get("id"),
                "location_id": locations_id,
                "parameter": param.get("name") or param.get("displayName"),
                "units": param.get("units"),
                "datetimeFirst": dt_first,
                "datetimeLast": dt_last,
            })
        return sensors

    def generate_availability_matrix(
        self,
        stations: List[Dict[str, Any]],
        start_iso: Optional[str] = None,
        end_iso: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generates diagnostic availability matrix for station PM2.5/PM10 sensors."""
        matrix: List[Dict[str, Any]] = []
        for st in stations:
            loc_id = st["location_id"]
            st_name = st["station_id"]
            try:
                sensors = self.discover_sensors(loc_id)
                for s in sensors:
                    pol = s.get("parameter")
                    if str(pol).lower() in ["pm25", "pm2.5", "pm10"]:
                        matrix.append({
                            "station": st_name,
                            "location_id": loc_id,
                            "sensor_id": s["sensor_id"],
                            "pollutant": pol,
                            "units": s.get("units"),
                            "first_available_utc": s.get("datetimeFirst"),
                            "last_available_utc": s.get("datetimeLast"),
                            "requested_window_overlap": True if start_iso and end_iso else False,
                            "historical_data_available": bool(s.get("datetimeFirst") and s.get("datetimeLast")),
                        })
            except Exception as e:
                logger.warning(f"Could not generate availability matrix for station {st_name}: {e}")
                matrix.append({
                    "station": st_name,
                    "location_id": loc_id,
                    "sensor_id": None,
                    "pollutant": "PM2.5",
                    "units": "µg/m³",
                    "first_available_utc": None,
                    "last_available_utc": None,
                    "requested_window_overlap": False,
                    "historical_data_available": False,
                    "error": str(e),
                })
        return matrix

    def fetch_delhi_sample(self, location_limit: int = 3) -> Dict[str, Any]:
        """Controlled fetch workflow for Delhi pilot area.
        
        Fetches up to `location_limit` stations and their latest readings,
        returning a combined raw envelope with provenance metadata.
        """
        retrieval_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        locations_data = self.get_locations(limit=location_limit)
        locations_list = locations_data.get("results", [])

        location_readings: List[Dict[str, Any]] = []
        for loc in locations_list:
            loc_id = loc.get("id")
            if not loc_id:
                continue
            try:
                latest_data = self.get_location_latest(loc_id)
                location_readings.append({
                    "location_id": loc_id,
                    "location_metadata": loc,
                    "latest": latest_data.get("results", []),
                })
            except OpenAQError as err:
                logger.warning(f"Could not fetch latest readings for location {loc_id}: {err}")
                location_readings.append({
                    "location_id": loc_id,
                    "location_metadata": loc,
                    "latest": [],
                    "error": str(err),
                })

        return {
            "metadata": {
                "source": "OpenAQ REST API v3",
                "base_url": self.base_url,
                "retrieved_at": retrieval_timestamp,
                "query": {
                    "target": "Delhi NCR Pilot",
                    "coordinates": DELHI_COORDINATES,
                    "radius_meters": DELHI_DEFAULT_RADIUS_METERS,
                    "location_limit": location_limit,
                },
                "locations_retrieved": len(locations_list),
            },
            "raw_locations": locations_list,
            "location_readings": location_readings,
        }
