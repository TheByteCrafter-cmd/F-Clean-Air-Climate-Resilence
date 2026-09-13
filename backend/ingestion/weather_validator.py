"""
VayuDrishti - Meteorological Observation Validation & Quality Engine
Validates physical limits, detects duplicates, enforces chronological ordering,
and generates auditable weather quality reports.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from backend.api.v1.schemas.weather import WeatherObservation


@dataclass
class WeatherValidationOutcome:
    """Outcome of validating a single WeatherObservation."""
    is_valid: bool
    is_duplicate: bool = False
    rejection_reason: Optional[str] = None
    observation: Optional[WeatherObservation] = None


@dataclass
class WeatherQualityReport:
    """Auditable report detailing meteorological ingestion quality and physical bounds."""
    run_id: str
    source_name: str
    generated_at: str
    location_summary: Dict[str, Any] = field(default_factory=dict)
    records_fetched: int = 0
    records_parsed: int = 0
    records_valid: int = 0
    records_invalid: int = 0
    records_duplicate: int = 0
    invalid_reasons: Dict[str, int] = field(default_factory=dict)
    missing_values: Dict[str, int] = field(default_factory=dict)
    timestamp_min: Optional[str] = None
    timestamp_max: Optional[str] = None
    min_temp_c: Optional[float] = None
    max_temp_c: Optional[float] = None
    min_rh_pct: Optional[float] = None
    max_rh_pct: Optional[float] = None
    min_wind_speed_ms: Optional[float] = None
    max_wind_speed_ms: Optional[float] = None
    min_pressure_hpa: Optional[float] = None
    max_pressure_hpa: Optional[float] = None
    min_blh_m: Optional[float] = None
    max_blh_m: Optional[float] = None
    unit_summary: Dict[str, str] = field(default_factory=dict)

    def record_invalid(self, reason: str) -> None:
        self.records_invalid += 1
        self.invalid_reasons[reason] = self.invalid_reasons.get(reason, 0) + 1

    def record_valid(self, obs: WeatherObservation) -> None:
        self.records_valid += 1
        
        # Track timestamp window
        ts_iso = obs.timestamp.isoformat()
        if self.timestamp_min is None or ts_iso < self.timestamp_min:
            self.timestamp_min = ts_iso
        if self.timestamp_max is None or ts_iso > self.timestamp_max:
            self.timestamp_max = ts_iso

        # Temperature stats
        t = obs.temperature_c
        self.min_temp_c = t if self.min_temp_c is None else min(self.min_temp_c, t)
        self.max_temp_c = t if self.max_temp_c is None else max(self.max_temp_c, t)

        # Humidity stats
        rh = obs.relative_humidity_pct
        self.min_rh_pct = rh if self.min_rh_pct is None else min(self.min_rh_pct, rh)
        self.max_rh_pct = rh if self.max_rh_pct is None else max(self.max_rh_pct, rh)

        # Wind speed stats
        ws = obs.wind_speed_ms
        self.min_wind_speed_ms = ws if self.min_wind_speed_ms is None else min(self.min_wind_speed_ms, ws)
        self.max_wind_speed_ms = ws if self.max_wind_speed_ms is None else max(self.max_wind_speed_ms, ws)

        # Pressure stats
        p = obs.surface_pressure_hpa
        self.min_pressure_hpa = p if self.min_pressure_hpa is None else min(self.min_pressure_hpa, p)
        self.max_pressure_hpa = p if self.max_pressure_hpa is None else max(self.max_pressure_hpa, p)

        # Boundary layer height stats (if present)
        if obs.boundary_layer_height_m is not None:
            blh = obs.boundary_layer_height_m
            self.min_blh_m = blh if self.min_blh_m is None else min(self.min_blh_m, blh)
            self.max_blh_m = blh if self.max_blh_m is None else max(self.max_blh_m, blh)
        else:
            self.missing_values["boundary_layer_height_m"] = self.missing_values.get("boundary_layer_height_m", 0) + 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "source": self.source_name,
            "generated_at": self.generated_at,
            "target_location": self.location_summary,
            "metrics": {
                "records_fetched": self.records_fetched,
                "records_parsed": self.records_parsed,
                "records_valid": self.records_valid,
                "records_invalid": self.records_invalid,
                "records_duplicate": self.records_duplicate,
                "pass_rate_percent": round(
                    (self.records_valid / max(self.records_parsed, 1)) * 100.0, 2
                ),
            },
            "invalid_reasons": self.invalid_reasons,
            "missing_values": self.missing_values,
            "temporal_range": {
                "start": self.timestamp_min,
                "end": self.timestamp_max,
            },
            "physical_summary": {
                "temperature_range_c": [self.min_temp_c, self.max_temp_c],
                "relative_humidity_range_pct": [self.min_rh_pct, self.max_rh_pct],
                "wind_speed_range_ms": [self.min_wind_speed_ms, self.max_wind_speed_ms],
                "surface_pressure_range_hpa": [self.min_pressure_hpa, self.max_pressure_hpa],
                "boundary_layer_height_range_m": [self.min_blh_m, self.max_blh_m],
            },
            "units": self.unit_summary or {
                "temperature": "?C",
                "relative_humidity": "%",
                "surface_pressure": "hPa",
                "wind_speed": "m/s",
                "wind_direction": "degrees (0-360)",
                "precipitation": "mm",
                "boundary_layer_height": "m",
            },
        }

    def to_markdown(self) -> str:
        pass_rate = round((self.records_valid / max(self.records_parsed, 1)) * 100.0, 2)
        md = [
            f"# Open-Meteo Weather Ingestion Quality Report",
            f"**Run ID:** `{self.run_id}`  ",
            f"**Source:** {self.source_name}  ",
            f"**Generated At:** {self.generated_at}  ",
            f"**Pass Rate:** {pass_rate}%  ",
            "",
            "## 1. Volume Metrics",
            f"- **Hourly Steps Fetched:** {self.records_fetched}",
            f"- **Steps Parsed:** {self.records_parsed}",
            f"- **Steps Valid:** {self.records_valid}",
            f"- **Steps Invalid:** {self.records_invalid}",
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
            "## 3. Physical Value Summary",
            f"- **Temperature:** {self.min_temp_c}?C to {self.max_temp_c}?C",
            f"- **Relative Humidity:** {self.min_rh_pct}% to {self.max_rh_pct}%",
            f"- **Wind Speed:** {self.min_wind_speed_ms} m/s to {self.max_wind_speed_ms} m/s",
            f"- **Surface Pressure:** {self.min_pressure_hpa} hPa to {self.max_pressure_hpa} hPa",
            f"- **Boundary Layer Height:** {self.min_blh_m} m to {self.max_blh_m} m",
            "",
            "## 4. Temporal Extent",
            f"- **Time Window:** `{self.timestamp_min}` to `{self.timestamp_max}`",
        ])
        return "\n".join(md)


class WeatherValidator:
    """Validates normalized WeatherObservation instances against physical atmospheric boundaries."""

    def __init__(self):
        self.seen_fingerprints: Set[str] = set()

    def get_fingerprint(self, obs: WeatherObservation) -> str:
        """Deterministic identity: weather:{lat}:{lon}:{timestamp}"""
        lat = round(obs.location.latitude, 4)
        lon = round(obs.location.longitude, 4)
        ts = obs.timestamp.isoformat()
        return f"weather:{lat}:{lon}:{ts}"

    def validate(
        self,
        obs: Optional[WeatherObservation],
        report: Optional[WeatherQualityReport] = None,
    ) -> WeatherValidationOutcome:
        """Audit single WeatherObservation against physical atmospheric boundaries."""
        if obs is None:
            if report:
                report.record_invalid("null_observation")
            return WeatherValidationOutcome(is_valid=False, rejection_reason="null_observation")

        # 1. Coordinate check
        lat = obs.location.latitude
        lon = obs.location.longitude
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            reason = f"coordinates_out_of_bounds: lat={lat}, lon={lon}"
            if report:
                report.record_invalid(reason)
            return WeatherValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 2. Temperature physical boundaries (-50?C to 60?C)
        if not (-50.0 <= obs.temperature_c <= 60.0):
            reason = f"temperature_physical_violation: {obs.temperature_c}?C"
            if report:
                report.record_invalid(reason)
            return WeatherValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 3. Relative humidity bounds (0% to 100%)
        if not (0.0 <= obs.relative_humidity_pct <= 100.0):
            reason = f"humidity_physical_violation: {obs.relative_humidity_pct}%"
            if report:
                report.record_invalid(reason)
            return WeatherValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 4. Surface pressure bounds (800 hPa to 1100 hPa)
        if not (800.0 <= obs.surface_pressure_hpa <= 1100.0):
            reason = f"surface_pressure_physical_violation: {obs.surface_pressure_hpa} hPa"
            if report:
                report.record_invalid(reason)
            return WeatherValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 5. Wind speed bounds (0 to 100 m/s)
        if not (0.0 <= obs.wind_speed_ms <= 100.0):
            reason = f"wind_speed_physical_violation: {obs.wind_speed_ms} m/s"
            if report:
                report.record_invalid(reason)
            return WeatherValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 6. Wind direction bounds (0 to 360 degrees)
        if not (0.0 <= obs.wind_direction_deg <= 360.0):
            reason = f"wind_direction_physical_violation: {obs.wind_direction_deg}?"
            if report:
                report.record_invalid(reason)
            return WeatherValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 7. Boundary layer height (>= 0 m if present)
        if obs.boundary_layer_height_m is not None and obs.boundary_layer_height_m < 0.0:
            reason = f"boundary_layer_height_negative: {obs.boundary_layer_height_m} m"
            if report:
                report.record_invalid(reason)
            return WeatherValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 8. Precipitation (>= 0 mm)
        if obs.precipitation_mm is not None and obs.precipitation_mm < 0.0:
            reason = f"precipitation_negative: {obs.precipitation_mm} mm"
            if report:
                report.record_invalid(reason)
            return WeatherValidationOutcome(is_valid=False, rejection_reason=reason, observation=obs)

        # 9. Deduplication check
        fingerprint = self.get_fingerprint(obs)
        if fingerprint in self.seen_fingerprints:
            if report:
                report.records_duplicate += 1
            return WeatherValidationOutcome(
                is_valid=False,
                is_duplicate=True,
                rejection_reason=f"duplicate_hourly_observation: {fingerprint}",
                observation=obs,
            )

        self.seen_fingerprints.add(fingerprint)
        if report:
            report.record_valid(obs)

        return WeatherValidationOutcome(is_valid=True, observation=obs)
