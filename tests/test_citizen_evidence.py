import io
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.api.v1.schemas.evidence import EvidenceManifest
from backend.ingestion.citizen_evidence_storage import (
    CitizenEvidenceStorage,
    generate_evidence_id,
    validate_safe_id,
)
from backend.ingestion.citizen_evidence_validator import CitizenEvidenceValidator
from backend.ingestion.exceptions import (
    ConsentRequiredError,
    EmptyEvidenceError,
    FileSizeLimitExceededError,
    LocationValidationError,
    UnsupportedMediaFormatError,
)

client = TestClient(app)


def test_evidence_id_generation_and_validation():
    """Verify format and cryptographic uniqueness of evidence IDs."""
    eid1 = generate_evidence_id()
    eid2 = generate_evidence_id()
    assert eid1.startswith("ev_")
    assert eid2.startswith("ev_")
    assert eid1 != eid2
    assert validate_safe_id(eid1) is True
    assert validate_safe_id(eid2) is True
    assert validate_safe_id("ev_invalid") is False
    assert validate_safe_id("../ev_123") is False


def test_validator_consent_and_modality():
    """Verify consent requirement and modality check."""
    # Missing consent
    with pytest.raises(ConsentRequiredError):
        CitizenEvidenceValidator.validate_consent(False)

    CitizenEvidenceValidator.validate_consent(True)  # No exception

    # Missing all modalities
    with pytest.raises(EmptyEvidenceError):
        CitizenEvidenceValidator.validate_modality_presence(False, False, False)

    # Valid with at least one modality
    CitizenEvidenceValidator.validate_modality_presence(True, False, False)
    CitizenEvidenceValidator.validate_modality_presence(False, True, False)
    CitizenEvidenceValidator.validate_modality_presence(False, False, True)


def test_validator_location_rules():
    """Verify WGS84 range validation and accuracy boundaries."""
    # Valid coordinates
    CitizenEvidenceValidator.validate_location(28.628, 77.114, 15.0)

    # Latitude out of bounds
    with pytest.raises(LocationValidationError):
        CitizenEvidenceValidator.validate_location(95.0, 77.114)

    # Longitude out of bounds
    with pytest.raises(LocationValidationError):
        CitizenEvidenceValidator.validate_location(28.628, -185.0)

    # Partial coordinates (latitude without longitude)
    with pytest.raises(LocationValidationError):
        CitizenEvidenceValidator.validate_location(28.628, None)

    # Negative accuracy radius
    with pytest.raises(LocationValidationError):
        CitizenEvidenceValidator.validate_location(28.628, 77.114, -5.0)


def test_validator_media_security_and_limits():
    """Verify rejection of oversized files and malicious extensions."""
    # Allowed JPEG
    CitizenEvidenceValidator.validate_photo("image/jpeg", 5000, "sample.jpg")

    # Prohibited executable
    with pytest.raises(UnsupportedMediaFormatError):
        CitizenEvidenceValidator.validate_photo("application/x-msdownload", 5000, "malware.exe")

    # Disallowed photo MIME type (e.g. text/html)
    with pytest.raises(UnsupportedMediaFormatError):
        CitizenEvidenceValidator.validate_photo("text/html", 500, "page.html")

    # Oversized photo (>10 MB)
    with pytest.raises(FileSizeLimitExceededError):
        CitizenEvidenceValidator.validate_photo("image/jpeg", 11 * 1024 * 1024, "huge.jpg")


