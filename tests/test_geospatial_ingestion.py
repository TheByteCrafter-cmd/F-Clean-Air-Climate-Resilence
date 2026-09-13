import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import httpx
import pytest

from backend.api.v1.schemas.geospatial import (
    GeoJSONFeature,
    GeoJSONFeatureCollection,
    GeospatialFeature,
    GeospatialMetadata,
    IndustrialContextFeature,
    RoadContextFeature,
    SensitiveReceptorFeature,
    WardBoundaryFeature,
)
from backend.ingestion.boundary_client import BoundaryClient
from backend.ingestion.boundary_normalizer import BoundaryNormalizer
from backend.ingestion.exceptions import (
    BoundaryRetrievalError,
    OverpassAPIError,
    OverpassRateLimitError,
)
from backend.ingestion.geospatial_pipeline import GeospatialPipeline
from backend.ingestion.geospatial_validator import (
    GeospatialValidator,
    validate_coordinates,
)
from backend.ingestion.osm_client import (
    DELHI_PILOT_BBOX,
    OSMClient,
    build_pilot_overpass_query,
)
from backend.ingestion.osm_normalizer import OSMNormalizer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_geojson_schema_and_models():
    """Tests serialization and field integrity of canonical geospatial models."""
    road = RoadContextFeature(
        feature_id="geo_road_way_101",
        osm_id=101,
        highway="trunk",
        ref="NH-48",
        classification="freight_corridor",
        traffic_density_rank=5,
        city_code="DELHI",
        geometry={"type": "LineString", "coordinates": [[77.1, 28.6], [77.2, 28.7]]},
        source="OPENSTREETMAP_OVERPASS",
        license="ODbL",
        attribution="? OpenStreetMap contributors",
    )
    assert road.feature_type == "road"
    assert road.classification == "freight_corridor"
    assert road.traffic_density_rank == 5
    assert road.license == "ODbL"

    ward = WardBoundaryFeature(
        feature_id="geo_ward_delhi_101",
        ward_id="geo_ward_delhi_101",
        ward_no="101",
        ward_name="Mayapuri",
        admin_level="municipal_ward",
        city_code="DELHI",
        geometry={"type": "Polygon", "coordinates": [[[77.1, 28.6], [77.2, 28.6], [77.2, 28.7], [77.1, 28.7], [77.1, 28.6]]]},
        source="DATAMEET_MUNICIPAL_SPATIAL_DATA",
        license="CC-BY-SA 4.0",
        attribution="DataMeet Municipal Spatial Data",
    )
    assert ward.feature_type == "ward_boundary"
    assert ward.ward_no == "101"
    assert ward.license == "CC-BY-SA 4.0"


def test_coordinate_validation_wgs84():
    """Tests strict WGS84 coordinate boundary rules (EPSG:4326)."""
    # Valid Point
    ok, err = validate_coordinates([77.12, 28.63], "Point")
    assert ok is True
    assert err is None

    # Invalid Point (latitude > 90)
    ok, err = validate_coordinates([77.12, 95.0], "Point")
    assert ok is False
    assert "out of WGS84 bounds" in err

    # Invalid Point (longitude < -180)
    ok, err = validate_coordinates([-185.0, 28.63], "Point")
    assert ok is False
    assert "out of WGS84 bounds" in err

    # Valid LineString
    ok, err = validate_coordinates([[77.1, 28.6], [77.2, 28.7]], "LineString")
    assert ok is True

    # LineString with only 1 point (invalid)
    ok, err = validate_coordinates([[77.1, 28.6]], "LineString")
    assert ok is False
    assert "at least 2 coordinate pairs" in err

    # Valid Polygon (closed linear ring >= 4 coordinates)
    poly = [[[77.1, 28.6], [77.2, 28.6], [77.2, 28.7], [77.1, 28.7], [77.1, 28.6]]]
    ok, err = validate_coordinates(poly, "Polygon")
    assert ok is True

    # Unclosed Polygon (invalid)
    unclosed = [[[77.1, 28.6], [77.2, 28.6], [77.2, 28.7], [77.1, 28.7]]]
    ok, err = validate_coordinates(unclosed, "Polygon")
    assert ok is False
    assert "must be closed" in err


