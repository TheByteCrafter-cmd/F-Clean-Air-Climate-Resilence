import json
import logging
import re
import uuid
from pathlib import Path
from typing import Optional

from backend.api.v1.schemas.evidence import EvidenceManifest, MediaItem
from backend.ingestion.exceptions import EvidenceStorageError, UnsupportedMediaFormatError

logger = logging.getLogger(__name__)

DEFAULT_RAW_EVIDENCE_DIR = Path("data/raw/citizen_evidence")
DEFAULT_PROCESSED_MANIFEST_DIR = Path("data/processed/citizen_evidence/manifests")

# MIME type to safe standard extension mapping
MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/webm": ".webm",
    "audio/wav": ".wav",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/mpeg": ".mp3",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".aac",
}


def generate_evidence_id() -> str:
    """Generates a cryptographically secure, unique evidence identifier: ev_<uuid_hex>."""
    return f"ev_{uuid.uuid4().hex}"


def validate_safe_id(evidence_id: str) -> bool:
    """Validates evidence ID format to prevent path traversal or injection."""
    return bool(re.match(r"^ev_[a-f0-9]{32}$", evidence_id))


class CitizenEvidenceStorage:
    """Filesystem-backed secure local evidence storage manager.
    
    Adheres strictly to the local storage contract:
      - Media stored under `data/raw/citizen_evidence/<evidence_id>/`
      - Manifests stored under `data/processed/citizen_evidence/manifests/<evidence_id>.json`
      - Zero reliance on external databases or cloud storage.
    """

    def __init__(
        self,
        raw_dir: Path = DEFAULT_RAW_EVIDENCE_DIR,
        manifest_dir: Path = DEFAULT_PROCESSED_MANIFEST_DIR,
    ):
        self.raw_dir = Path(raw_dir)
        self.manifest_dir = Path(manifest_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_dir.mkdir(parents=True, exist_ok=True)

    def save_media_file(
        self,
        evidence_id: str,
        media_type: str,
        content: bytes,
        mime_type: str,
        client_filename: Optional[str] = None,
        sequence_index: int = 1,
    ) -> MediaItem:
        """Saves uploaded media bytes with a server-generated safe filename.
        
        Args:
            evidence_id: Canonical evidence ID.
            media_type: 'photo' or 'voice'.
            content: Raw byte contents of the uploaded file.
            mime_type: Validated MIME type.
            client_filename: Original client filename (used only for extension hints, never raw path).
            sequence_index: Index number if multiple items are attached.
            
        Returns:
            Populated MediaItem metadata object.
            
        Raises:
            EvidenceStorageError: If directory creation or file writing fails.
        """
        if not validate_safe_id(evidence_id):
            raise EvidenceStorageError(f"Invalid or unsafe evidence ID: '{evidence_id}'")

        # Determine safe file extension
        clean_mime = (mime_type or "").split(";")[0].strip().lower()
        ext = MIME_TO_EXT.get(clean_mime)
        if not ext and client_filename:
            raw_ext = Path(client_filename).suffix.lower()
            if raw_ext in (".jpg", ".jpeg", ".png", ".webp", ".webm", ".wav", ".ogg", ".mp4", ".m4a"):
                ext = raw_ext

        if not ext:
            ext = ".bin" if media_type != "photo" else ".jpg"

        safe_filename = f"{media_type}_{sequence_index:02d}{ext}"
        item_dir = self.raw_dir / evidence_id
        try:
            item_dir.mkdir(parents=True, exist_ok=True)
            target_file = item_dir / safe_filename

            # Resolve to prevent any path traversal attempt
            resolved_target = target_file.resolve()
            resolved_parent = item_dir.resolve()
            if not str(resolved_target).startswith(str(resolved_parent)):
                raise EvidenceStorageError(f"Path traversal detected in filename: '{safe_filename}'")

            with open(target_file, "wb") as f:
                f.write(content)

            logger.info(f"Saved {media_type} evidence ({len(content)} bytes) to {target_file}")

            media_id = f"med_{uuid.uuid4().hex[:12]}"
            return MediaItem(
                media_id=media_id,
                media_type=media_type,
                mime_type=clean_mime,
                file_size_bytes=len(content),
                filename=safe_filename,
            )

        except EvidenceStorageError:
            raise
        except Exception as exc:
            logger.error(f"Failed to write evidence media file: {exc}")
            raise EvidenceStorageError(f"Filesystem error saving evidence media: {exc}")

    def save_manifest(self, manifest: EvidenceManifest) -> Path:
        """Saves the canonical evidence manifest JSON.
        
        Args:
            manifest: Validated EvidenceManifest instance.
            
        Returns:
            Path to the saved manifest file.
            
        Raises:
            EvidenceStorageError: If writing manifest fails.
        """
        evidence_id = manifest.evidence_id
        if not validate_safe_id(evidence_id):
            raise EvidenceStorageError(f"Invalid or unsafe evidence ID in manifest: '{evidence_id}'")

        target_file = self.manifest_dir / f"{evidence_id}.json"
        try:
            resolved_target = target_file.resolve()
            resolved_parent = self.manifest_dir.resolve()
            if not str(resolved_target).startswith(str(resolved_parent)):
                raise EvidenceStorageError(f"Path traversal detected in manifest target: '{evidence_id}'")

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(manifest.model_dump_json(indent=2))

            logger.info(f"Persisted evidence manifest to {target_file}")
            return target_file

        except EvidenceStorageError:
            raise
        except Exception as exc:
            logger.error(f"Failed to write evidence manifest: {exc}")
            raise EvidenceStorageError(f"Filesystem error saving evidence manifest: {exc}")

    def get_manifest(self, evidence_id: str) -> Optional[EvidenceManifest]:
        """Retrieves a stored manifest by its evidence ID.
        
        Args:
            evidence_id: Canonical evidence ID.
            
        Returns:
            EvidenceManifest instance, or None if not found.
        """
        if not validate_safe_id(evidence_id):
            return None

        target_file = self.manifest_dir / f"{evidence_id}.json"
        if not target_file.exists():
            return None

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return EvidenceManifest(**data)
        except Exception as exc:
            logger.error(f"Failed to parse stored manifest for '{evidence_id}': {exc}")
            return None
