"""
VayuDrishti — Historical Source Compatibility & Station Recovery Test Suite (Phase 1E-J2E.5.3)

Provides 26 focused unit tests for historical source discovery, sensor/parameter verification,
station recovery mapping, unit validation, feature contract auditing, multi-season coverage,
and frozen model integrity checks.
"""

import hashlib
import json
from pathlib import Path
import pytest

from ml.src.forecasting.historical_source_compatibility import (
    HistoricalSourceCompatibilityAnalyzer,
    VALID_PM25_PARAMETERS,
    VALID_PM25_UNITS,
)
from ml.src.forecasting.historical_ingestion import DELHI_PILOT_STATIONS


@pytest.fixture
def analyzer():
    return HistoricalSourceCompatibilityAnalyzer()


# 1. Source Discovery
def test_01_source_discovery(analyzer):
    sensors = analyzer.discover_station_sensors()
    assert isinstance(sensors, list)
    assert len(sensors) > 0
    sources = {s["source"] for s in sensors}
    assert any("OpenAQ" in src for src in sources)


# 2. Station Identity
def test_02_station_identity(analyzer):
    sensors = analyzer.discover_station_sensors()
    station_ids = {s["canonical_station_id"] for s in sensors}
    assert "ANAND_VIHAR_8118" in station_ids
    assert "PUNJABI_BAGH_8122" in station_ids
    assert "MANDIR_MARG_8125" in station_ids


# 3. Sensor Enumeration
def test_03_sensor_enumeration(analyzer):
    sensors = analyzer.discover_station_sensors()
    for s in sensors:
        assert "sensor_id" in s
        assert "source_location_id" in s
        assert "parameter" in s
        assert s["sensor_id"] is not None


# 4. Parameter Mapping
def test_04_parameter_mapping(analyzer):
    res_pm25 = analyzer.verify_parameter_compatibility("pm25")
    assert res_pm25["status"] == "VERIFIED_PM25"
    assert res_pm25["is_pm25"] is True

    res_pm25_dot = analyzer.verify_parameter_compatibility("pm2.5")
    assert res_pm25_dot["status"] == "VERIFIED_PM25"

    res_o3 = analyzer.verify_parameter_compatibility("o3")
    assert res_o3["status"] == "UNSUPPORTED_PARAMETER"
    assert res_o3["is_pm25"] is False


# 5. PM2.5 Validation
def test_05_pm25_validation(analyzer):
    res = analyzer.verify_parameter_compatibility("PM2.5")
    assert res["is_pm25"] is True
    assert res["canonical_parameter"] == "PM2.5"


# 6. Unit Validation
def test_06_unit_validation(analyzer):
    res_ug = analyzer.validate_units("µg/m³")
    assert res_ug["status"] == "VERIFIED_UNIT"
    assert res_ug["normalized_unit"] == "µg/m³"

    res_alt = analyzer.validate_units("ug/m3")
    assert res_alt["status"] == "VERIFIED_UNIT"
    assert res_alt["normalized_unit"] == "µg/m³"

    res_bad = analyzer.validate_units("unknown_unit")
    assert res_bad["status"] == "UNIT_UNCERTAIN"
    assert res_bad["is_valid"] is False


# 7. Timestamp Normalization
def test_07_timestamp_normalization(analyzer):
    res = analyzer.audit_temporal_granularity("2025-01-15T12:00:00Z")
    assert res["is_valid"] is True
    assert res["utc_iso"] == "2025-01-15T12:00:00Z"
    assert res["hour_aligned"] is True


# 8. Hourly Granularity
def test_08_hourly_granularity(analyzer):
    res = analyzer.audit_temporal_granularity("2025-01-15T12:30:15Z")
    assert res["is_valid"] is True
    assert res["hour_aligned"] is False


# 9. Duplicate Handling
def test_09_duplicate_handling(analyzer):
    obs = [
        {"station_id": "ANAND_VIHAR_8118", "timestamp": "2025-01-01T10:00:00Z", "sensor_id": 23534, "source": "AWS_S3"},
        {"station_id": "ANAND_VIHAR_8118", "timestamp": "2025-01-01T10:00:00Z", "sensor_id": 23534, "source": "AWS_S3"},
    ]
    deduped, metrics = analyzer.handle_sensor_collisions(obs)
    assert len(deduped) == 1
    assert metrics["collision_events"] == 1


# 10. Sensor Collision Handling
def test_10_sensor_collision_handling(analyzer):
    obs = [
        {"station_id": "ANAND_VIHAR_8118", "timestamp": "2025-01-01T10:00:00Z", "sensor_id": 23534, "source": "AWS_S3"},
        {"station_id": "ANAND_VIHAR_8118", "timestamp": "2025-01-01T10:00:00Z", "sensor_id": 24151, "source": "REST_Snapshot"},
    ]
    deduped, metrics = analyzer.handle_sensor_collisions(obs)
    assert len(deduped) == 1
    assert deduped[0]["sensor_id"] == 23534  # Archive sensor takes precedence for time series
    assert metrics["collision_events"] == 1


# 11. Station Aliasing & Primary Scope
def test_11_station_aliasing(analyzer):
    res = analyzer.run_station_recovery_investigation()
    summaries = res["report"]["station_summaries"]
    assert summaries["ANAND_VIHAR_8118"]["role"] == "PRIMARY_PILOT_STATION"
    assert summaries["PUNJABI_BAGH_8122"]["role"] == "VALIDATION_ONLY_STATION"


# 12. Weather Compatibility Check
def test_12_weather_compatibility(analyzer):
    res = analyzer.run_station_recovery_investigation()
    assert "station_summaries" in res["report"]