def test_osm_normalizer_supported_tag_filtering():
    """Tests that only supported highway, landuse, and amenity tags are accepted."""
    normalizer = OSMNormalizer(city_code="DELHI")

    # 1. Road corridor
    el_road = {
        "type": "way",
        "id": 12345,
        "tags": {"highway": "trunk", "name": "Ring Road", "ref": "NH-48"},
        "geometry": [{"lat": 28.62, "lon": 77.11}, {"lat": 28.63, "lon": 77.12}],
    }
    res = normalizer.normalize_element(el_road)
    assert res is not None
    cat, pydantic_feat, geojson_feat = res
    assert cat == "road"
    assert pydantic_feat.highway == "trunk"
    assert pydantic_feat.classification == "freight_corridor"
    assert pydantic_feat.attribution == "? OpenStreetMap contributors"

    # 2. Industrial area
    el_ind = {
        "type": "way",
        "id": 67890,
        "tags": {"landuse": "industrial", "industrial": "scrap_metal", "name": "Mayapuri Area"},
        "geometry": [
            {"lat": 28.63, "lon": 77.12},
            {"lat": 28.64, "lon": 77.12},
            {"lat": 28.64, "lon": 77.13},
            {"lat": 28.63, "lon": 77.12},
        ],
    }
    res_ind = normalizer.normalize_element(el_ind)
    assert res_ind is not None
    cat_i, pydantic_i, geojson_i = res_ind
    assert cat_i == "industrial"
    assert pydantic_i.landuse == "industrial"
    assert geojson_i.geometry["type"] == "Polygon"

    # 3. Sensitive receptor (hospital)
    el_hosp = {
        "type": "node",
        "id": 99901,
        "lat": 28.625,
        "lon": 77.115,
        "tags": {"amenity": "hospital", "name": "ESI Hospital"},
    }
    res_h = normalizer.normalize_element(el_hosp)
    assert res_h is not None
    cat_h, pydantic_h, geojson_h = res_h
    assert cat_h == "sensitive_receptor"
    assert pydantic_h.receptor_type == "HEALTHCARE"
    assert geojson_h.geometry["type"] == "Point"


def test_osm_normalizer_rejections():
    """Tests that unsupported tags and malformed geometries are rejected without corruption."""
    normalizer = OSMNormalizer(city_code="DELHI")

    # Unsupported tag: residential footway
    el_unsupported = {
        "type": "way",
        "id": 555,
        "tags": {"highway": "footway", "name": "Jogging Track"},
        "geometry": [{"lat": 28.6, "lon": 77.1}, {"lat": 28.7, "lon": 77.2}],
    }
    assert normalizer.normalize_element(el_unsupported) is None
    assert normalizer.rejected_count == 1
    assert "unsupported_or_missing_tags" in normalizer.rejection_reasons

    # Unsupported landuse (residential)
    el_res = {
        "type": "way",
        "id": 556,
        "tags": {"landuse": "residential"},
        "geometry": [{"lat": 28.6, "lon": 77.1}, {"lat": 28.7, "lon": 77.2}],
    }
    assert normalizer.normalize_element(el_res) is None

    # Missing geometry
    el_nogeom = {
        "type": "way",
        "id": 557,
        "tags": {"highway": "primary"},
    }
    assert normalizer.normalize_element(el_nogeom) is None


def test_delhi_ward_boundary_normalization():
    """Tests Delhi municipal ward properties mapping and source property preservation."""
    normalizer = BoundaryNormalizer(city="delhi")
    raw_ward = {
        "type": "Feature",
        "properties": {
            "Ward_Name": "DELHI CANTT CHARGE 1",
            "Ward_No": "CANT_1",
            "Additional_Custom_Field": 42,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[77.13, 28.63], [77.14, 28.62], [77.14, 28.64], [77.13, 28.64], [77.13, 28.63]]
            ],
        },
    }
    res = normalizer.normalize_feature(raw_ward)
    assert res is not None
    pydantic_ward, geojson_ward = res

    assert pydantic_ward.ward_name == "DELHI CANTT CHARGE 1"
    assert pydantic_ward.ward_no == "CANT_1"
    assert pydantic_ward.feature_id == "geo_ward_delhi_cant_1"
    assert pydantic_ward.city_code == "DELHI"
    assert pydantic_ward.source_properties["Additional_Custom_Field"] == 42
    assert pydantic_ward.attribution == "DataMeet Municipal Spatial Data"
    assert pydantic_ward.license == "CC-BY-SA 4.0"


