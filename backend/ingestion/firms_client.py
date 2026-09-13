"""
VayuDrishti - NASA FIRMS Client
Controlled HTTP client for NASA FIRMS Active Fire / Thermal Anomaly data.
"""

import csv
import io
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
import httpx

from backend.ingestion.exceptions import (
    FIRMSAPIError,
    FIRMSParsingError,
    NetworkError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

# Primary unauthenticated 24h near-real-time regional feed for South Asia (Suomi-NPP VIIRS C2)
DEFAULT_REGIONAL_URL = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_South_Asia_24h.csv"
)

# Optional keyed Web API base URL
KEYED_API_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_RETRIES = 2
MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB safety ceiling


class FIRMSClient:
    """Controlled NASA FIRMS HTTP Client.
    
    Retrieves near-real-time active fire / thermal anomaly data.
    Primary mode: Open unauthenticated South Asia regional CSV stream.
    Secondary mode: Targeted bounding-box API when NASA_FIRMS_MAP_KEY is provided.
    
    Features:
    - Explicit 15-second timeout
    - Bounded transient failure retries (max 2) with backoff
    - Payload size ceiling protection
    - Safe CSV parsing into structured row dictionaries
    """

    def __init__(
        self,
        regional_url: str = DEFAULT_REGIONAL_URL,
        map_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.Client] = None,
    ):
        self.regional_url = regional_url
        self.map_key = map_key or os.environ.get("NASA_FIRMS_MAP_KEY")
        self.timeout = timeout
        self.max_retries = max_retries
        self._custom_client = http_client

    def fetch_regional_feed(self, url: Optional[str] = None) -> str:
        """Fetch the unauthenticated South Asia 24h regional CSV stream.
        
        Returns raw CSV text.
        """
        target_url = url or self.regional_url
        headers = {
            "User-Agent": "VayuDrishti-FIRMSIngestion/1.0 (Hackathon Civic Tech)",
            "Accept": "text/csv,text/plain",
        }

        logger.info(f"FIRMS request: GET {target_url}")
        return self._execute_request(target_url, headers=headers)

    def fetch_targeted_feed(
        self,
        bbox: Tuple[float, float, float, float],
        days: int = 1,
        source: str = "VIIRS_SNPP_NRT",
    ) -> str:
        """Fetch targeted bounding-box active fire CSV using NASA_FIRMS_MAP_KEY.
        
        Args:
            bbox: (min_lon, min_lat, max_lon, max_lat) WGS84 coordinates.
            days: Integer days back (1-10).
            source: Instrument source identifier.
        """
        if not self.map_key:
            raise FIRMSAPIError(
                "NASA_FIRMS_MAP_KEY is required for targeted bounding-box API. "
                "Use the open regional stream instead or set NASA_FIRMS_MAP_KEY."
            )

        min_lon, min_lat, max_lon, max_lat = bbox
        bbox_str = f"{min_lon:.4f},{min_lat:.4f},{max_lon:.4f},{max_lat:.4f}"
        url = f"{KEYED_API_BASE}/{self.map_key}/{source}/{bbox_str}/{days}"

        headers = {
            "User-Agent": "VayuDrishti-FIRMSIngestion/1.0 (Hackathon Civic Tech)",
            "Accept": "text/csv,text/plain",
        }

        logger.info(f"FIRMS targeted request: GET bbox={bbox_str}, days={days}")
        return self._execute_request(url, headers=headers)

    def _execute_request(self, url: str, headers: Dict[str, str]) -> str:
        """Internal bounded HTTP executor with transient error retries."""
        attempts = 0
        while attempts <= self.max_retries:
            try:
                attempts += 1
                if self._custom_client:
                    response = self._custom_client.get(
                        url, headers=headers, timeout=self.timeout
                    )
                else:
                    with httpx.Client(timeout=self.timeout) as client:
                        response = client.get(url, headers=headers)

                # Check HTTP status codes
                if response.status_code == 200 or response.status_code == 206:
                    content_length = len(response.content)
                    if content_length > MAX_PAYLOAD_BYTES:
                        raise FIRMSAPIError(
                            f"Payload size {content_length} exceeds maximum allowed {MAX_PAYLOAD_BYTES} bytes."
                        )
                    return response.text

                elif response.status_code == 429:
                    raise RateLimitError(
                        "NASA FIRMS upstream rate limit exceeded (HTTP 429).",
                    )
                elif response.status_code in (401, 403):
                    raise FIRMSAPIError(
                        f"NASA FIRMS authentication/authorization failed (HTTP {response.status_code}).",
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )
                elif response.status_code >= 500:
                    if attempts <= self.max_retries:
                        backoff = 0.5 * (2 ** (attempts - 1))
                        logger.warning(
                            f"FIRMS server error {response.status_code}. Retrying in {backoff:.1f}s (attempt {attempts}/{self.max_retries})"
                        )
                        time.sleep(backoff)
                        continue
                    raise FIRMSAPIError(
                        f"NASA FIRMS server error (HTTP {response.status_code}) after retries.",
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )
                else:
                    raise FIRMSAPIError(
                        f"NASA FIRMS unexpected status (HTTP {response.status_code}).",
                        status_code=response.status_code,
                        response_body=response.text[:200],
                    )

            except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as exc:
                if attempts <= self.max_retries:
                    backoff = 0.5 * (2 ** (attempts - 1))
                    logger.warning(
                        f"FIRMS network error: {exc}. Retrying in {backoff:.1f}s (attempt {attempts}/{self.max_retries})"
                    )
                    time.sleep(backoff)
                    continue
                raise NetworkError(f"FIRMS network connection failed after {attempts} attempts: {exc}")

        raise NetworkError("FIRMS request failed after maximum retries.")

    @staticmethod
    def parse_csv(csv_text: str) -> List[Dict[str, str]]:
        """Parse raw CSV text into a list of row dictionaries."""
        if not csv_text or not csv_text.strip():
            return []

        try:
            # Handle potential comment lines or BOM
            clean_text = csv_text.lstrip("﻿")
            reader = csv.DictReader(io.StringIO(clean_text))
            rows = []
            for row in reader:
                # Strip keys and values
                clean_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
                rows.append(clean_row)
            return rows
        except Exception as exc:
            raise FIRMSParsingError(f"Failed to parse CSV text: {exc}")
