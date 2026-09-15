"""
VayuDrishti — Phase 1E-G Gemini Evidence Analysis Unit & Integration Test Suite

Verifies Gemini multimodal evidence analyzer, schema validation, exception mapping,
persistence, idempotency, and API endpoints using mocked SDK responses.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.api.v1.schemas.evidence import (
    EvidenceAIAnalysis,
    EvidenceManifest,
    EvidenceLocation,
    MediaItem,
    ProbableCategoryItem,
)
from backend.ingestion.citizen_evidence_storage import CitizenEvidenceStorage
from backend.ingestion.exceptions import (
    GeminiCredentialError,
    GeminiAuthenticationError,
    GeminiRateLimitError,
    GeminiResponseValidationError,
    GeminiTimeoutError,
)
from backend.ingestion.gemini_evidence_analyzer import (
    GeminiEvidenceAnalyzer,
    SYSTEM_ANALYSIS_PROMPT,
)

client = TestClient(app)


@pytest.fixture
def temp_storage():
    """Create a temporary CitizenEvidenceStorage instance for testing."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage = CitizenEvidenceStorage(data_root=Path(tmp_dir))
        yield storage


@pytest.fixture
def sample_evidence(temp_storage):
    """Create and persist a valid sample evidence manifest and dummy photo file."""
    evidence_id = "ev_11223344556677889900aabbccddeeff"
    raw_dir = temp_storage.get_media_dir(evidence_id)
    photo_file = raw_dir / "photo_01.jpg"

    # Create dummy 100x100 image file
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="gray")
    img.save(photo_file)

    manifest = EvidenceManifest(
        evidence_id=evidence_id,
        submitted_at="2026-09-16T00:00:00Z",
        location=EvidenceLocation(latitude=28.6320, longitude=77.1180, source="gps"),
        media=[
            MediaItem(
                media_id="med_01",
                media_type="photo",
                mime_type="image/jpeg",
                file_size_bytes=1024,
                filename="photo_01.jpg",
            )
        ],
        description="Heavy black smoke rising near factory chimney.",
        category="industrial_smoke",
        consent_given=True,
        status="RECEIVED",
        source="citizen_web",
        schema_version="1.0",
    )
    temp_storage.save_manifest(manifest)
    return evidence_id, temp_storage


