"""
VayuDrishti — Controlled Live Pilot Readiness & Freshness Verification Tests (Phase 1E-J2E.4.9)

Focused test suite validating live readiness, freshness auditing, status precedence,
credential safety, and end-to-end pipeline composition.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ml.src.decision.live_pilot_orchestrator import (
    CANONICAL_STATION_ID,
    PRODUCTION_VALIDATION_STATUS,
    ControlledLivePilotOrchestrator,
    ControlledLivePilotResult,
    FreshnessMetadata,
)
from ml.src.forecasting.feature_assembler import ForecastFeatureAssembler
from ml.src.forecasting.live_air_quality import LiveAirQualityProvider
from ml.src.forecasting.live_weather import LiveWeatherProvider
from ml.src.forecasting.pipeline import ForecastPipelineService, LiveForecastResult


@pytest.fixture
def base_timestamps():
    """Returns fixed UTC prediction and observation timestamps for testing."""
    now_dt = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)
    pred_ts = now_dt.isoformat().replace("+00:00", "Z")
    return now_dt, pred_ts


@pytest.fixture
def fresh_aq_fixtures(base_timestamps):
    """Generates fresh AQ records within the 120-minute threshold."""
    now_dt, _ = base_timestamps
    records = []
    for h in range(30, -1, -1):
        t_dt = now_dt - timedelta(hours=h)
        records.append({
            "station_id": CANONICAL_STATION_ID,
            "location_id": 8118,
            "sensor_id": 8118,
            "timestamp": t_dt.isoformat().replace("+00:00", "Z"),
            "pollutant": "PM2.5",
            "value": 145.0 + (h % 5),
            "unit": "µg/m³",
            "source": "Fixture",
        })
    return records


@pytest.fixture
def stale_aq_fixtures(base_timestamps):
    """Generates stale AQ records older than the 120-minute threshold."""
    now_dt, _ = base_timestamps
    records = []
    for h in range(40, 2, -1):  # Latest observation is 3 hours (180 mins) old
        t_dt = now_dt - timedelta(hours=h)
        records.append({
            "station_id": CANONICAL_STATION_ID,
            "location_id": 8118,
            "sensor_id": 8118,
            "timestamp": t_dt.isoformat().replace("+00:00", "Z"),
            "pollutant": "PM2.5",
            "value": 150.0,
            "unit": "µg/m³",
            "source": "Fixture",
        })
    return records


@pytest.fixture
def fresh_weather_fixtures(base_timestamps):
    """Generates fresh weather records within the 60-minute threshold."""
    now_dt, _ = base_timestamps
    records = []
    for h in range(10, -1, -1):
        t_dt = now_dt - timedelta(hours=h)
        records.append({
            "timestamp": t_dt.isoformat().replace("+00:00", "Z"),
            "temperature_2m": 28.5,
            "relative_humidity_2m": 65.0,
            "wind_speed_10m": 3.5,
            "wind_direction_10m": 180.0,
            "surface_pressure": 1005.0,
            "boundary_layer_height": 450.0,
            "source": "Fixture",
        })
    return records


@pytest.fixture
def stale_weather_fixtures(base_timestamps):
    """Generates stale weather records older than the 60-minute threshold."""
    now_dt, _ = base_timestamps
    records = []
    for h in range(10, 1, -1):  # Latest observation is 2 hours (120 mins) old
        t_dt = now_dt - timedelta(hours=h)
        records.append({
            "timestamp": t_dt.isoformat().replace("+00:00", "Z"),
            "temperature_2m": 28.5,
            "relative_humidity_2m": 65.0,
            "wind_speed_10m": 3.5,
            "wind_direction_10m": 180.0,
            "surface_pressure": 1005.0,
            "boundary_layer_height": 450.0,
            "source": "Fixture",
        })
    return records


@pytest.fixture
def temp_dir():
    """Temporary directory for atomic cache & artifact testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# -----------------------------------------------------------------------------
# 1-8. TELEMETRY FRESHNESS AND STALENESS TESTS
# -----------------------------------------------------------------------------

def test_01_fresh_aq_evaluation(base_timestamps, fresh_aq_fixtures):
    """Test 1: Fresh AQ records within 120 minutes return READY status."""
    _, pred_ts = base_timestamps
    provider = LiveAirQualityProvider(mode="OFFLINE_TEST", max_aq_age_minutes=120.0)
    res = provider.fetch_recent_pm25_history(prediction_timestamp=pred_ts, fixture_records=fresh_aq_fixtures)
    assert res["status"] == "READY"
    assert res["source_age_minutes"] <= 120.0