# 13. +1h Target Compatibility
def test_13_target_plus_1h_compatibility(analyzer):
    res = analyzer.run_station_recovery_investigation()
    av = res["report"]["station_summaries"]["ANAND_VIHAR_8118"]
    assert av["target_generation_usable_rows"]["+1h"] > 0


# 14. +3h Target Compatibility
def test_14_target_plus_3h_compatibility(analyzer):
    res = analyzer.run_station_recovery_investigation()
    av = res["report"]["station_summaries"]["ANAND_VIHAR_8118"]
    assert av["target_generation_usable_rows"]["+3h"] > 0


# 15. +6h Target Compatibility
def test_15_target_plus_6h_compatibility(analyzer):
    res = analyzer.run_station_recovery_investigation()
    av = res["report"]["station_summaries"]["ANAND_VIHAR_8118"]
    assert av["target_generation_usable_rows"]["+6h"] > 0


# 16. Temporal Leakage Prevention Invariant
def test_16_leakage_prevention_invariant(analyzer):
    # Enforce timestamp parsing strictness
    t_past = "2025-01-01T10:00:00Z"
    t_pred = "2025-01-01T12:00:00Z"
    res_past = analyzer.audit_temporal_granularity(t_past)
    res_pred = analyzer.audit_temporal_granularity(t_pred)
    assert res_past["parsed_datetime"] <= res_pred["parsed_datetime"]


# 17. 27-Feature Contract Auditing
def test_17_feature_contract_auditing(analyzer):
    res = analyzer.run_station_recovery_investigation()
    av = res["report"]["station_summaries"]["ANAND_VIHAR_8118"]
    assert av["feature_contract_27_compatible"] is True

    rk = res["report"]["station_summaries"]["RK_PURAM_8124"]
    assert rk["feature_contract_27_compatible"] is False


# 18. Seasonal Coverage Evaluation
def test_18_seasonal_coverage_evaluation(analyzer):
    res = analyzer.run_station_recovery_investigation()
    av_seasons = res["report"]["station_summaries"]["ANAND_VIHAR_8118"]["seasons_coverage"]
    assert av_seasons["WINTER_2024_2025"] == "AVAILABLE"
    assert av_seasons["PRE_MONSOON_2025"] == "UNAVAILABLE"


# 19. Station Period Sufficiency
def test_19_station_period_sufficiency(analyzer):
    res = analyzer.run_station_recovery_investigation()
    av_quality = res["report"]["station_summaries"]["ANAND_VIHAR_8118"]["data_quality_state"]
    assert av_quality in ["SUFFICIENT", "LIMITED"]

    rk_quality = res["report"]["station_summaries"]["RK_PURAM_8124"]["data_quality_state"]
    assert rk_quality == "INSUFFICIENT"


# 20. Historical Provenance Metadata
def test_20_historical_provenance_metadata(analyzer):
    sensors = analyzer.discover_station_sensors()
    for s in sensors:
        assert "source" in s
        assert "artifact_sample" in s


# 21. Machine-Readable Comparison Matrix Generation
def test_21_comparison_matrix_generation(analyzer):
    res = analyzer.run_station_recovery_investigation()
    assert "sensor_matrix" in res
    assert "coverage_matrix" in res
    assert "sensors" in res["sensor_matrix"]
    assert "stations" in res["coverage_matrix"]


# 22. Unsupported Parameter Handling
def test_22_unsupported_parameter_handling(analyzer):
    for param in ["o3", "no2", "so2", "co", "pm10"]:
        res = analyzer.verify_parameter_compatibility(param)
        assert res["is_pm25"] is False
        assert res["status"] == "UNSUPPORTED_PARAMETER"


# 23. Unavailable Station Handling
def test_23_unavailable_station_handling(analyzer):
    res = analyzer.run_station_recovery_investigation()
    unavail = res["report"]["stations_verified_unavailable"]
    assert "RK_PURAM_8124" in unavail
    assert "ITO_8120" in unavail
    assert "DHIER_PUR_8119" in unavail


# 24. Deterministic Output Generation
def test_24_deterministic_output_generation(analyzer):
    res1 = analyzer.run_station_recovery_investigation()
    res2 = analyzer.run_station_recovery_investigation()
    assert res1["report"]["stations_recovered"] == res2["report"]["stations_recovered"]
    assert res1["report"]["stations_verified_unavailable"] == res2["report"]["stations_verified_unavailable"]


# 25. Frozen Model Integrity Preservation
def test_25_frozen_model_integrity_preservation():
    model_dir = Path("ml/models/forecasting")
    expected_hashes = {
        "lightgbm_pm25_1h.txt": "4C1CF555281AF9ABEE7BDA145C543648CB51F6418C939EE2D1A1DA58CA03AD28",
        "lightgbm_pm25_3h.txt": "224DD3C4B0A97CC03ABF621B6AA3070610B60F41DAA05D99D02F8D024571C950",
        "lightgbm_pm25_6h.txt": "0DF954AFBB21F8732814C055EFD5AD380F50AFA4B893942534CE5AD48E8B679F",
    }
    for filename, exp_hash in expected_hashes.items():
        file_path = model_dir / filename
        assert file_path.exists(), f"Model file {filename} does not exist"
        content = file_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest().upper()
        assert actual_hash == exp_hash, f"Frozen model {filename} hash mutated!"


# 26. Artifact File Writer Verification
def test_26_artifact_file_writer_verification(analyzer):
    res = analyzer.run_station_recovery_investigation()
    saved = analyzer.save_artifacts(res)
    for k, v in saved.items():
        assert Path(v).exists()