def test_submit_valid_photo_only(tmp_path):
    """Verify successful intake with photo only."""
    photo_content = b"fake-jpeg-image-bytes"
    response = client.post(
        "/api/v1/evidence",
        data={
            "consent": "true",
            "latitude": "28.632",
            "longitude": "77.118",
            "accuracy": "10.5",
            "location_source": "gps",
        },
        files={
            "photo": ("test_smoke.jpg", io.BytesIO(photo_content), "image/jpeg"),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "received"
    assert data["evidence_id"].startswith("ev_")
    assert data["media_count"] == 1
    assert "photo" in data["media_types"]
    assert data["location"]["latitude"] == 28.632
    assert data["location"]["longitude"] == 77.118

    # Verify manifest was persisted and can be fetched
    eid = data["evidence_id"]
    get_res = client.get(f"/api/v1/evidence/{eid}")
    assert get_res.status_code == 200
    manifest = get_res.json()
    assert manifest["evidence_id"] == eid
    assert manifest["status"] == "RECEIVED"
    assert manifest["consent_given"] is True
    assert len(manifest["media"]) == 1
    assert manifest["media"][0]["media_type"] == "photo"


def test_submit_valid_photo_and_text():
    """Verify intake with photo and text description."""
    photo_content = b"fake-png-image-bytes"
    response = client.post(
        "/api/v1/evidence",
        data={
            "consent": "true",
            "description": "Black smoke billows near Mayapuri industrial sector.",
            "category": "industrial_smoke",
            "latitude": "28.640",
            "longitude": "77.125",
        },
        files={
            "photo": ("emission.png", io.BytesIO(photo_content), "image/png"),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["evidence_id"].startswith("ev_")

    get_res = client.get(f"/api/v1/evidence/{data['evidence_id']}")
    assert get_res.status_code == 200
    manifest = get_res.json()
    assert manifest["description"] == "Black smoke billows near Mayapuri industrial sector."
    assert manifest["category"] == "industrial_smoke"


def test_submit_valid_voice_and_text():
    """Verify intake with optional voice recording and description."""
    voice_content = b"fake-webm-audio-bytes"
    response = client.post(
        "/api/v1/evidence",
        data={
            "consent": "true",
            "description": "Garbage burning near construction site.",
            "category": "biomass_burning",
        },
        files={
            "voice": ("voice_note.webm", io.BytesIO(voice_content), "audio/webm"),
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["media_count"] == 1
    assert "voice" in data["media_types"]


def test_submit_text_only():
    """Verify intake with text remark only when citizen cannot take photo."""
    response = client.post(
        "/api/v1/evidence",
        data={
            "consent": "true",
            "description": "Strong chemical odor detected along freight corridor.",
            "category": "industrial_smoke",
            "latitude": "28.650",
            "longitude": "77.130",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["media_count"] == 0


def test_rejection_missing_consent():
    """Verify HTTP 400 CONSENT_REQUIRED when consent is false or missing."""
    response = client.post(
        "/api/v1/evidence",
        data={
            "consent": "false",
            "description": "No consent test",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "CONSENT_REQUIRED"


def test_rejection_empty_evidence():
    """Verify HTTP 400 EMPTY_EVIDENCE when no photo, voice, or text is supplied."""
    response = client.post(
        "/api/v1/evidence",
        data={
            "consent": "true",
            "latitude": "28.650",
            "longitude": "77.130",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "EMPTY_EVIDENCE"


def test_rejection_invalid_coordinates():
    """Verify HTTP 400 INVALID_COORDINATES on illegal GPS latitude."""
    response = client.post(
        "/api/v1/evidence",
        data={
            "consent": "true",
            "description": "Invalid coord test",
            "latitude": "99.999",
            "longitude": "77.130",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_COORDINATES"


def test_rejection_invalid_accuracy():
    """Verify HTTP 400 INVALID_ACCURACY on negative accuracy radius."""
    response = client.post(
        "/api/v1/evidence",
        data={
            "consent": "true",
            "description": "Negative accuracy test",
            "latitude": "28.650",
            "longitude": "77.130",
            "accuracy": "-10.0",
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_ACCURACY"


def test_rejection_unsupported_media_type():
    """Verify HTTP 400 UNSUPPORTED_MEDIA_TYPE when uploading executable or PDF."""
    response = client.post(
        "/api/v1/evidence",
        data={"consent": "true"},
        files={
            "photo": ("script.py", io.BytesIO(b"print('hack')"), "text/x-python"),
        },
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_rejection_path_traversal_filename():
    """Verify that path traversal in client filename is stripped and stored safely."""
    photo_content = b"safe-jpeg-content"
    response = client.post(
        "/api/v1/evidence",
        data={"consent": "true"},
        files={
            "photo": ("../../etc/passwd.jpg", io.BytesIO(photo_content), "image/jpeg"),
        },
    )
    assert response.status_code == 201
    data = response.json()
    # Stored manifest must have server-generated filename without path traversal
    get_res = client.get(f"/api/v1/evidence/{data['evidence_id']}")
    assert get_res.status_code == 200
    manifest = get_res.json()
    assert manifest["media"][0]["filename"] == "photo_01.jpg"


def test_get_nonexistent_evidence_returns_404():
    """Verify HTTP 404 for unknown evidence ID."""
    fake_id = "ev_00000000000000000000000000000000"
    response = client.get(f"/api/v1/evidence/{fake_id}")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "EVIDENCE_NOT_FOUND"


def test_get_malformed_evidence_id_returns_400():
    """Verify HTTP 400 for unsafe or malformed evidence ID."""
    response = client.get("/api/v1/evidence/../../etc/passwd")
    assert response.status_code == 400 or response.status_code == 404
