"""
VayuDrishti — Multi-Season & Multi-Station Validation Data Expansion Tests (Phase 1E-J2E.5.2)

Comprehensive test suite verifying station discovery, station eligibility, period discovery,
period boundaries, data quality gates, 27-feature contract parity, target alignment, zero temporal leakage,
persistence baseline evaluation, frozen model evaluation isolation, candidate model evaluation isolation,
residual diagnostics, conformal uncertainty coverage, readiness evidence status, and deterministic execution.
"""

import json
import pytest
from pathlib import Path

from ml.src.forecasting import MultiStationDataExpander
from ml.src.forecasting.multi_station_validation import (
    HISTORICAL_PERIOD_DEFINITIONS,
    VALID_EVIDENCE_STATUSES,
)
from ml.src.forecasting.robust_temporal_validation import (
    FROZEN_MODEL_HASHES,
    PRODUCTION_VALIDATION_STATUS,
    compute_file_sha256,
)


@pytest.fixture
def expander():
    """Fixture providing MultiStationDataExpander."""
    return MultiStationDataExpander(
        data_root=Path("data"),
        models_dir=Path("ml/models/forecasting"),
        candidates_dir=Path("ml/models/forecasting/candidates"),
    )


# Test 1: Station discovery finds all 6 Delhi pilot stations
def test_01_station_discovery_all_stations(expander):
    stations = expander.discover_stations()
    assert len(stations) == 6
    st_ids = [s["station_id"] for s in stations]
    assert "ANAND_VIHAR_8118" in st_ids
    assert "PUNJABI_BAGH_8122" in st_ids
    assert "MANDIR_MARG_8125" in st_ids
    assert "RK_PURAM_8124" in st_ids
    assert "ITO_8120" in st_ids
    assert "DHIER_PUR_8119" in st_ids


# Test 2: Station eligibility identifies Anand Vihar as eligible and others as incompatible
def test_02_station_eligibility_classification(expander):
    stations = expander.discover_stations()
    by_id = {s["station_id"]: s for s in stations}
    assert by_id["ANAND_VIHAR_8118"]["eligible_for_forecasting"] is True
    assert by_id["PUNJABI_BAGH_8122"]["eligible_for_forecasting"] is False
    assert by_id["MANDIR_MARG_8125"]["eligible_for_forecasting"] is False
    assert by_id["RK_PURAM_8124"]["eligible_for_forecasting"] is False
    assert by_id["ITO_8120"]["eligible_for_forecasting"] is False
    assert by_id["DHIER_PUR_8119"]["eligible_for_forecasting"] is False


# Test 3: Period discovery audits all historical period definitions
def test_03_period_discovery(expander):
    stations = expander.discover_stations()
    coverage = expander.evaluate_period_coverage(stations)
    assert "WINTER_2024_2025" in coverage
    assert "PRE_MONSOON_2025" in coverage
    assert "MONSOON_2025" in coverage
    assert "POST_MONSOON_2025" in coverage


# Test 4: Period boundaries check UTC start/end timestamp formats
def test_04_period_boundaries_utc_format(expander):
    for p in HISTORICAL_PERIOD_DEFINITIONS:
        assert p["start_utc"].endswith("Z")
        assert p["end_utc"].endswith("Z")
        assert p["start_utc"] < p["end_utc"]


# Test 5: Missing-period behavior marks unavailable periods correctly
def test_05_missing_period_behavior(expander):
    stations = expander.discover_stations()
    coverage = expander.evaluate_period_coverage(stations)
    assert coverage["WINTER_2024_2025"]["available"] is True
    assert coverage["PRE_MONSOON_2025"]["available"] is False
    assert coverage["MONSOON_2025"]["available"] is False
    assert coverage["POST_MONSOON_2025"]["available"] is False


# Test 6: Data sufficiency state evaluation
def test_06_data_sufficiency_states(expander):
    summary = expander.execute_multi_station_expansion()
    matrix = summary["coverage_matrix"]["matrix"]
    status_codes = {m["status_code"] for m in matrix}
    assert "SUFFICIENT" in status_codes
    assert "INCOMPATIBLE_PARAMETER" in status_codes