def test_02_stale_aq_evaluation(base_timestamps, stale_aq_fixtures):
    """Test 2: AQ records older than 120 minutes return LIVE_AQ_STALE status."""
    _, pred_ts = base_timestamps
    provider = LiveAirQualityProvider(mode="OFFLINE_TEST", max_aq_age_minutes=120.0)
    res = provider.fetch_recent_pm25_history(prediction_timestamp=pred_ts, fixture_records=stale_aq_fixtures)
    assert res["status"] == "LIVE_AQ_STALE"
    assert res["source_age_minutes"] > 120.0


def test_03_missing_aq_evaluation(base_timestamps):
    """Test 3: Empty AQ telemetry returns LIVE_AQ_UNAVAILABLE status."""
    _, pred_ts = base_timestamps
    provider = LiveAirQualityProvider(mode="OFFLINE_TEST")
    res = provider.fetch_recent_pm25_history(prediction_timestamp=pred_ts, fixture_records=[])
    assert res["status"] == "LIVE_AQ_UNAVAILABLE"


def test_04_fresh_weather_evaluation(base_timestamps, fresh_weather_fixtures):
    """Test 4: Fresh weather records within 60 minutes return READY status."""
    _, pred_ts = base_timestamps
    provider = LiveWeatherProvider(mode="OFFLINE_TEST", max_weather_age_minutes=60.0)
    res = provider.fetch_recent_weather(prediction_timestamp=pred_ts, fixture_records=fresh_weather_fixtures)
    assert res["status"] == "READY"
    assert res["source_age_minutes"] <= 60.0


def test_05_stale_weather_evaluation(base_timestamps, stale_weather_fixtures):
    """Test 5: Weather records older than 60 minutes return WEATHER_STALE status."""
    _, pred_ts = base_timestamps
    provider = LiveWeatherProvider(mode="OFFLINE_TEST", max_weather_age_minutes=60.0)
    res = provider.fetch_recent_weather(prediction_timestamp=pred_ts, fixture_records=stale_weather_fixtures)
    assert res["status"] == "WEATHER_STALE"
    assert res["source_age_minutes"] > 60.0


def test_06_missing_weather_evaluation(base_timestamps):
    """Test 6: Empty weather telemetry returns WEATHER_STALE status."""
    _, pred_ts = base_timestamps
    provider = LiveWeatherProvider(mode="OFFLINE_TEST")
    res = provider.fetch_recent_weather(prediction_timestamp=pred_ts, fixture_records=[])
    assert res["status"] == "WEATHER_STALE"


def test_07_both_sources_fresh(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 7: Orchestrator returns overall READY when both AQ and weather are fresh."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert result.overall_status == "READY"
    assert result.freshness_metadata["overall_live_fresh"] is True


def test_08_one_source_stale(base_timestamps, fresh_aq_fixtures, stale_weather_fixtures, temp_dir):
    """Test 8: Orchestrator returns PARTIAL when weather is stale even if AQ is fresh."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=stale_weather_fixtures,
    )
    assert result.overall_status in ("PARTIAL", "WEATHER_STALE")
    assert result.freshness_metadata["overall_live_fresh"] is False


# -----------------------------------------------------------------------------
# 9-15. QUALITY GATES, PROVENANCE, SCOPE & LEAKAGE TESTS
# -----------------------------------------------------------------------------

def test_09_deterministic_quality_gate_precedence(base_timestamps, temp_dir):
    """Test 9: Verifies precedence BLOCKED > PARTIAL > READY on missing input."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=[],
        weather_fixtures=[],
    )
    assert result.overall_status == "BLOCKED"