def test_bengaluru_ward_boundary_normalization():
    """Tests Bengaluru BBMP ward properties mapping and source property preservation."""
    normalizer = BoundaryNormalizer(city="bengaluru")
    raw_ward = {
        "type": "Feature",
        "properties": {
            "KGISWardName": "Kempegowda Ward",
            "KGISWardNo": "1",
            "KGISWardID": 4878,
            "KGISTownCode": "2003",
            "KGISWardCode": "2003001",
            "LGD_WardCode": 1303139,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[77.61, 13.13], [77.62, 13.13], [77.62, 13.14], [77.61, 13.14], [77.61, 13.13]]
            ],
        },
    }
    res = normalizer.normalize_feature(raw_ward)
    assert res is not None
    pydantic_ward, geojson_ward = res

    assert pydantic_ward.ward_name == "Kempegowda Ward"
    assert pydantic_ward.ward_no == "1"
    assert pydantic_ward.source_ward_id == "4878"
    assert pydantic_ward.feature_id == "geo_ward_bengaluru_1"
    assert pydantic_ward.city_code == "BENGALURU"
    assert pydantic_ward.source_properties["KGISWardCode"] == "2003001"


def test_validator_deduplication():
    """Tests that features with duplicate stable IDs are detected and counted."""
    validator = GeospatialValidator(source_name="TEST_SOURCE")
    feat1 = GeoJSONFeature(
        id="geo_road_way_100",
        geometry={"type": "LineString", "coordinates": [[77.1, 28.6], [77.2, 28.7]]},
        properties={"feature_id": "geo_road_way_100", "feature_type": "road"},
    )
    feat2 = GeoJSONFeature(
        id="geo_road_way_100",
        geometry={"type": "LineString", "coordinates": [[77.1, 28.6], [77.2, 28.7]]},
        properties={"feature_id": "geo_road_way_100", "feature_type": "road"},
    )

    ok1, err1 = validator.validate_feature(feat1)
    assert ok1 is True
    assert err1 is None

    ok2, err2 = validator.validate_feature(feat2)
    assert ok2 is False
    assert "duplicate_feature_id" in err2
    assert validator.duplicate_count == 1
    assert len(validator.valid_features) == 1


def test_validator_spatial_bounding_box():
    """Tests bounding box calculation and optional filtering."""
    filter_box = {"lat_min": 28.0, "lat_max": 29.0, "lon_min": 77.0, "lon_max": 78.0}
    validator = GeospatialValidator(source_name="TEST_SOURCE", bbox_filter=filter_box)

    in_scope = GeoJSONFeature(
        id="feat_in",
        geometry={"type": "Point", "coordinates": [77.5, 28.5]},
        properties={"feature_id": "feat_in", "feature_type": "sensitive_receptor"},
    )
    out_scope = GeoJSONFeature(
        id="feat_out",
        geometry={"type": "Point", "coordinates": [80.5, 31.5]},
        properties={"feature_id": "feat_out", "feature_type": "sensitive_receptor"},
    )

    ok_in, _ = validator.validate_feature(in_scope)
    assert ok_in is True

    ok_out, err_out = validator.validate_feature(out_scope)
    assert ok_out is False
    assert err_out == "out_of_bounding_box"


def test_overpass_client_bounded_error_handling():
    """Tests Overpass client retry, timeout, and 429 rate limit exception handling."""
    client = OSMClient(endpoint="https://mock.overpass/api/interpreter", timeout=5.0, max_retries=1)

    # 1. HTTP 429 Rate Limit
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    with patch("httpx.Client.get", return_value=mock_resp_429):
        with pytest.raises(OverpassRateLimitError) as exc_info:
            client.query("[out:json];node(1,1,2,2);out;")
        assert "rate limit reached (HTTP 429)" in str(exc_info.value)

    # 2. HTTP 406 Missing User-Agent
    mock_resp_406 = MagicMock()
    mock_resp_406.status_code = 406
    mock_resp_406.text = "Error: please supply a valid User-Agent"
    with patch("httpx.Client.get", return_value=mock_resp_406):
        with pytest.raises(OverpassAPIError) as exc_info:
            client.query("[out:json];node(1,1,2,2);out;")
        assert exc_info.value.status_code == 406

    # 3. Timeout Handling
    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(OverpassAPIError) as exc_info:
            client.query("[out:json];node(1,1,2,2);out;")
        assert "timed out after" in str(exc_info.value)


def test_boundary_client_error_handling():
    """Tests boundary client validation of unsupported cities and HTTP failures."""
    client = BoundaryClient()

    # Unsupported city
    with pytest.raises(BoundaryRetrievalError) as exc_info:
        client.fetch_boundary("mumbai")
    assert "Unsupported boundary city" in str(exc_info.value)

    # Upstream HTTP 500
    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    with patch("httpx.Client.get", return_value=mock_resp_500):
        with pytest.raises(BoundaryRetrievalError) as exc_info:
            client.fetch_boundary("delhi")
        assert exc_info.value.status_code == 500