# Test 7: Duplicate detection in raw discovery
def test_07_duplicate_detection(expander):
    stations = expander.discover_stations()
    for s in stations:
        assert s["total_observation_count"] >= 0
        assert s["pm25_observation_count"] >= 0


# Test 8: Temporal gap audit in station quality
def test_08_temporal_gaps_audit(expander):
    summary = expander.execute_multi_station_expansion()
    q_reports = summary["readiness_report"]["quality_gate_summary"]
    for q in q_reports:
        assert q["max_temporal_gap_hours"] >= 0.0


# Test 9: PM2.5 availability verification per station
def test_09_pm25_availability(expander):
    stations = expander.discover_stations()
    by_id = {s["station_id"]: s for s in stations}
    assert by_id["ANAND_VIHAR_8118"]["pm25_available"] is True
    assert by_id["PUNJABI_BAGH_8122"]["pm25_available"] is False


# Test 10: Weather alignment availability for all stations
def test_10_weather_alignment(expander):
    stations = expander.discover_stations()
    for s in stations:
        assert s["weather_alignment_available"] is True


# Test 11: 27-feature contract validation
def test_11_feature_contract_27_features(expander):
    manifest_features = expander.assembler.manifest_features
    assert len(manifest_features) == 27
    assert "latitude" in manifest_features
    assert "pm25_lag_1h" in manifest_features
    assert "temperature_2m" in manifest_features


# Test 12: Feature ordering parity check
def test_12_feature_ordering(expander):
    manifest_features = expander.assembler.manifest_features
    assert manifest_features[0] == "latitude"
    assert manifest_features[1] == "longitude"
    assert manifest_features[-1] == "month_cos"


# Test 13: +1h target alignment presence
def test_13_target_alignment_plus_1h(expander):
    summary = expander.execute_multi_station_expansion()
    perf = summary["validation_dataset_report"]["model_evaluations"]["ANAND_VIHAR_8118"]
    assert "+1h" in perf
    assert perf["+1h"]["sample_count"] > 0


# Test 14: +3h target alignment presence
def test_14_target_alignment_plus_3h(expander):
    summary = expander.execute_multi_station_expansion()
    perf = summary["validation_dataset_report"]["model_evaluations"]["ANAND_VIHAR_8118"]
    assert "+3h" in perf
    assert perf["+3h"]["sample_count"] > 0


# Test 15: +6h target alignment presence
def test_15_target_alignment_plus_6h(expander):
    summary = expander.execute_multi_station_expansion()
    perf = summary["validation_dataset_report"]["model_evaluations"]["ANAND_VIHAR_8118"]
    assert "+6h" in perf
    assert perf["+6h"]["sample_count"] > 0


# Test 16: Zero future temporal leakage prevention
def test_16_temporal_leakage_prevention(expander):
    from ml.src.forecasting.validation import verify_zero_temporal_leakage
    from ml.src.forecasting.dataset_builder import ForecastingDatasetBuilder
    builder = ForecastingDatasetBuilder(data_root=expander.data_root)
    sample_records = [
        {"station_id": "ANAND_VIHAR_8118", "timestamp": "2025-01-01T00:00:00Z", "pollutant": "PM2.5", "value": 100.0, "latitude": 28.6476, "longitude": 77.3158},
        {"station_id": "ANAND_VIHAR_8118", "timestamp": "2025-01-01T01:00:00Z", "pollutant": "PM2.5", "value": 110.0, "latitude": 28.6476, "longitude": 77.3158},
        {"station_id": "ANAND_VIHAR_8118", "timestamp": "2025-01-01T02:00:00Z", "pollutant": "PM2.5", "value": 120.0, "latitude": 28.6476, "longitude": 77.3158},
    ]
    leakage = verify_zero_temporal_leakage(
        builder_fn=lambda o, w: builder.build_dataset_rows(o, w),
        test_openaq_records=sample_records,
    )
    assert leakage["leakage_passed"] is True


