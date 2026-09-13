import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.api.v1.schemas.geospatial import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
)
from backend.ingestion.boundary_client import BoundaryClient
from backend.ingestion.boundary_normalizer import BoundaryNormalizer
from backend.ingestion.osm_normalizer import OSMNormalizer
from backend.ingestion.geospatial_validator import GeospatialValidator
from backend.ingestion.osm_client import (
    OSMClient,
    build_pilot_overpass_query,
    DELHI_PILOT_BBOX,
)

logger = logging.getLogger(__name__)

DEFAULT_RAW_DIR = Path("data/raw")
DEFAULT_PROCESSED_DIR = Path("data/processed/geospatial")


class GeospatialPipeline:
    """End-to-end ingestion and normalization pipeline for OpenStreetMap and Municipal Ward Boundaries.
    
    Coordinates:
      1. Controlled retrieval (OSM Overpass / DataMeet CDN) or fixture replay.
      2. Raw artifact storage in `data/raw/`.
      3. Tag filtering, geometry translation, coordinate validation (WGS84 EPSG:4326).
      4. Jurisdictional property mapping and deduplication.
      5. GeoJSON FeatureCollection artifact export in `data/processed/geospatial/`.
      6. Comprehensive JSON and Markdown quality reporting.
    """

    def __init__(
        self,
        raw_dir: Path = DEFAULT_RAW_DIR,
        processed_dir: Path = DEFAULT_PROCESSED_DIR,
        osm_client: Optional[OSMClient] = None,
        boundary_client: Optional[BoundaryClient] = None,
    ):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.osm_client = osm_client or OSMClient()
        self.boundary_client = boundary_client or BoundaryClient()

    def run_osm_pipeline(
        self,
        mode: str = "live",
        fixture_path: Optional[Path] = None,
        query_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Runs OSM infrastructure ingestion for Delhi pilot corridor."""
        ts_utc = datetime.now(timezone.utc).isoformat()
        ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Step 1: Ingest
        if mode == "fixture":
            if not fixture_path or not Path(fixture_path).exists():
                raise FileNotFoundError(f"OSM fixture file not found: {fixture_path}")
            logger.info(f"Loading OSM data from fixture: {fixture_path}")
            with open(fixture_path, "r", encoding="utf-8") as f:
                raw_payload = json.load(f)
            elements = raw_payload.get("elements", [])
            query_str = "FIXTURE_REPLAY"
            latency_ms = 0
            endpoint = "FIXTURE"
        else:
            query_str = query_override or build_pilot_overpass_query()
            res = self.osm_client.query(query_str)
            raw_payload = res["raw_payload"]
            elements = res["elements"]
            latency_ms = res["latency_ms"]
            endpoint = res["request_url"]

            # Save raw payload to data/raw
            raw_file = self.raw_dir / f"osm_delhi_context_{ts_compact}.json"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(raw_payload, f, indent=2)
            logger.info(f"Saved raw OSM response to {raw_file}")

        # Step 2: Normalize
        normalizer = OSMNormalizer(city_code="DELHI")
        validator = GeospatialValidator(source_name="OPENSTREETMAP_OVERPASS")

        roads: List[GeoJSONFeature] = []
        industrial: List[GeoJSONFeature] = []
        receptors: List[GeoJSONFeature] = []

        for el in elements:
            norm_res = normalizer.normalize_element(el)
            if not norm_res:
                continue
            cat, pydantic_feat, geojson_feat = norm_res
            ok, err = validator.validate_feature(geojson_feat)
            if ok:
                if cat == "road":
                    roads.append(geojson_feat)
                elif cat == "industrial":
                    industrial.append(geojson_feat)
                elif cat == "sensitive_receptor":
                    receptors.append(geojson_feat)

        # Step 3: Export GeoJSON artifacts
        meta = validator.get_metadata(
            retrieval_timestamp=ts_utc,
            license_str="ODbL",
            attribution_str="? OpenStreetMap contributors",
            query_filter=query_str[:200],
        )

        def _save_collection(features: List[GeoJSONFeature], filename: str):
            coll = GeoJSONFeatureCollection(
                type="FeatureCollection",
                features=features,
                metadata=meta,
            )
            out_path = self.processed_dir / filename
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(coll.model_dump_json(indent=2))
            return out_path

        roads_path = _save_collection(roads, "delhi_roads.geojson")
        ind_path = _save_collection(industrial, "delhi_industrial_areas.geojson")
        rec_path = _save_collection(receptors, "delhi_sensitive_pois.geojson")
        all_path = _save_collection(validator.valid_features, "delhi_geospatial_context.geojson")

        # Step 4: Quality Reports
        for rk, rv in normalizer.rejection_reasons.items():
            validator.rejection_reasons[rk] = validator.rejection_reasons.get(rk, 0) + rv
        validator.rejected_count += normalizer.rejected_count

        report_data = validator.generate_quality_report(
            request_url=endpoint,
            retrieval_timestamp=ts_utc,
            latency_ms=latency_ms,
            raw_count=len(elements),
            license_str="ODbL",
            attribution_str="? OpenStreetMap contributors",
            query_scope=query_str[:200],
        )
        report_json_path = self.processed_dir / "osm_delhi_quality_report.json"
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        report_md_path = self.processed_dir / "osm_delhi_quality_report.md"
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(validator.render_markdown_report(report_data))

        logger.info(
            f"OSM Pipeline completed: {len(validator.valid_features)} features valid "
            f"({len(roads)} roads, {len(industrial)} industrial, {len(receptors)} receptors)"
        )

        return {
            "status": "success",
            "mode": mode,
            "raw_count": len(elements),
            "valid_count": len(validator.valid_features),
            "rejected_count": validator.rejected_count,
            "roads_count": len(roads),
            "industrial_count": len(industrial),
            "receptors_count": len(receptors),
            "output_paths": {
                "roads": str(roads_path),
                "industrial": str(ind_path),
                "sensitive_pois": str(rec_path),
                "combined": str(all_path),
                "quality_report_json": str(report_json_path),
                "quality_report_md": str(report_md_path),
            },
            "quality_report": report_data,
        }

    def run_wards_pipeline(
        self,
        city: str = "delhi",
        mode: str = "live",
        fixture_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Runs municipal administrative boundary ingestion for Delhi or Bengaluru."""
        city_lower = city.lower().strip()
        ts_utc = datetime.now(timezone.utc).isoformat()
        ts_compact = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        # Step 1: Ingest
        if mode == "fixture":
            if not fixture_path or not Path(fixture_path).exists():
                raise FileNotFoundError(f"Boundary fixture file not found: {fixture_path}")
            logger.info(f"Loading ward boundaries from fixture: {fixture_path}")
            with open(fixture_path, "r", encoding="utf-8") as f:
                raw_geojson = json.load(f)
            features = raw_geojson.get("features", [])
            endpoint = "FIXTURE"
            latency_ms = 0
        else:
            res = self.boundary_client.fetch_boundary(city_lower)
            raw_geojson = res["raw_geojson"]
            features = raw_geojson.get("features", [])
            endpoint = res["url"]
            latency_ms = 0

            # Save raw GeoJSON to data/raw
            raw_file = self.raw_dir / f"{city_lower}_wards_raw_{ts_compact}.geojson"
            with open(raw_file, "w", encoding="utf-8") as f:
                json.dump(raw_geojson, f, indent=2)
            logger.info(f"Saved raw {city_lower} boundary to {raw_file}")

        # Step 2: Normalize & Validate
        normalizer = BoundaryNormalizer(city=city_lower)
        validator = GeospatialValidator(source_name=f"DATAMEET_{city_lower.upper()}_WARDS")

        valid_wards: List[GeoJSONFeature] = []
        for feat in features:
            norm_res = normalizer.normalize_feature(feat)
            if not norm_res:
                continue
            pydantic_model, geojson_feat = norm_res
            ok, err = validator.validate_feature(geojson_feat)
            if ok:
                valid_wards.append(geojson_feat)

        # Step 3: Export GeoJSON
        meta = validator.get_metadata(
            retrieval_timestamp=ts_utc,
            license_str="CC-BY-SA 4.0",
            attribution_str="DataMeet Municipal Spatial Data",
            query_filter=f"MUNICIPAL_BOUNDARIES_{city_lower.upper()}",
        )
        coll = GeoJSONFeatureCollection(
            type="FeatureCollection",
            features=valid_wards,
            metadata=meta,
        )
        out_filename = f"{city_lower}_wards.geojson"
        out_path = self.processed_dir / out_filename
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(coll.model_dump_json(indent=2))

        # Step 4: Quality Reports
        for rk, rv in normalizer.rejection_reasons.items():
            validator.rejection_reasons[rk] = validator.rejection_reasons.get(rk, 0) + rv
        validator.rejected_count += normalizer.rejected_count

        report_data = validator.generate_quality_report(
            request_url=endpoint,
            retrieval_timestamp=ts_utc,
            latency_ms=latency_ms,
            raw_count=len(features),
            license_str="CC-BY-SA 4.0",
            attribution_str="DataMeet Municipal Spatial Data",
            query_scope=f"Administrative Ward Boundaries ({city_lower.title()})",
        )
        report_json_path = self.processed_dir / f"{city_lower}_wards_quality_report.json"
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        report_md_path = self.processed_dir / f"{city_lower}_wards_quality_report.md"
        with open(report_md_path, "w", encoding="utf-8") as f:
            f.write(validator.render_markdown_report(report_data))

        logger.info(
            f"Wards Pipeline ({city_lower}) completed: {len(valid_wards)} valid wards "
            f"exported to {out_path}"
        )

        return {
            "status": "success",
            "city": city_lower,
            "mode": mode,
            "raw_count": len(features),
            "valid_count": len(valid_wards),
            "rejected_count": validator.rejected_count,
            "output_path": str(out_path),
            "quality_report_json": str(report_json_path),
            "quality_report_md": str(report_md_path),
            "quality_report": report_data,
        }
