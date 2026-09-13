"""
VayuDrishti - Sentinel-5P / Google Earth Engine Client
Manages Earth Engine catalog contracts, authentication audits, and controlled extractions.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.ingestion.exceptions import (
    GEEAuthenticationError,
    GEEExtractionError,
    Sentinel5PError,
)

logger = logging.getLogger(__name__)

# Exact Google Earth Engine Dataset Catalog identifier
GEE_COLLECTION_ID = "COPERNICUS/S5P/NRTI/L3_NO2"
GEE_OFFLINE_COLLECTION_ID = "COPERNICUS/S5P/OFFL/L3_NO2"

# Primary band for urban and regional air quality monitoring
PRIMARY_BAND = "tropospheric_NO2_column_number_density"

# Essential supporting metadata and QA bands
SUPPORTING_BANDS = [
    "NO2_column_number_density",
    "stratospheric_NO2_column_number_density",
    "cloud_fraction",
]

# Approved compact Delhi pilot Region of Interest (ROI)
DEFAULT_DELHI_ROI: Dict[str, float] = {
    "lat_min": 28.40,
    "lat_max": 28.85,
    "lon_min": 76.90,
    "lon_max": 77.35,
}


class Sentinel5PClient:
    """Sentinel-5P / Earth Engine Satellite Data Client.
    
    Handles:
    1. Earth Engine runtime authentication verification.
    2. Official catalog contract specification for COPERNICUS/S5P/NRTI/L3_NO2.
    3. Controlled spatial/temporal extraction when GEE credentials are valid.
    4. Deterministic offline fixture and cached extraction loading.
    
    SCIENTIFIC INTEGRITY:
    Maintains tropospheric NO2 column density strictly in mol/m? (no fake conversions).
    """

    def __init__(self, collection_id: str = GEE_COLLECTION_ID):
        self.collection_id = collection_id
        self._ee_initialized = False

    def check_authentication(self) -> Tuple[bool, str]:
        """Audit whether Google Earth Engine is authenticated in the current runtime.
        
        Returns:
            (is_authenticated, status_message)
        """
        try:
            import ee
            try:
                ee.Initialize()
                self._ee_initialized = True
                return (True, "ACTIVE")
            except Exception as exc:
                self._ee_initialized = False
                return (False, f"GEE RUNTIME ACCESS NOT CONFIGURED: {exc}")
        except ImportError:
            self._ee_initialized = False
            return (False, "GEE RUNTIME ACCESS NOT CONFIGURED: earthengine-api not installed")

    @staticmethod
    def get_catalog_contract() -> Dict[str, Any]:
        """Returns the verified Google Earth Engine catalog contract for Sentinel-5P NO2."""
        return {
            "dataset_id": GEE_COLLECTION_ID,
            "offline_dataset_id": GEE_OFFLINE_COLLECTION_ID,
            "provider": "European Union / ESA / Copernicus",
            "platform": "Sentinel-5P",
            "instrument": "TROPOMI",
            "spatial_resolution_m": 1113.2,  # approx 0.01 deg in GEE gridding (~5.5km along-track)
            "temporal_cadence": "Daily (approx. 13:30 local solar overpass)",
            "primary_band": {
                "name": PRIMARY_BAND,
                "unit": "mol/m?",
                "physical_meaning": "Tropospheric vertical column NO2 number density (ground to tropopause)",
                "valid_min": -0.0001,  # Permitted negative noise threshold
                "valid_max": 0.01,
            },
            "supporting_bands": {
                "cloud_fraction": {
                    "unit": "fraction (0.0 to 1.0)",
                    "description": "Effective cloud fraction used for QA screening",
                    "filter_threshold": "<= 0.5 for valid retrieval (<= 0.3 for clear sky)",
                },
                "stratospheric_NO2_column_number_density": {
                    "unit": "mol/m?",
                    "description": "Stratospheric NO2 column derived from assimilation model",
                },
                "NO2_column_number_density": {
                    "unit": "mol/m?",
                    "description": "Total vertical column NO2 (troposphere + stratosphere)",
                },
            },
            "quality_filtering_policy": (
                "Pixels with cloud_fraction > 0.5 must be rejected or flagged. "
                "Negative values between -0.0001 and 0.0 mol/m? must NOT be zero-clamped, "
                "as clamping introduces positive statistical bias in spatial averaging."
            ),
        }

    def extract_live(
        self,
        roi: Optional[Dict[str, float]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_samples: int = 50,
    ) -> List[Dict[str, Any]]:
        """Attempt controlled live extraction from Google Earth Engine.
        
        Fails gracefully with GEEAuthenticationError if authentication is unconfigured.
        """
        is_auth, status_msg = self.check_authentication()
        if not is_auth:
            raise GEEAuthenticationError(status_msg)

        # If authenticated, execute controlled query
        import ee

        target_roi = roi or DEFAULT_DELHI_ROI
        geom = ee.Geometry.Rectangle([
            target_roi["lon_min"],
            target_roi["lat_min"],
            target_roi["lon_max"],
            target_roi["lat_max"],
        ])

        collection = (
            ee.ImageCollection(self.collection_id)
            .filterBounds(geom)
            .select([PRIMARY_BAND] + SUPPORTING_BANDS)
        )

        if start_date and end_date:
            collection = collection.filterDate(start_date, end_date)
        else:
            # Most recent 24-48 hours
            collection = collection.limit(1)

        count = collection.size().getInfo()
        if count == 0:
            logger.info("GEE query returned 0 matching scenes for ROI and date range.")
            return []

        # Sample points within the ROI
        image = ee.Image(collection.first())
        samples_fc = image.sample(
            region=geom,
            scale=5500,  # 5.5km resolution
            numPixels=max_samples,
            geometries=True,
        )

        features = samples_fc.getInfo().get("features", [])
        records = []
        for feat in features:
            coords = feat.get("geometry", {}).get("coordinates", [None, None])
            props = feat.get("properties", {})
            records.append({
                "latitude": coords[1],
                "longitude": coords[0],
                "tropospheric_NO2_column_number_density": props.get(PRIMARY_BAND),
                "cloud_fraction": props.get("cloud_fraction"),
                "stratospheric_NO2_column_number_density": props.get("stratospheric_NO2_column_number_density"),
                "NO2_column_number_density": props.get("NO2_column_number_density"),
                "system_time_start": image.get("system:time_start").getInfo(),
            })

        return records

    @staticmethod
    def load_fixture(file_path: Path) -> List[Dict[str, Any]]:
        """Load and parse local offline JSON fixture or cached JSONL."""
        fpath = Path(file_path)
        if not fpath.exists():
            raise FileNotFoundError(f"Satellite fixture not found at {fpath}")

        raw_text = fpath.read_text(encoding="utf-8").strip()
        if not raw_text:
            return []

        if fpath.suffix == ".jsonl":
            return [json.loads(line) for line in raw_text.splitlines() if line.strip()]
        else:
            data = json.loads(raw_text)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "observations" in data:
                return data["observations"]
            elif isinstance(data, dict) and "features" in data:
                return data["features"]
            return [data]
