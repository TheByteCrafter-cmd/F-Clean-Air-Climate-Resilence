"""
VayuDrishti — OpenAQ Open Data on AWS Historical Archive Client (Phase 1E-J2A.3)

Provides deterministic, anonymous HTTP access to the official OpenAQ S3 historical archive
(s3://openaq-data-archive/ -> https://openaq-data-archive.s3.amazonaws.com/).

Follows the official S3 object partitioning structure:
records/csv.gz/locationid={LOCATION_ID}/year={YEAR}/month={MONTH}/location-{LOCATION_ID}-{YYYYMMDD}.csv.gz
"""

import csv
import gzip
import hashlib
import io
import logging
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.ingestion.exceptions import OpenAQError

logger = logging.getLogger(__name__)

S3_BASE_URL = "https://openaq-data-archive.s3.amazonaws.com"
EXPECTED_COLUMNS = [
    "location_id",
    "sensors_id",
    "location",
    "datetime",
    "lat",
    "lon",
    "parameter",
    "units",
    "value",
]


class OpenAQAWSArchiveClient:
    """Client for fetching and parsing daily CSV.gz archives from OpenAQ S3 data archive."""

    def __init__(self, base_url: str = S3_BASE_URL, timeout: int = 15):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _parse_date(dt_input: Union[str, date, datetime]) -> date:
        """Helper to convert date input to datetime.date object."""
        if isinstance(dt_input, datetime):
            return dt_input.date()
        elif isinstance(dt_input, date):
            return dt_input
        elif isinstance(dt_input, str):
            # Try ISO formats
            clean_str = dt_input.split("T")[0]
            return datetime.strptime(clean_str, "%Y-%m-%d").date()
        else:
            raise ValueError(f"Unsupported date input type: {type(dt_input)}")

    def generate_object_key(self, location_id: int, target_date: Union[str, date, datetime]) -> str:
        """
        Generates official OpenAQ S3 object key.
        Pattern: records/csv.gz/locationid={location_id}/year={YYYY}/month={MM}/location-{location_id}-{YYYYMMDD}.csv.gz
        """
        d = self._parse_date(target_date)
        year_str = d.strftime("%Y")
        month_str = d.strftime("%m")
        yyyymmdd = d.strftime("%Y%m%d")

        return f"records/csv.gz/locationid={location_id}/year={year_str}/month={month_str}/location-{location_id}-{yyyymmdd}.csv.gz"

    def generate_object_url(self, location_id: int, target_date: Union[str, date, datetime]) -> str:
        """Generates full public HTTPS URL for an archive object key."""
        object_key = self.generate_object_key(location_id, target_date)
        return f"{self.base_url}/{object_key}"

    def validate_single_object(
        self, location_id: int, target_date: Union[str, date, datetime]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validates access and schema structure for a single known archive object key.
        Step 2 requirement: test 1 small read operation before batch processing.
        """
        url = self.generate_object_url(location_id, target_date)
        object_key = self.generate_object_key(location_id, target_date)
        logger.info(f"Validating AWS S3 archive object: {url}")

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VayuDrishti-ArchiveClient/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status != 200:
                    return False, {
                        "url": url,
                        "object_key": object_key,
                        "status_code": response.status,
                        "error": f"HTTP {response.status}",
                    }
                compressed_bytes = response.read()

            file_size = len(compressed_bytes)
            sha256_checksum = hashlib.sha256(compressed_bytes).hexdigest()

            # Decompress and check CSV header
            with gzip.GzipFile(fileobj=io.BytesIO(compressed_bytes)) as gz:
                text_content = gz.read().decode("utf-8", errors="replace")

            reader = csv.DictReader(io.StringIO(text_content))
            actual_columns = reader.fieldnames or []
            rows = list(reader)

            valid_schema = all(col in actual_columns for col in ["location_id", "parameter", "datetime", "value"])

            meta = {
                "url": url,
                "object_key": object_key,
                "location_id": location_id,
                "target_date": str(self._parse_date(target_date)),
                "http_status": 200,
                "file_size": file_size,
                "sha256_checksum": sha256_checksum,
                "columns": actual_columns,
                "schema_valid": valid_schema,
                "total_records": len(rows),
                "parameters_found": list({r.get("parameter") for r in rows if r.get("parameter")}),
            }
            return valid_schema, meta

        except Exception as e:
            logger.warning(f"Single object validation failed for {url}: {e}")
            return False, {
                "url": url,
                "object_key": object_key,
                "location_id": location_id,
                "target_date": str(self._parse_date(target_date)),
                "http_status": getattr(e, "code", 500),
                "error": str(e),
                "schema_valid": False,
            }

    def fetch_daily_archive(
        self, location_id: int, target_date: Union[str, date, datetime]
    ) -> Tuple[Optional[bytes], List[Dict[str, Any]], Dict[str, Any]]:
        """
        Fetches single daily archive file, returning (raw_bytes, rows, metadata).
        """
        d = self._parse_date(target_date)
        url = self.generate_object_url(location_id, d)
        object_key = self.generate_object_key(location_id, d)

        metadata: Dict[str, Any] = {
            "source": "openaq_aws",
            "bucket": "openaq-data-archive",
            "object_key": object_key,
            "url": url,
            "location_id": location_id,
            "year": d.year,
            "month": d.month,
            "date": d.strftime("%Y-%m-%d"),
            "retrieval_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "file_size": 0,
            "checksum": None,
            "status": "FAILED",
        }

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VayuDrishti-ArchiveClient/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status != 200:
                    metadata["status"] = f"HTTP_{resp.status}"
                    return None, [], metadata
                raw_bytes = resp.read()

            file_size = len(raw_bytes)
            checksum = hashlib.sha256(raw_bytes).hexdigest()
            metadata["file_size"] = file_size
            metadata["checksum"] = checksum
            metadata["status"] = "SUCCESS"

            with gzip.GzipFile(fileobj=io.BytesIO(raw_bytes)) as gz:
                text = gz.read().decode("utf-8", errors="replace")

            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            return raw_bytes, rows, metadata

        except Exception as e:
            metadata["error"] = str(e)
            return None, [], metadata

    def fetch_date_range(
        self,
        location_id: int,
        start_date: Union[str, date, datetime],
        end_date: Union[str, date, datetime],
        pollutants: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetches daily archive files across a bounded date range.
        Returns dictionary containing raw file metadata list and extracted raw observation rows.
        """
        st_d = self._parse_date(start_date)
        end_d = self._parse_date(end_date)

        if st_d > end_d:
            raise ValueError(f"Start date {st_d} cannot be after end date {end_d}")

        target_pollutants = [p.lower() for p in pollutants] if pollutants else ["pm25", "pm2.5", "pm10"]

        downloaded_manifests: List[Dict[str, Any]] = []
        raw_rows: List[Dict[str, Any]] = []
        raw_bytes_dict: Dict[str, bytes] = {}

        curr_d = st_d
        while curr_d <= end_d:
            raw_bytes, rows, meta = self.fetch_daily_archive(location_id, curr_d)
            downloaded_manifests.append(meta)

            if raw_bytes and meta["status"] == "SUCCESS":
                date_str = curr_d.strftime("%Y-%m-%d")
                raw_bytes_dict[f"location-{location_id}-{date_str}.csv.gz"] = raw_bytes

                for r in rows:
                    p = str(r.get("parameter", "")).lower()
                    if any(target_p in p for target_p in target_pollutants):
                        raw_rows.append(r)

            curr_d += timedelta(days=1)

        return {
            "location_id": location_id,
            "start_date": str(st_d),
            "end_date": str(end_d),
            "downloaded_files_count": len([m for m in downloaded_manifests if m["status"] == "SUCCESS"]),
            "attempted_files_count": len(downloaded_manifests),
            "download_manifests": downloaded_manifests,
            "raw_rows": raw_rows,
            "raw_bytes_dict": raw_bytes_dict,
        }