def test_missing_api_key_raises_credential_error(temp_storage, monkeypatch):
    """Ensure missing GEMINI_API_KEY raises GeminiCredentialError."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    analyzer = GeminiEvidenceAnalyzer(data_root=temp_storage.root_dir)

    with pytest.raises(GeminiCredentialError) as exc_info:
        analyzer.get_api_key()

    assert "missing, unconfigured, or set to default" in str(exc_info.value)


def test_placeholder_api_key_raises_credential_error(temp_storage, monkeypatch):
    """Ensure default placeholder API key raises GeminiCredentialError."""
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    analyzer = GeminiEvidenceAnalyzer(data_root=temp_storage.root_dir)

    with pytest.raises(GeminiCredentialError):
        analyzer.get_api_key()


def test_valid_mocked_analysis_execution(sample_evidence):
    """Test successful multimodal analysis with mocked SDK output."""
    evidence_id, temp_storage = sample_evidence
    analyzer = GeminiEvidenceAnalyzer(data_root=temp_storage.root_dir)

    # Mock client with valid JSON output
    mock_sdk_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = json.dumps({
        "relevance": "relevant",
        "observed_phenomena": ["visible_dark_smoke_plume"],
        "probable_categories": [{"category": "industrial_smoke", "confidence_level": "high"}],
        "visual_indicators": ["dark plume"],
        "evidence_quality": "clear",
        "audio_status": "AUDIO_ANALYSIS_DEFERRED",
        "uncertainty": ["None"],
        "explanation": "Visible plume observed.",
        "recommended_followup": ["Wider angle photo."]
    })
    mock_sdk_client.models.generate_content.return_value = mock_res

    analysis = analyzer.analyze_evidence(evidence_id, client_mock=mock_sdk_client)

    assert analysis.evidence_id == evidence_id
    assert analysis.relevance == "relevant"
    assert len(analysis.probable_categories) == 1
    assert analysis.probable_categories[0].confidence_level == "high"
    assert analysis.audio_status == "AUDIO_ANALYSIS_DEFERRED"

    # Verify manifest updated
    updated_manifest = temp_storage.get_manifest(evidence_id)
    assert updated_manifest.status == "AI_ANALYZED"

    # Verify analysis persisted
    persisted = analyzer.get_existing_analysis(evidence_id)
    assert persisted is not None
    assert persisted.analysis_id == analysis.analysis_id


def test_idempotency_returns_cached_analysis(sample_evidence):
    """Test that analyzing twice without force_reanalyze returns the existing analysis artifact."""
    evidence_id, temp_storage = sample_evidence
    analyzer = GeminiEvidenceAnalyzer(data_root=temp_storage.root_dir)

    mock_sdk_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = json.dumps({
        "relevance": "relevant",
        "observed_phenomena": ["visible_dark_smoke_plume"],
        "probable_categories": [{"category": "industrial_smoke", "confidence_level": "high"}],
        "visual_indicators": ["dark plume"],
        "evidence_quality": "clear",
        "audio_status": "AUDIO_ANALYSIS_DEFERRED",
        "uncertainty": ["None"],
        "explanation": "Visible plume observed.",
        "recommended_followup": []
    })
    mock_sdk_client.models.generate_content.return_value = mock_res

    analysis_1 = analyzer.analyze_evidence(evidence_id, client_mock=mock_sdk_client)
    analysis_2 = analyzer.analyze_evidence(evidence_id, client_mock=mock_sdk_client)

    assert analysis_1.analysis_id == analysis_2.analysis_id
    assert analysis_1.analyzed_at == analysis_2.analyzed_at


def test_malformed_model_json_raises_validation_error(sample_evidence, monkeypatch):
    """Test that non-JSON output from model raises GeminiResponseValidationError."""
    evidence_id, temp_storage = sample_evidence
    monkeypatch.setenv("GEMINI_API_KEY", "valid_test_key_123")
    analyzer = GeminiEvidenceAnalyzer(data_root=temp_storage.root_dir)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "NOT_JSON_CONTENT"
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        with pytest.raises(GeminiResponseValidationError):
            analyzer._execute_live_gemini_analysis(
                evidence_id=evidence_id,
                model_name="gemini-2.5-flash",
                api_key="valid_test_key_123",
                photo_file=temp_storage.get_media_dir(evidence_id) / "photo_01.jpg",
                user_prompt="test",
                audio_status="AUDIO_ANALYSIS_DEFERRED",
            )


def test_authentication_error_mapping(sample_evidence, monkeypatch):
    """Test HTTP 401/403 mapping to GeminiAuthenticationError."""
    evidence_id, temp_storage = sample_evidence
    monkeypatch.setenv("GEMINI_API_KEY", "invalid_key")
    analyzer = GeminiEvidenceAnalyzer(data_root=temp_storage.root_dir)

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("401 Invalid API Key")

    with patch("google.genai.Client", return_value=mock_client):
        with pytest.raises(GeminiAuthenticationError):
            analyzer._execute_live_gemini_analysis(
                evidence_id=evidence_id,
                model_name="gemini-2.5-flash",
                api_key="invalid_key",
                photo_file=None,
                user_prompt="test",
                audio_status="NO_AUDIO",
            )


def test_rate_limit_retry_and_error_mapping(sample_evidence, monkeypatch):
    """Test HTTP 429 rate limit retries and raises GeminiRateLimitError."""
    evidence_id, temp_storage = sample_evidence
    monkeypatch.setenv("GEMINI_API_KEY", "valid_key")
    analyzer = GeminiEvidenceAnalyzer(data_root=temp_storage.root_dir)

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("429 Resource Exhausted")

    with patch("google.genai.Client", return_value=mock_client):
        with pytest.raises(GeminiRateLimitError):
            analyzer._execute_live_gemini_analysis(
                evidence_id=evidence_id,
                model_name="gemini-2.5-flash",
                api_key="valid_key",
                photo_file=None,
                user_prompt="test",
                audio_status="NO_AUDIO",
            )


def test_api_analyze_endpoint_success(sample_evidence, monkeypatch):
    """Test POST /api/v1/evidence/{evidence_id}/analyze returns 200 with EvidenceAIAnalysis."""
    evidence_id, temp_storage = sample_evidence
    monkeypatch.setenv("GEMINI_API_KEY", "test_key")

    mock_analysis = EvidenceAIAnalysis(
        analysis_id="an_12345678901234567890123456789012",
        evidence_id=evidence_id,
        model_name="gemini-2.5-flash",
        model_version="2026-09",
        analyzed_at="2026-09-16T00:00:00Z",
        relevance="relevant",
        observed_phenomena=["dark plume"],
        probable_categories=[
            ProbableCategoryItem(category="industrial_smoke", confidence_level="high")
        ],
        visual_indicators=["dark plume"],
        evidence_quality="clear",
        audio_status="AUDIO_ANALYSIS_DEFERRED",
        uncertainty=["None"],
        explanation="Clear industrial smoke plume detected.",
        recommended_followup=["Check nearby CAAQMS sensor readings."],
    )

    with patch("backend.api.v1.endpoints.evidence.storage", temp_storage):
        with patch.object(GeminiEvidenceAnalyzer, "analyze_evidence", return_value=mock_analysis):
            res = client.post(f"/api/v1/evidence/{evidence_id}/analyze")
            assert res.status_code == 200
            data = res.json()
            assert data["evidence_id"] == evidence_id
            assert data["relevance"] == "relevant"
            assert data["probable_categories"][0]["confidence_level"] == "high"


def test_api_analyze_nonexistent_evidence_returns_404():
    """Test POST /api/v1/evidence/{nonexistent_id}/analyze returns HTTP 404."""
    fake_id = "ev_00000000000000000000000000000000"
    res = client.post(f"/api/v1/evidence/{fake_id}/analyze")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "EVIDENCE_NOT_FOUND"


def test_api_analyze_unconfigured_credentials_returns_503(sample_evidence, monkeypatch):
    """Test POST /api/v1/evidence/{evidence_id}/analyze returns 503 when API key is unconfigured."""
    evidence_id, temp_storage = sample_evidence
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with patch("backend.api.v1.endpoints.evidence.storage", temp_storage):
        with patch.object(GeminiEvidenceAnalyzer, "__init__", return_value=None):
            with patch.object(GeminiEvidenceAnalyzer, "analyze_evidence", side_effect=GeminiCredentialError("Unconfigured")):
                res = client.post(f"/api/v1/evidence/{evidence_id}/analyze")
                assert res.status_code == 503
                assert res.json()["error"]["code"] == "GEMINI_CREDENTIAL_UNCONFIGURED"


def test_api_get_analysis_endpoint(sample_evidence, monkeypatch):
    """Test GET /api/v1/evidence/{evidence_id}/analysis retrieves stored analysis artifact."""
    evidence_id, temp_storage = sample_evidence
    analyzer = GeminiEvidenceAnalyzer(data_root=temp_storage.root_dir)
    
    mock_sdk_client = MagicMock()
    mock_res = MagicMock()
    mock_res.text = json.dumps({
        "relevance": "relevant",
        "observed_phenomena": ["visible_dark_smoke_plume"],
        "probable_categories": [{"category": "industrial_smoke", "confidence_level": "high"}],
        "visual_indicators": ["dark plume"],
        "evidence_quality": "clear",
        "audio_status": "AUDIO_ANALYSIS_DEFERRED",
        "uncertainty": ["None"],
        "explanation": "Visible plume observed.",
        "recommended_followup": []
    })
    mock_sdk_client.models.generate_content.return_value = mock_res
    analysis = analyzer.analyze_evidence(evidence_id, client_mock=mock_sdk_client)

    with patch("backend.api.v1.endpoints.evidence.storage", temp_storage):
        with patch.object(GeminiEvidenceAnalyzer, "get_existing_analysis", return_value=analysis):
            res = client.get(f"/api/v1/evidence/{evidence_id}/analysis")
            assert res.status_code == 200
            data = res.json()
            assert data["evidence_id"] == evidence_id
            assert data["analysis_id"] == analysis.analysis_id


def test_live_gemini_verification_conditional():
    """
    Conditional Live Gemini Verification Test.
    Executes a single live request if GEMINI_API_KEY is configured.
    Otherwise skips cleanly as instructed.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        pytest.skip("Live Gemini verification skipped because GEMINI_API_KEY is not configured.")

    analyzer = GeminiEvidenceAnalyzer()
    model_name = analyzer.get_model_name()

    try:
        from google import genai
        gclient = genai.Client(api_key=api_key)
        res = gclient.models.generate_content(
            model=model_name,
            contents="Say 'VayuDrishti Live Verification Successful' in plain text.",
        )
        assert res is not None and len(res.text) > 0
    except Exception as e:
        pytest.fail(f"Live Gemini API verification failed: {e}")