def test_geospatial_pipeline_osm_fixture_execution(tmp_path):
    """Tests full execution of OSM pipeline from sanitized fixture file."""
    fixture_path = FIXTURES_DIR / "osm_delhi_sample.json"
    pipeline = GeospatialPipeline(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    result = pipeline.run_osm_pipeline(mode="fixture", fixture_path=fixture_path)
    assert result["status"] == "success"
    assert result["raw_count"] == 9
    assert result["valid_count"] == 7  # 3 roads + 2 industrial + 2 sensitive receptors
    assert result["roads_count"] == 3
    assert result["industrial_count"] == 2
    assert result["receptors_count"] == 2
    assert result["rejected_count"] == 2  # 1 footway + 1 cafe

    # Verify generated GeoJSON files
    roads_file = Path(result["output_paths"]["roads"])
    assert roads_file.exists()
    with open(roads_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 3
        assert data["metadata"]["license"] == "ODbL"
        assert data["metadata"]["attribution"] == "? OpenStreetMap contributors"

    # Verify quality reports
    report_json = Path(result["output_paths"]["quality_report_json"])
    assert report_json.exists()
    report_md = Path(result["output_paths"]["quality_report_md"])
    assert report_md.exists()


def test_geospatial_pipeline_wards_fixture_execution(tmp_path):
    """Tests full execution of ward boundary pipeline from sanitized fixture file."""
    fixture_path = FIXTURES_DIR / "wards_sample.geojson"
    pipeline = GeospatialPipeline(
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
    )

    # Delhi
    res_delhi = pipeline.run_wards_pipeline(city="delhi", mode="fixture", fixture_path=fixture_path)
    assert res_delhi["status"] == "success"
    assert res_delhi["valid_count"] == 2
    delhi_out = Path(res_delhi["output_path"])
    assert delhi_out.exists()
    with open(delhi_out, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data["features"]) == 2
        assert data["metadata"]["license"] == "CC-BY-SA 4.0"

    # Bengaluru
    res_blr = pipeline.run_wards_pipeline(city="bengaluru", mode="fixture", fixture_path=fixture_path)
    assert res_blr["status"] == "success"
    assert res_blr["valid_count"] == 2
    blr_out = Path(res_blr["output_path"])
    assert blr_out.exists()
    with open(blr_out, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data["features"]) == 2
        assert data["features"][0]["properties"]["city_code"] == "BENGALURU"


def test_malformed_geojson_rejected():
    """Tests that completely malformed GeoJSON structures are rejected."""
    validator = GeospatialValidator(source_name="TEST_MALFORMED")

    # Missing geometry type
    bad_geom1 = GeoJSONFeature(
        id="bad1",
        geometry={"coordinates": [77.1, 28.6]},
        properties={"feature_id": "bad1"},
    )
    ok1, err1 = validator.validate_feature(bad_geom1)
    assert ok1 is False
    assert "missing_geometry_type_or_coordinates" in err1

    # Empty LineString coordinates
    bad_geom2 = GeoJSONFeature(
        id="bad2",
        geometry={"type": "LineString", "coordinates": []},
        properties={"feature_id": "bad2"},
    )
    ok2, err2 = validator.validate_feature(bad_geom2)
    assert ok2 is False
    assert "at least 2 coordinate pairs" in err2


def test_source_attribution_and_metadata_preservation():
    """Tests that metadata and provenance are strictly preserved according to specs."""
    validator = GeospatialValidator(source_name="OPENSTREETMAP_OVERPASS")
    feat = GeoJSONFeature(
        id="geo_road_way_999",
        geometry={"type": "LineString", "coordinates": [[77.1, 28.6], [77.2, 28.7]]},
        properties={
            "feature_id": "geo_road_way_999",
            "feature_type": "road",
            "source": "OPENSTREETMAP_OVERPASS",
            "license": "ODbL",
            "attribution": "? OpenStreetMap contributors",
        },
    )
    ok, _ = validator.validate_feature(feat)
    assert ok is True

    meta = validator.get_metadata(
        retrieval_timestamp="2026-09-14T00:00:00Z",
        license_str="ODbL",
        attribution_str="? OpenStreetMap contributors",
        query_filter="TEST_FILTER",
    )
    assert meta.source == "OPENSTREETMAP_OVERPASS"
    assert meta.crs == "EPSG:4326"
    assert meta.feature_count == 1
    assert meta.license == "ODbL"
    assert meta.attribution == "? OpenStreetMap contributors"
    assert meta.query_filter == "TEST_FILTER"
    assert "LineString" in meta.geometry_types
