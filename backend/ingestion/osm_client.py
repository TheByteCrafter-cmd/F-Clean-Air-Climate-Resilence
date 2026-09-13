import logging
import time
from typing import Any, Dict, Optional, Tuple
import httpx

from backend.ingestion.exceptions import (
    OverpassAPIError,
    OverpassRateLimitError,
)

logger = logging.getLogger(__name__)

# Canonical Overpass API Endpoint
DEFAULT_OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"
DEFAULT_USER_AGENT = "VayuDrishti-Research/1.0"

# Approved Delhi pilot geographic bounding box (Mayapuri, Wazirpur, Central/West Delhi corridors)
DELHI_PILOT_BBOX: Dict[str, float] = {
    "lat_min": 28.60,
    "lat_max": 28.72,
    "lon_min": 77.08,
    "lon_max": 77.22,
}


def build_pilot_overpass_query(
    bbox: Optional[Dict[str, float]] = None,
    limit_per_category: int = 50,
    timeout_seconds: int = 25,
) -> str:
    """Constructs a balanced, index-optimized Overpass QL query for the pilot corridor.
    
    Uses multi-stage out directives to guarantee balanced representation across:
      1. Major freight and arterial roads (trunk, primary, secondary)
      2. Industrial land-use areas
      3. Sensitive community receptors (hospitals, schools, clinics)
    """
    box = bbox or DELHI_PILOT_BBOX
    s, w, n, e = box["lat_min"], box["lon_min"], box["lat_max"], box["lon_max"]
    bbox_str = f"{s:.4f},{w:.4f},{n:.4f},{e:.4f}"

    return f"""[out:json][timeout:{timeout_seconds}];
(
  way["highway"="trunk"]({bbox_str});
  way["highway"="primary"]({bbox_str});
  way["highway"="secondary"]({bbox_str});
);
out geom {limit_per_category};
(
  way["landuse"="industrial"]({bbox_str});
  relation["landuse"="industrial"]({bbox_str});
);
out geom 25;
(
  node["amenity"="hospital"]({bbox_str});
  node["amenity"="school"]({bbox_str});
  node["amenity"="clinic"]({bbox_str});
);
out {limit_per_category};
"""


class OSMClient:
    """Client for querying OpenStreetMap vectors via the Overpass API.
    
    Adheres strictly to the responsible use policy:
      - Explicit user agent (VayuDrishti-Research/1.0)
      - Bounded queries with explicit timeout
      - Respectful request frequency and rate limit (HTTP 429) detection
      - Preserves upstream attribution and licensing
    """

    def __init__(
        self,
        endpoint: str = DEFAULT_OVERPASS_ENDPOINT,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 25.0,
        max_retries: int = 2,
    ):
        self.endpoint = endpoint
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

    def query(self, query_ql: str) -> Dict[str, Any]:
        """Executes an Overpass QL query against the interpreter endpoint.
        
        Args:
            query_ql: Overpass QL formatted query string.
            
        Returns:
            Dict containing raw elements, metadata, latency, and attribution.
            
        Raises:
            OverpassRateLimitError: If server responds with HTTP 429.
            OverpassAPIError: If upstream returns HTTP error or invalid response.
        """
        logger.info(f"Querying Overpass API at {self.endpoint} (timeout={self.timeout}s)")
        start_time = time.time()
        last_error = None

        for attempt in range(1, self.max_retries + 2):
            try:
                # Use GET with query param 'data' for maximum CDN/proxy compatibility
                with httpx.Client(headers=self.headers, timeout=self.timeout) as client:
                    resp = client.get(self.endpoint, params={"data": query_ql})

                latency_ms = int((time.time() - start_time) * 1000)

                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                    except Exception as parse_err:
                        raise OverpassAPIError(
                            f"Failed to parse Overpass response as JSON: {parse_err}",
                            status_code=200,
                            response_body=resp.text[:500],
                        )

                    elements = payload.get("elements", [])
                    logger.info(
                        f"Overpass query successful: status=200, latency={latency_ms}ms, "
                        f"elements={len(elements)}"
                    )
                    return {
                        "elements": elements,
                        "raw_payload": payload,
                        "status_code": 200,
                        "latency_ms": latency_ms,
                        "request_url": self.endpoint,
                        "query_ql": query_ql,
                        "attribution": "? OpenStreetMap contributors",
                        "license": "ODbL",
                    }

                elif resp.status_code == 429:
                    logger.warning(
                        f"Overpass API returned 429 Too Many Requests (attempt {attempt}/{self.max_retries + 1})"
                    )
                    if attempt <= self.max_retries:
                        wait_time = 15.0 * attempt
                        logger.info(f"Respectful backoff: waiting {wait_time:.1f}s for Overpass slot to free...")
                        time.sleep(wait_time)
                        continue
                    raise OverpassRateLimitError(
                        f"Overpass API rate limit reached (HTTP 429) at {self.endpoint}",
                        retry_after=60,
                    )

                elif resp.status_code == 406:
                    raise OverpassAPIError(
                        f"Overpass API rejected request with HTTP 406 (User-Agent or Accept header invalid)",
                        status_code=406,
                        response_body=resp.text[:500],
                    )

                elif 500 <= resp.status_code < 600:
                    logger.warning(
                        f"Overpass API server error {resp.status_code} (attempt {attempt}/{self.max_retries + 1})"
                    )
                    last_error = OverpassAPIError(
                        f"Overpass API server error {resp.status_code}",
                        status_code=resp.status_code,
                        response_body=resp.text[:500],
                    )
                    if attempt <= self.max_retries:
                        time.sleep(2.0 * attempt)
                        continue
                    raise last_error

                else:
                    raise OverpassAPIError(
                        f"Overpass API returned HTTP {resp.status_code}",
                        status_code=resp.status_code,
                        response_body=resp.text[:500],
                    )

            except httpx.TimeoutException as te:
                logger.warning(f"Overpass API request timed out (attempt {attempt}/{self.max_retries + 1}): {te}")
                last_error = OverpassAPIError(f"Overpass API timed out after {self.timeout}s: {te}")
                if attempt <= self.max_retries:
                    time.sleep(2.0 * attempt)
                    continue
                raise last_error

            except (OverpassRateLimitError, OverpassAPIError):
                raise

            except Exception as exc:
                logger.error(f"Unexpected error communicating with Overpass API: {exc}")
                raise OverpassAPIError(f"Overpass client error: {exc}")

        if last_error:
            raise last_error
        raise OverpassAPIError("Unknown failure during Overpass query")