def test_10_live_mode_metadata(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 10: Verifies metadata correctly records CONTROLLED_LIVE mode."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="CONTROLLED_LIVE",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert result.data_mode == "CONTROLLED_LIVE"


def test_11_historical_live_distinction(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 11: Verifies offline and live provenance sources are distinctly labeled."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    res_offline = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert res_offline.cache_provenance["air_quality_source"] == "OpenAQ_v3_Offline"

    res_live = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="CONTROLLED_LIVE",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert res_live.cache_provenance["air_quality_source"] == "OpenAQ_v3_Live"


def test_12_station_scope_enforcement(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 12: Verifies unsupported station IDs are BLOCKED."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        station_id="UNSUPPORTED_STATION_9999",
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert result.overall_status == "BLOCKED"


def test_13_feature_assembler_invocation(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures):
    """Test 13: Verifies canonical feature assembler produces READY feature vector."""
    _, pred_ts = base_timestamps
    assembler = ForecastFeatureAssembler()
    vector = assembler.assemble_features(
        station_id=CANONICAL_STATION_ID,
        prediction_timestamp=pred_ts,
        air_quality_records=fresh_aq_fixtures,
        weather_records=fresh_weather_fixtures,
    )
    assert vector.assembly_status == "READY"
    assert len(vector.features) == 27


def test_14_no_feature_order_drift(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures):
    """Test 14: Verifies assembled feature keys match model manifest feature list order exactly."""
    _, pred_ts = base_timestamps
    assembler = ForecastFeatureAssembler()
    vector = assembler.assemble_features(
        station_id=CANONICAL_STATION_ID,
        prediction_timestamp=pred_ts,
        air_quality_records=fresh_aq_fixtures,
        weather_records=fresh_weather_fixtures,
    )
    manifest_features = assembler.manifest_features
    feature_keys = list(vector.features.keys())
    assert feature_keys == manifest_features


def test_15_temporal_leakage_guard(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures):
    """Test 15: Verifies observations with timestamp > prediction_timestamp are strictly excluded."""
    now_dt, pred_ts = base_timestamps
    future_record = {
        "station_id": CANONICAL_STATION_ID,
        "location_id": 8118,
        "sensor_id": 8118,
        "timestamp": (now_dt + timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
        "pollutant": "PM2.5",
        "value": 999.0,  # Poison value
        "unit": "µg/m³",
    }
    assembler = ForecastFeatureAssembler()
    vector = assembler.assemble_features(
        station_id=CANONICAL_STATION_ID,
        prediction_timestamp=pred_ts,
        air_quality_records=fresh_aq_fixtures + [future_record],
        weather_records=fresh_weather_fixtures,
    )
    assert 999.0 not in vector.features.values()


# -----------------------------------------------------------------------------
# 16-22. PIPELINE COMPOSITION, VALIDATION & CREDENTIAL SAFETY TESTS
# -----------------------------------------------------------------------------

def test_16_forecast_composition(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 16: Verifies +1h, +3h, +6h forecast horizons are populated in pilot result."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    horizons = result.forecast_result.get("horizons", {})
    assert "+1h" in horizons
    assert "+3h" in horizons
    assert "+6h" in horizons


def test_17_risk_composition(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 17: Verifies risk assessment outputs (score, level) are composed in result."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert "risk_score" in result.risk_result
    assert "risk_level" in result.risk_result


def test_18_action_composition(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 18: Verifies authority action recommendations are composed in result."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert "recommendations" in result.action_result
    assert result.action_result["status"] in ("READY", "PARTIAL")


def test_19_decision_composition(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 19: Verifies end-to-end Decision Intelligence result is generated."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="OFFLINE_TEST",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert "decision_result_id" in result.decision_result
    assert result.decision_result["requires_human_review"] is True


def test_20_production_validation_status_invariant(base_timestamps, fresh_aq_fixtures, fresh_weather_fixtures, temp_dir):
    """Test 20: Verifies production_validation_status is permanently NOT_PRODUCTION_VALIDATED."""
    _, pred_ts = base_timestamps
    orchestrator = ControlledLivePilotOrchestrator(
        artifact_path=temp_dir / "pilot.json",
        live_cache_dir=temp_dir / "cache",
    )
    result = orchestrator.evaluate_pilot(
        prediction_timestamp=pred_ts,
        data_mode="CONTROLLED_LIVE",
        aq_fixtures=fresh_aq_fixtures,
        weather_fixtures=fresh_weather_fixtures,
    )
    assert result.production_validation_status == PRODUCTION_VALIDATION_STATUS
    assert result.production_validation_status == "NOT_PRODUCTION_VALIDATED"


def test_21_missing_api_key_behavior(base_timestamps, temp_dir):
    """Test 21: Verifies missing OPENAQ_API_KEY causes BLOCKED status with clean diagnostic reason."""
    _, pred_ts = base_timestamps
    with patch.dict(os.environ, {}, clear=True):
        orchestrator = ControlledLivePilotOrchestrator(
            artifact_path=temp_dir / "pilot.json",
            live_cache_dir=temp_dir / "cache",
        )
        result = orchestrator.evaluate_pilot(
            prediction_timestamp=pred_ts,
            data_mode="CONTROLLED_LIVE",
            aq_fixtures=None,
            weather_fixtures=None,
        )
        assert result.overall_status == "BLOCKED"
        assert any("OPENAQ_API_KEY" in r for r in result.status_reasons)


def test_22_no_credential_leakage(base_timestamps, temp_dir):
    """Test 22: Verifies output artifact contains zero secret key disclosures."""
    _, pred_ts = base_timestamps
    secret_key = "SECRET_OPENAQ_KEY_DO_NOT_LEAK"
    with patch.dict(os.environ, {"OPENAQ_API_KEY": secret_key}):
        artifact_file = temp_dir / "pilot.json"
        orchestrator = ControlledLivePilotOrchestrator(
            artifact_path=artifact_file,
            live_cache_dir=temp_dir / "cache",
        )
        result = orchestrator.evaluate_pilot(
            prediction_timestamp=pred_ts,
            data_mode="CONTROLLED_LIVE",
            aq_fixtures=None,
            weather_fixtures=None,
        )
        raw_text = artifact_file.read_text(encoding="utf-8")
        assert secret_key not in raw_text
        assert secret_key not in str(result.to_dict())
