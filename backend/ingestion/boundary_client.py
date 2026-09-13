import logging
from typing import Any, Dict
import httpx

from backend.ingestion.exceptions import BoundaryRetrievalError

logger = logging.getLogger(__name__)

# Official DataMeet Municipal Spatial Data GitHub raw endpoints (Verified in Phase 1D)
BOUNDARY_URLS: Dict[str, str] = {
    "delhi": "https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Delhi/Delhi_Wards.geojson",
    "bengaluru": "https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/master/Bangalore/BBMP.geojson",
}

DEFAULT_USER_AGENT = "VayuDrishti-Research/1.0"


class BoundaryClient:
    """Client for retrieving municipal administrative ward boundaries from DataMeet.
    
    Verified source: DataMeet Open Spatial Data repository (CC-BY-SA 4.0).
    """

    def __init__(
        self,
        urls: Dict[str, str] = BOUNDARY_URLS,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 25.0,
    ):
        self.urls = urls
        self.user_agent = user_agent
        self.timeout = timeout
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/geo+json, application/json",
        }

    def fetch_boundary(self, city: str) -> Dict[str, Any]:
        """Fetches the raw municipal boundary GeoJSON for the specified city.
        
        Args:
            city: Either 'delhi' or 'bengaluru' (case-insensitive).
            
        Returns:
            Dict containing raw GeoJSON FeatureCollection, metadata, and attribution.
            
        Raises:
            BoundaryRetrievalError: If the city is unsupported or HTTP retrieval fails.
        """
        normalized_city = city.lower().strip()
        if normalized_city not in self.urls:
            supported = list(self.urls.keys())
            raise BoundaryRetrievalError(
                f"Unsupported boundary city '{city}'. Must be one of: {supported}"
            )

        url = self.urls[normalized_city]
        logger.info(f"Retrieving municipal boundary for {normalized_city} from {url}")

        try:
            with httpx.Client(headers=self.headers, timeout=self.timeout) as client:
                resp = client.get(url)

            if resp.status_code != 200:
                raise BoundaryRetrievalError(
                    f"Boundary retrieval failed for {normalized_city} with HTTP {resp.status_code}",
                    status_code=resp.status_code,
                )

            try:
                data = resp.json()
            except Exception as parse_err:
                raise BoundaryRetrievalError(
                    f"Failed to parse GeoJSON response from {url}: {parse_err}",
                    status_code=200,
                )

            features = data.get("features", [])
            logger.info(
                f"Successfully retrieved {len(features)} ward features for {normalized_city} "
                f"({len(resp.content)} bytes)"
            )

            return {
                "city": normalized_city,
                "url": url,
                "status_code": 200,
                "feature_count": len(features),
                "raw_geojson": data,
                "attribution": "DataMeet Municipal Spatial Data",
                "license": "CC-BY-SA 4.0",
            }

        except BoundaryRetrievalError:
            raise
        except httpx.TimeoutException as te:
            raise BoundaryRetrievalError(
                f"Timed out after {self.timeout}s fetching boundary from {url}: {te}"
            )
        except Exception as exc:
            raise BoundaryRetrievalError(
                f"Unexpected error retrieving boundary from {url}: {exc}"
            )