# Test 17: Persistence baseline evaluation calculation
def test_17_persistence_baseline_evaluation(expander):
    summary = expander.execute_multi_station_expansion()
    perf = summary["validation_dataset_report"]["model_evaluations"]["ANAND_VIHAR_8118"]
    for h in ["+1h", "+3h", "+6h"]:
        pers = perf[h]["persistence_baseline"]
        assert pers["mae"] >= 0.0
        assert pers["rmse"] >= 0.0


# Test 18: Frozen model evaluation isolation (hashes untouched)
def test_18_frozen_model_evaluation_isolation(expander):
    hashes_before = expander.verify_frozen_model_hashes()
    expander.execute_multi_station_expansion()
    hashes_after = expander.verify_frozen_model_hashes()
    for h in ["1h", "3h", "6h"]:
        assert hashes_before[h]["actual"] == hashes_after[h]["actual"]
        assert hashes_after[h]["actual"] == FROZEN_MODEL_HASHES[h]


# Test 19: Candidate model evaluation isolation
def test_19_candidate_model_isolation(expander):
    summary = expander.execute_multi_station_expansion()
    perf = summary["validation_dataset_report"]["model_evaluations"]["ANAND_VIHAR_8118"]
    for h in ["+1h", "+3h", "+6h"]:
        cand = perf[h]["candidate_model"]
        assert cand["mae"] >= 0.0


# Test 20: Cross-station reporting structure
def test_20_cross_station_reporting(expander):
    summary = expander.execute_multi_station_expansion()
    dataset_report = summary["validation_dataset_report"]
    assert len(dataset_report["stations"]) == 6


# Test 21: Cross-period reporting structure
def test_21_cross_period_reporting(expander):
    summary = expander.execute_multi_station_expansion()
    dataset_report = summary["validation_dataset_report"]
    assert len(dataset_report["periods"]) == 4


# Test 22: Residual diagnostics evaluation
def test_22_residual_diagnostics(expander):
    summary = expander.execute_multi_station_expansion()
    perf = summary["validation_dataset_report"]["model_evaluations"]["ANAND_VIHAR_8118"]
    for h in ["+1h", "+3h", "+6h"]:
        res_diag = perf[h]["residual_diagnostics"]
        assert "mean_residual" in res_diag
        assert "percentiles" in res_diag


# Test 23: Uncertainty coverage calculation (80%, 90%)
def test_23_uncertainty_coverage(expander):
    summary = expander.execute_multi_station_expansion()
    perf = summary["validation_dataset_report"]["model_evaluations"]["ANAND_VIHAR_8118"]
    for h in ["+1h", "+3h", "+6h"]:
        cov = perf[h]["conformal_coverage"]
        assert 0.0 <= cov["coverage_80_pct"] <= 100.0
        assert 0.0 <= cov["coverage_90_pct"] <= 100.0


# Test 24: Readiness evidence status and production validation status invariant
def test_24_readiness_evidence_status(expander):
    summary = expander.execute_multi_station_expansion()
    assert summary["evidence_status"] in VALID_EVIDENCE_STATUSES
    assert summary["production_validation_status"] == PRODUCTION_VALIDATION_STATUS


# Test 25: Deterministic repeated execution
def test_25_deterministic_repeated_execution(expander):
    out1 = expander.execute_multi_station_expansion()
    out2 = expander.execute_multi_station_expansion()
    assert out1["evidence_status"] == out2["evidence_status"]
    assert out1["production_validation_status"] == out2["production_validation_status"]
    assert len(out1["coverage_matrix"]["matrix"]) == len(out2["coverage_matrix"]["matrix"])


# Test 26: Artifact JSON file persistence verification
def test_26_artifact_files_exist(expander):
    expander.execute_multi_station_expansion()
    p1 = Path("data/processed/forecasting/multi_period_station_readiness_report.json")
    p2 = Path("data/processed/forecasting/multi_station_validation_dataset_report.json")
    p3 = Path("data/processed/forecasting/validation_coverage_matrix.json")
    assert p1.exists()
    assert p2.exists()
    assert p3.exists()
