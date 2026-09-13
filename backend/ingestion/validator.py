"""
VayuDrishti - Observation Validation & Quality Reporting Engine
Provides deterministic validation, deduplication, and auditable data quality reporting.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.api.v1.schemas.observation import EnvironmentalObservation

CANONICAL_POLLUTANTS = {"PM2.5", "PM10", "NO2", "SO2", "CO", "O3"}


@dataclass
class ValidationOutcome:
    """Outcome of single observation validation."""
    is_valid: bool
    is_duplicate: bool = False
    rejection_reason: Optional[str] = None
    observation: Optional[EnvironmentalObservation] = None


@dataclass
class DataQualityReport:
    """Auditable report detailing ingestion volume, validation rates, and distributions."""
    run_id: str
    source_name: str
    generated_at: str
    records_fetched: int = 0
    records_parsed: int = 0
    records_normalized: int = 0
    records_valid: int = 0
    records_invalid: int = 0
    records_duplicate: int = 0
    invalid_reasons: Dict[str, int] = field(default_factory=dict)
    pollutant_counts: Dict[str, int] = field(default_factory=dict)
    station_counts: Dict[str, int] = field(default_factory=dict)
    timestamp_min: Optional[str] = None
    timestamp_max: Optional[str] = None
    lat_min: Optional[float] = None
    lat_max: Optional[float] = None
    lon_min: Optional[float] = None
    lon_max: Optional[float] = None

    def record_invalid(self, reason: str) -> None:
        """Record an invalid record with its rejection reason."""
        self.records_invalid += 1
        self.invalid_reasons[reason] = self.invalid_reasons.get(reason, 0) + 1

    def record_valid(self, obs: EnvironmentalObservation) -> None:
        """Record a valid observation and update statistics."""
        self.records_valid += 1
        self.records_normalized += 1
        
        # Pollutant tally
        p = obs.pollutant
        self.pollutant_counts[p] = self.pollutant_counts.get(p, 0) + 1
        
        # Station tally
        s = obs.station_id or "UNKNOWN"
        self.station_counts[s] = self.station_counts.get(s, 0) + 1
        
        # Timestamp range
        ts_iso = obs.timestamp.isoformat()
        if self.timestamp_min is None or ts_iso < self.timestamp_min:
            self.timestamp_min = ts_iso
        if self.timestamp_max is None or ts_iso > self.timestamp_max:
            self.timestamp_max = ts_iso
            
        # Geographic bounds
        lat = obs.location.latitude
        lon = obs.location.longitude
        if self.lat_min is None or lat < self.lat_min:
            self.lat_min = lat
        if self.lat_max is None or lat > self.lat_max:
            self.lat_max = lat
        if self.lon_min is None or lon < self.lon_min:
            self.lon_min = lon
        if self.lon_max is None or lon > self.lon_max:
            self.lon_max = lon

    def to_dict(self) -> Dict[str, Any]:
        """Convert quality report to JSON-serializable dictionary."""
        return {
            "run_id": self.run_id,
            "source": self.source_name,
            "generated_at": self.generated_at,
            "metrics": {
                "records_fetched": self.records_fetched,
                "records_parsed": self.records_parsed,
                "records_normalized": self.records_normalized,
                "records_valid": self.records_valid,
                "records_invalid": self.records_invalid,
                "records_duplicate": self.records_duplicate,
                "pass_rate_percent": round(
                    (self.records_valid / max(self.records_parsed, 1)) * 100.0, 2
                ),
            },
            "invalid_reasons": self.invalid_reasons,
            "distributions": {
                "pollutant_counts": self.pollutant_counts,
                "station_counts": self.station_counts,
            },
            "temporal_range": {
                "min": self.timestamp_min,
                "max": self.timestamp_max,
            },
            "geographic_range": {
                "lat_min": self.lat_min,
                "lat_max": self.lat_max,
                "lon_min": self.lon_min,
                "lon_max": self.lon_max,
            },
        }

    def to_markdown(self) -> str:
        """Generate clean human-readable Markdown summary."""
        pass_rate = round((self.records_valid / max(self.records_parsed, 1)) * 100.0, 2)
        md = [
            f"# OpenAQ Data Ingestion Quality Report",
            f"**Run ID:** `{self.run_id}`  ",
            f"**Source:** {self.source_name}  ",
            f"**Generated At:** {self.generated_at}  ",
            f"**Pass Rate:** {pass_rate}%  ",
            "",
            "## 1. Volume Metrics",
            f"- **Records Fetched:** {self.records_fetched}",
            f"- **Records Parsed:** {self.records_parsed}",
            f"- **Records Valid:** {self.records_valid}",
            f"- **Records Invalid:** {self.records_invalid}",
            f"- **Duplicates Filtered:** {self.records_duplicate}",
            "",
            "## 2. Invalid Reasons Breakdown",
        ]
        if self.invalid_reasons:
            for r, count in sorted(self.invalid_reasons.items(), key=lambda x: x[1], reverse=True):
                md.append(f"- `{r}`: {count}")
        else:
            md.append("None (100% clean ingestion).")

        md.extend([
            "",
            "## 3. Pollutant Distribution",
        ])
        for p, count in sorted(self.pollutant_counts.items()):
            md.append(f"- **{p}:** {count} observations")

        md.extend([
            "",
            "## 4. Geographic & Temporal Extent",
            f"- **Time Window:** `{self.timestamp_min}` to `{self.timestamp_max}`",
            f"- **Latitude Bounds:** [{self.lat_min}, {self.lat_max}]",
            f"- **Longitude Bounds:** [{self.lon_min}, {self.lon_max}]",
        ])
        return "\n".join(md)


class ObservationValidator:
    """Validates normalized EnvironmentalObservation instances."""

    def __init__(self):
        self.seen_fingerprints: Set[str] = set()

    def get_fingerprint(self, obs: EnvironmentalObservation) -> str:
        """Deterministic identity string for deduplication: station:pollutant:timestamp."""
        station = obs.station_id or "UNKNOWN"
        pollutant = obs.pollutant
        ts = obs.timestamp.isoformat()
        return f"{station}:{pollutant}:{ts}"

    def validate(
        self,
        obs: Optional[EnvironmentalObservation],
        report: Optional[DataQualityReport] = None,
    ) -> ValidationOutcome:
        """Audit single observation against physical and schema rules."""
        if obs is None:
            if report:
                report.record_invalid("null_observation")
            return ValidationOutcome(is_valid=False, rejection_reason="null_observation")

        # 1. Coordinates check
        lat = obs.location.latitude
        lon = obs.location.longitude
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            reason = f"coordinates_out_of_bounds: lat={lat}, lon={lon}"
            if report:
                report.record_invalid(reason)
            return ValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 2. Timestamp check (not None, not in distant future > 24h)
        now_utc = datetime.now(timezone.utc)
        if obs.timestamp > now_utc + timedelta(hours=24):
            reason = f"future_timestamp_violation: {obs.timestamp.isoformat()}"
            if report:
                report.record_invalid(reason)
            return ValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 3. Pollutant check
        if obs.pollutant not in CANONICAL_POLLUTANTS:
            reason = f"unsupported_pollutant: '{obs.pollutant}'"
            if report:
                report.record_invalid(reason)
            return ValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 4. Numeric value check (no negative concentrations)
        if obs.value < 0.0:
            reason = f"negative_concentration_physical_violation: {obs.value}"
            if report:
                report.record_invalid(reason)
            return ValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 5. Non-empty unit and source
        if not obs.unit or not obs.unit.strip():
            reason = "empty_unit"
            if report:
                report.record_invalid(reason)
            return ValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        if not obs.source or not obs.source.strip():
            reason = "empty_source"
            if report:
                report.record_invalid(reason)
            return ValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 6. Idempotency / Deduplication check
        fingerprint = self.get_fingerprint(obs)
        if fingerprint in self.seen_fingerprints:
            if report:
                report.records_duplicate += 1
            return ValidationOutcome(
                is_valid=False,
                is_duplicate=True,
                rejection_reason=f"duplicate_record: {fingerprint}",
                observation=obs,
            )

        self.seen_fingerprints.add(fingerprint)
        if report:
            report.record_valid(obs)

        return ValidationOutcome(is_valid=True, observation=obs)
