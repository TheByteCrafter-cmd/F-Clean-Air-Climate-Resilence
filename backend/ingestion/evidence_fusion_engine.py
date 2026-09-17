"""
VayuDrishti — Phase 1E-H Multi-Source Evidence Fusion Engine

Provides a deterministic, rule-based, offline evidence fusion engine that correlates
citizen evidence, Gemini AI interpretation, OpenAQ air quality, Open-Meteo weather,
NASA FIRMS thermal anomalies, Sentinel-5P NO2 satellite signals, and OSM geospatial context.
"""

import json
import logging
import math
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.api.v1.schemas.evidence import EvidenceManifest, EvidenceAIAnalysis
from backend.api.v1.schemas.fusion import MatchedRecordRef, EvidenceFusionResult
from backend.ingestion.citizen_evidence_storage import CitizenEvidenceStorage, validate_safe_id
from backend.ingestion.gemini_evidence_analyzer import GeminiEvidenceAnalyzer
from backend.ingestion.exceptions import (
    AnchorMetadataNotFoundError,
    EvidenceFusionError,
    FusionPersistenceError,
)

logger = logging.getLogger(__name__)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates geodesic distance between two WGS84 coordinates in kilometers using Haversine formula."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c, 3)


def time_difference_minutes(t_anchor: datetime, t_obs: datetime) -> float:
    """Calculates signed time difference in minutes: (t_obs - t_anchor)."""
    return round((t_obs - t_anchor).total_seconds() / 60.0, 1)


class FusionConfiguration:
    """Explicit, documented configuration for provisional fusion matching windows and weights."""

    def __init__(
        self,
        config_version: str = "1.0-provisional",
        openaq_max_distance_km: float = 10.0,
        openaq_max_time_minutes: float = 60.0,
        weather_max_distance_km: float = 25.0,
        weather_max_time_minutes: float = 180.0,
        firms_max_distance_km: float = 15.0,
        firms_max_time_minutes: float = 720.0,
        sentinel5p_max_distance_km: float = 30.0,
        sentinel5p_max_time_minutes: float = 1440.0,
        osm_max_distance_km: float = 5.0,
        weight_citizen_gemini: float = 25.0,
        weight_air_quality: float = 25.0,
        weight_firms_thermal: float = 15.0,
        weight_weather: float = 15.0,
        weight_sentinel5p: float = 10.0,
        weight_geospatial: float = 10.0,
        tier_moderate_threshold: float = 40.0,
        tier_high_threshold: float = 70.0,
    ):
        self.config_version = config_version
        self.openaq_max_distance_km = openaq_max_distance_km
        self.openaq_max_time_minutes = openaq_max_time_minutes
        self.weather_max_distance_km = weather_max_distance_km
        self.weather_max_time_minutes = weather_max_time_minutes
        self.firms_max_distance_km = firms_max_distance_km
        self.firms_max_time_minutes = firms_max_time_minutes
        self.sentinel5p_max_distance_km = sentinel5p_max_distance_km
        self.sentinel5p_max_time_minutes = sentinel5p_max_time_minutes
        self.osm_max_distance_km = osm_max_distance_km

        self.weight_citizen_gemini = weight_citizen_gemini
        self.weight_air_quality = weight_air_quality
        self.weight_firms_thermal = weight_firms_thermal
        self.weight_weather = weight_weather
        self.weight_sentinel5p = weight_sentinel5p
        self.weight_geospatial = weight_geospatial

        self.tier_moderate_threshold = tier_moderate_threshold
        self.tier_high_threshold = tier_high_threshold


class EvidenceFusionEngine:
    """Deterministic offline engine for multi-source evidence fusion."""

    def __init__(
        self,
        data_root: Optional[Union[str, Path]] = None,
        config: Optional[FusionConfiguration] = None,
    ):
        self.config = config or FusionConfiguration()
        self.storage = CitizenEvidenceStorage(data_root=data_root)
        self.analyzer = GeminiEvidenceAnalyzer(data_root=data_root)

        self.data_root = Path(data_root) if data_root else self.storage.root_dir
        self.processed_dir = self.data_root / "processed"
        self.raw_dir = self.data_root / "raw"

        self.fusion_dir = self.processed_dir / "fusion"
        self.fusion_dir.mkdir(parents=True, exist_ok=True)

    def fuse_evidence(
        self,
        evidence_id: str,
        custom_openaq_data: Optional[List[Dict[str, Any]]] = None,
        custom_weather_data: Optional[List[Dict[str, Any]]] = None,
        custom_firms_data: Optional[List[Dict[str, Any]]] = None,
        custom_satellite_data: Optional[List[Dict[str, Any]]] = None,
        custom_geospatial_data: Optional[List[Dict[str, Any]]] = None,
    ) -> EvidenceFusionResult:
        """
        Executes multi-source evidence fusion anchored around citizen evidence ID.

        Args:
            evidence_id: Canonical evidence ID (ev_<uuid_hex>)
            custom_openaq_data: Optional in-memory OpenAQ records for testing
            custom_weather_data: Optional in-memory weather records for testing
            custom_firms_data: Optional in-memory FIRMS records for testing
            custom_satellite_data: Optional in-memory Sentinel-5P records for testing
            custom_geospatial_data: Optional in-memory GeoJSON features for testing

        Returns:
            Validated EvidenceFusionResult Pydantic model
        """
        if not validate_safe_id(evidence_id):
            raise EvidenceFusionError(f"Invalid or unsafe evidence ID format: '{evidence_id}'")

        # 1. Load Event Anchor (Citizen Evidence)
        manifest = self.storage.get_manifest(evidence_id)
        if not manifest:
            raise AnchorMetadataNotFoundError(f"Evidence manifest '{evidence_id}' not found.")

        if not manifest.location or manifest.location.latitude is None or manifest.location.longitude is None:
            raise AnchorMetadataNotFoundError(
                f"Evidence manifest '{evidence_id}' lacks valid geolocation coordinates for event anchoring."
            )

        anchor_lat = manifest.location.latitude
        anchor_lon = manifest.location.longitude
        anchor_time = manifest.submitted_at
        if anchor_time.tzinfo is None:
            anchor_time = anchor_time.replace(tzinfo=timezone.utc)

        # 2. Load Gemini Analysis if available
        ai_analysis = self.analyzer.get_existing_analysis(evidence_id)

        provenance_sources: List[str] = [
            f"data/processed/citizen_evidence/manifests/{evidence_id}.json"
        ]
        if ai_analysis:
            provenance_sources.append(f"data/processed/citizen_evidence/analysis/{evidence_id}.json")

        supporting_signals: List[MatchedRecordRef] = []
        conflicting_signals: List[MatchedRecordRef] = []
        unavailable_signals: List[str] = []
        uncertainty_notes: List[str] = []

        # ----------------------------------------------------------------------
        # FAMILY 1: CITIZEN + GEMINI EVIDENCE FAMILY (Max 25 pts)
        # ----------------------------------------------------------------------
        cg_score, cg_ref, cg_note = self._score_citizen_gemini_family(
            manifest, ai_analysis
        )
        if cg_ref:
            supporting_signals.append(cg_ref)
        if cg_note:
            uncertainty_notes.append(cg_note)

        # ----------------------------------------------------------------------
        # FAMILY 2: AIR QUALITY OBSERVATION FAMILY (Max 25 pts)
        # ----------------------------------------------------------------------
        openaq_records = custom_openaq_data if custom_openaq_data is not None else self._load_openaq_records()
        aq_score, aq_support_ref, aq_conflict_ref, aq_status = self._score_air_quality_family(
            anchor_lat, anchor_lon, anchor_time, openaq_records, provenance_sources
        )
        if aq_support_ref:
            supporting_signals.append(aq_support_ref)
        if aq_conflict_ref:
            conflicting_signals.append(aq_conflict_ref)
        if aq_status == "UNAVAILABLE":
            unavailable_signals.append("AIR_QUALITY")

        # ----------------------------------------------------------------------
        # FAMILY 3: NASA FIRMS THERMAL ANOMALY FAMILY (Max 15 pts)
        # ----------------------------------------------------------------------
        firms_records = custom_firms_data if custom_firms_data is not None else self._load_firms_records()
        firms_score, firms_support_ref, firms_status = self._score_firms_family(
            anchor_lat, anchor_lon, anchor_time, firms_records, provenance_sources
        )
        if firms_support_ref:
            supporting_signals.append(firms_support_ref)
        if firms_status == "UNAVAILABLE":
            unavailable_signals.append("THERMAL_ANOMALY")

        # ----------------------------------------------------------------------
        # FAMILY 4: WEATHER CONTEXT FAMILY (Max 15 pts)
        # ----------------------------------------------------------------------
        weather_records = custom_weather_data if custom_weather_data is not None else self._load_weather_records()
        wx_score, wx_support_ref, wx_status = self._score_weather_family(
            anchor_lat, anchor_lon, anchor_time, weather_records, provenance_sources
        )
        if wx_support_ref:
            supporting_signals.append(wx_support_ref)
        if wx_status == "UNAVAILABLE":
            unavailable_signals.append("WEATHER")

        # ----------------------------------------------------------------------
        # FAMILY 5: SENTINEL-5P SATELLITE NO2 FAMILY (Max 10 pts)
        # ----------------------------------------------------------------------
        sat_records = custom_satellite_data if custom_satellite_data is not None else self._load_satellite_records()
        sat_score, sat_support_ref, sat_status = self._score_satellite_family(
            anchor_lat, anchor_lon, anchor_time, sat_records, provenance_sources
        )
        if sat_support_ref:
            supporting_signals.append(sat_support_ref)
        if sat_status == "UNAVAILABLE":
            unavailable_signals.append("SATELLITE_NO2")

        # ----------------------------------------------------------------------
        # FAMILY 6: GEOSPATIAL CONTEXT FAMILY (Max 10 pts)
        # ----------------------------------------------------------------------
        geo_records = custom_geospatial_data if custom_geospatial_data is not None else self._load_geospatial_records()
        geo_score, geo_support_ref, geo_status = self._score_geospatial_family(
            anchor_lat, anchor_lon, geo_records, provenance_sources
        )
        if geo_support_ref:
            supporting_signals.append(geo_support_ref)
        if geo_status == "UNAVAILABLE":
            unavailable_signals.append("GEOSPATIAL_CONTEXT")

        # ----------------------------------------------------------------------
        # TOTAL SUPPORT SCORE & CONFIDENCE TIER CALCULATION
        # ----------------------------------------------------------------------
        raw_score = cg_score + aq_score + firms_score + wx_score + sat_score + geo_score
        support_score = round(min(100.0, max(0.0, raw_score)), 1)

        if support_score >= self.config.tier_high_threshold:
            confidence_tier = "HIGH_SUPPORT"
        elif support_score >= self.config.tier_moderate_threshold:
            confidence_tier = "MODERATE_SUPPORT"
        else:
            confidence_tier = "LOW_SUPPORT"

        # General Scientific Disclaimer Note
        uncertainty_notes.append(
            "Observations correlate spatially and temporally but do NOT establish causal pollution source proof."
        )

        # ----------------------------------------------------------------------
        # DETERMINISTIC EXPLANATION GENERATION
        # ----------------------------------------------------------------------
        explanation = self._generate_explanation(
            support_score,
            confidence_tier,
            supporting_signals,
            unavailable_signals,
            conflicting_signals,
        )

        fusion_id = f"fu_{uuid.uuid4().hex}"
        now_utc = datetime.now(timezone.utc)

        result = EvidenceFusionResult(
            fusion_id=fusion_id,
            event_anchor_id=evidence_id,
            created_at=now_utc,
            support_score=support_score,
            confidence_tier=confidence_tier,
            supporting_signals=supporting_signals,
            unavailable_signals=unavailable_signals,
            conflicting_signals=conflicting_signals,
            explanation=explanation,
            uncertainty_notes=uncertainty_notes,
            provenance_sources=list(dict.fromkeys(provenance_sources)),
            config_version=self.config.config_version,
            schema_version="1.0",
        )

        # ----------------------------------------------------------------------
        # PERSISTENCE
        # ----------------------------------------------------------------------
        self.save_fusion_result(result)
        return result

    def _score_citizen_gemini_family(
        self, manifest: EvidenceManifest, ai_analysis: Optional[EvidenceAIAnalysis]
    ) -> Tuple[float, Optional[MatchedRecordRef], Optional[str]]:
        """Scores Citizen + Gemini family (Max 25 pts) without double counting."""
        base_score = 10.0
        ref_id = manifest.evidence_id
        details = {
            "category": manifest.category or "unspecified",
            "has_photo": any(m.media_type == "photo" for m in manifest.media),
            "has_description": bool(manifest.description),
        }
        note = None

        if ai_analysis:
            details["gemini_relevance"] = ai_analysis.relevance
            details["gemini_model"] = ai_analysis.model_name

            if ai_analysis.relevance == "relevant":
                if any(c.confidence_level == "high" for c in ai_analysis.probable_categories):
                    base_score = 25.0
                else:
                    base_score = 22.0
            elif ai_analysis.relevance == "partially_relevant":
                base_score = 18.0
            elif ai_analysis.relevance in ["insufficient_evidence", "irrelevant"]:
                base_score = 10.0
                note = f"Gemini analysis indicated visual evidence was '{ai_analysis.relevance}'."

        ref = MatchedRecordRef(
            source_family="CITIZEN_GEMINI",
            source_type="CitizenReport_GeminiCombined",
            record_id=ref_id,
            distance_km=0.0,
            time_difference_minutes=0.0,
            key_values=details,
            provenance_ref=f"data/processed/citizen_evidence/manifests/{manifest.evidence_id}.json",
        )
        return base_score, ref, note

    def _score_air_quality_family(
        self,
        lat: float,
        lon: float,
        t_anchor: datetime,
        records: List[Dict[str, Any]],
        prov_list: List[str],
    ) -> Tuple[float, Optional[MatchedRecordRef], Optional[MatchedRecordRef], str]:
        """Scores OpenAQ observations (Max 25 pts) based on proximity and elevated pollutant values."""
        best_match = None
        best_dist = float("inf")
        best_time_diff = float("inf")
        best_val = 0.0
        best_pollutant = "PM2.5"

        for rec in records:
            r_lat = rec.get("latitude") or (rec.get("location", {}).get("latitude") if isinstance(rec.get("location"), dict) else None)
            r_lon = rec.get("longitude") or (rec.get("location", {}).get("longitude") if isinstance(rec.get("location"), dict) else None)
            if r_lat is None or r_lon is None:
                continue

            dist = haversine_distance_km(lat, lon, r_lat, r_lon)
            if dist > self.config.openaq_max_distance_km:
                continue

            raw_time = rec.get("timestamp") or rec.get("datetime")
            if not raw_time:
                continue
            try:
                t_obs = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                if t_obs.tzinfo is None:
                    t_obs = t_obs.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            t_diff = abs(time_difference_minutes(t_anchor, t_obs))
            if t_diff > self.config.openaq_max_time_minutes:
                continue

            val = float(rec.get("value", 0.0))
            if dist < best_dist:
                best_dist = dist
                best_time_diff = time_difference_minutes(t_anchor, t_obs)
                best_match = rec
                best_val = val
                best_pollutant = rec.get("pollutant", "PM2.5")

        if not best_match:
            return 0.0, None, None, "UNAVAILABLE"

        prov_ref = best_match.get("source_file", "data/processed/openaq_delhi_observations.jsonl")
        prov_list.append(prov_ref)

        rec_ref = MatchedRecordRef(
            source_family="AIR_QUALITY",
            source_type="OpenAQ",
            record_id=str(best_match.get("source_record_id") or best_match.get("station_id") or "openaq_station"),
            distance_km=best_dist,
            time_difference_minutes=best_time_diff,
            key_values={"pollutant": best_pollutant, "value": best_val, "unit": best_match.get("unit", "µg/m³")},
            provenance_ref=prov_ref,
        )

        # Determine if elevated or normal (elevated threshold: PM2.5 > 60 µg/m³ or PM10 > 100 µg/m³)
        threshold = 60.0 if "2.5" in str(best_pollutant) else 100.0
        if best_val >= threshold:
            if best_dist <= 1.0:
                score = 25.0
            elif best_dist <= 3.0:
                score = 20.0
            else:
                score = 12.0
            return score, rec_ref, None, "MATCHED"
        else:
            # Matched within window but value is normal -> Conflicting signal
            return 0.0, None, rec_ref, "CONFLICTING"

    def _score_firms_family(
        self,
        lat: float,
        lon: float,
        t_anchor: datetime,
        records: List[Dict[str, Any]],
        prov_list: List[str],
    ) -> Tuple[float, Optional[MatchedRecordRef], str]:
        """Scores NASA FIRMS thermal anomaly observations (Max 15 pts)."""
        best_match = None
        best_dist = float("inf")
        best_time_diff = 0.0
        best_frp = 0.0

        for rec in records:
            r_lat = rec.get("latitude")
            r_lon = rec.get("longitude")
            if r_lat is None or r_lon is None:
                continue

            dist = haversine_distance_km(lat, lon, float(r_lat), float(r_lon))
            if dist > self.config.firms_max_distance_km:
                continue

            raw_time = rec.get("timestamp") or rec.get("acq_datetime")
            if not raw_time:
                continue
            try:
                t_obs = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                if t_obs.tzinfo is None:
                    t_obs = t_obs.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            t_diff = abs(time_difference_minutes(t_anchor, t_obs))
            if t_diff > self.config.firms_max_time_minutes:
                continue

            frp = float(rec.get("frp", rec.get("frp_mw", 0.0)))
            if dist < best_dist:
                best_dist = dist
                best_time_diff = time_difference_minutes(t_anchor, t_obs)
                best_match = rec
                best_frp = frp

        if not best_match:
            return 0.0, None, "UNAVAILABLE"

        prov_ref = best_match.get("source_file", "data/processed/firms_delhi_fire.jsonl")
        prov_list.append(prov_ref)

        rec_ref = MatchedRecordRef(
            source_family="THERMAL_ANOMALY",
            source_type="NASA_FIRMS",
            record_id=str(best_match.get("fire_signal_id") or best_match.get("source_record_id") or "firms_fire"),
            distance_km=best_dist,
            time_difference_minutes=best_time_diff,
            key_values={"frp_mw": best_frp, "confidence": best_match.get("confidence", "nominal")},
            provenance_ref=prov_ref,
        )

        if best_dist <= 3.0 and best_frp >= 5.0:
            score = 15.0
        elif best_dist <= 10.0:
            score = 10.0
        else:
            score = 5.0

        return score, rec_ref, "MATCHED"

    def _score_weather_family(
        self,
        lat: float,
        lon: float,
        t_anchor: datetime,
        records: List[Dict[str, Any]],
        prov_list: List[str],
    ) -> Tuple[float, Optional[MatchedRecordRef], str]:
        """Scores Open-Meteo weather context observations (Max 15 pts)."""
        best_match = None
        best_dist = float("inf")
        best_time_diff = float("inf")

        for rec in records:
            r_lat = rec.get("latitude") or (rec.get("location", {}).get("latitude") if isinstance(rec.get("location"), dict) else lat)
            r_lon = rec.get("longitude") or (rec.get("location", {}).get("longitude") if isinstance(rec.get("location"), dict) else lon)

            dist = haversine_distance_km(lat, lon, float(r_lat), float(r_lon))
            if dist > self.config.weather_max_distance_km:
                continue

            raw_time = rec.get("timestamp") or rec.get("datetime")
            if not raw_time:
                continue
            try:
                t_obs = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                if t_obs.tzinfo is None:
                    t_obs = t_obs.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            t_diff = abs(time_difference_minutes(t_anchor, t_obs))
            if t_diff > self.config.weather_max_time_minutes:
                continue

            if t_diff < abs(best_time_diff):
                best_dist = dist
                best_time_diff = time_difference_minutes(t_anchor, t_obs)
                best_match = rec

        if not best_match:
            return 0.0, None, "UNAVAILABLE"

        prov_ref = best_match.get("source_file", "data/processed/open_meteo_delhi_weather.jsonl")
        prov_list.append(prov_ref)

        wind_speed = float(best_match.get("wind_speed_ms", best_match.get("wind_speed_10m", 2.0)))
        humidity = float(best_match.get("relative_humidity_pct", 65.0))
        temp = float(best_match.get("temperature_c", 25.0))

        rec_ref = MatchedRecordRef(
            source_family="WEATHER",
            source_type="OpenMeteo",
            record_id=str(best_match.get("weather_id") or "wx_obs"),
            distance_km=best_dist,
            time_difference_minutes=best_time_diff,
            key_values={"wind_speed_ms": wind_speed, "relative_humidity_pct": humidity, "temperature_c": temp},
            provenance_ref=prov_ref,
        )

        # Stagnant conditions award higher score
        if wind_speed <= 2.0:
            score = 15.0
        elif wind_speed <= 3.5:
            score = 10.0
        else:
            score = 5.0

        return score, rec_ref, "MATCHED"

    def _score_satellite_family(
        self,
        lat: float,
        lon: float,
        t_anchor: datetime,
        records: List[Dict[str, Any]],
        prov_list: List[str],
    ) -> Tuple[float, Optional[MatchedRecordRef], str]:
        """Scores Sentinel-5P NO2 satellite column density observations (Max 10 pts)."""
        best_match = None
        best_dist = float("inf")
        best_time_diff = float("inf")

        for rec in records:
            r_lat = rec.get("latitude") or (rec.get("location", {}).get("latitude") if isinstance(rec.get("location"), dict) else lat)
            r_lon = rec.get("longitude") or (rec.get("location", {}).get("longitude") if isinstance(rec.get("location"), dict) else lon)

            dist = haversine_distance_km(lat, lon, float(r_lat), float(r_lon))
            if dist > self.config.sentinel5p_max_distance_km:
                continue

            raw_time = rec.get("timestamp") or rec.get("datetime")
            if not raw_time:
                continue
            try:
                t_obs = datetime.fromisoformat(str(raw_time).replace("Z", "+00:00"))
                if t_obs.tzinfo is None:
                    t_obs = t_obs.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            t_diff = abs(time_difference_minutes(t_anchor, t_obs))
            if t_diff > self.config.sentinel5p_max_time_minutes:
                continue

            if dist < best_dist:
                best_dist = dist
                best_time_diff = time_difference_minutes(t_anchor, t_obs)
                best_match = rec

        if not best_match:
            return 0.0, None, "UNAVAILABLE"

        prov_ref = best_match.get("source_file", "data/processed/satellite/sentinel5p_delhi_no2.jsonl")
        prov_list.append(prov_ref)

        val = float(rec.get("value", rec.get("no2_column_density", 0.0001)))
        rec_ref = MatchedRecordRef(
            source_family="SATELLITE_NO2",
            source_type="Sentinel-5P_TROPOMI",
            record_id=str(best_match.get("satellite_id") or "s5p_no2"),
            distance_km=best_dist,
            time_difference_minutes=best_time_diff,
            key_values={"no2_column_density": val, "unit": "mol/m²"},
            provenance_ref=prov_ref,
        )

        score = 10.0 if best_dist <= 15.0 else 5.0
        return score, rec_ref, "MATCHED"

    def _score_geospatial_family(
        self,
        lat: float,
        lon: float,
        records: List[Dict[str, Any]],
        prov_list: List[str],
    ) -> Tuple[float, Optional[MatchedRecordRef], str]:
        """Scores OSM / Geospatial context layers (Max 10 pts)."""
        best_match = None
        best_dist = float("inf")

        for rec in records:
            r_lat = rec.get("latitude")
            r_lon = rec.get("longitude")
            if r_lat is None or r_lon is None:
                continue

            dist = haversine_distance_km(lat, lon, float(r_lat), float(r_lon))
            if dist > self.config.osm_max_distance_km:
                continue

            if dist < best_dist:
                best_dist = dist
                best_match = rec

        if not best_match:
            return 0.0, None, "UNAVAILABLE"

        prov_ref = best_match.get("source_file", "data/processed/geospatial/delhi_industrial_areas.geojson")
        prov_list.append(prov_ref)

        rec_ref = MatchedRecordRef(
            source_family="GEOSPATIAL_CONTEXT",
            source_type="OpenStreetMap",
            record_id=str(best_match.get("feature_id") or best_match.get("name") or "osm_feature"),
            distance_km=best_dist,
            time_difference_minutes=None,
            key_values={
                "name": best_match.get("name", "Industrial Zone"),
                "category": best_match.get("category", "industrial"),
            },
            provenance_ref=prov_ref,
        )

        score = 10.0 if best_dist <= 2.0 else 5.0
        return score, rec_ref, "MATCHED"

    # --------------------------------------------------------------------------
    # DATA LOADERS (OFFLINE FILESYSTEM SCANNING)
    # --------------------------------------------------------------------------
    def _load_openaq_records(self) -> List[Dict[str, Any]]:
        """Scans data/processed/ for openaq_*.jsonl files."""
        return self._scan_jsonl_files(self.processed_dir, "openaq_*.jsonl")

    def _load_firms_records(self) -> List[Dict[str, Any]]:
        """Scans data/processed/ for firms_*.jsonl files."""
        return self._scan_jsonl_files(self.processed_dir, "firms_*.jsonl")

    def _load_weather_records(self) -> List[Dict[str, Any]]:
        """Scans data/processed/ for open_meteo_*.jsonl files."""
        return self._scan_jsonl_files(self.processed_dir, "open_meteo_*.jsonl")

    def _load_satellite_records(self) -> List[Dict[str, Any]]:
        """Scans data/processed/satellite/ for sentinel5p_*.jsonl files."""
        sat_dir = self.processed_dir / "satellite"
        return self._scan_jsonl_files(sat_dir, "sentinel5p_*.jsonl")

    def _load_geospatial_records(self) -> List[Dict[str, Any]]:
        """Scans data/processed/geospatial/ for *.geojson files and extracts centroid features."""
        geo_dir = self.processed_dir / "geospatial"
        if not geo_dir.exists():
            return []

        features: List[Dict[str, Any]] = []
        for path in geo_dir.glob("*.geojson"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for feat in data.get("features", []):
                    props = feat.get("properties", {})
                    geom = feat.get("geometry", {})
                    coords = geom.get("coordinates")
                    if geom.get("type") == "Point" and coords:
                        features.append({
                            "feature_id": props.get("id") or props.get("name") or "geo_feat",
                            "latitude": coords[1],
                            "longitude": coords[0],
                            "name": props.get("name") or "Geospatial Feature",
                            "category": props.get("category") or props.get("landuse") or "industrial",
                            "source_file": str(path.relative_to(self.data_root)).replace("\\", "/"),
                        })
            except Exception as e:
                logger.warning(f"Error reading GeoJSON fixture {path}: {e}")
        return features

    def _scan_jsonl_files(self, directory: Path, pattern: str) -> List[Dict[str, Any]]:
        """Scans directory for jsonl files matching pattern."""
        if not directory.exists():
            return []

        records: List[Dict[str, Any]] = []
        for path in directory.glob(pattern):
            try:
                rel_path = str(path.relative_to(self.data_root)).replace("\\", "/")
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            rec = json.loads(line)
                            rec["source_file"] = rel_path
                            records.append(rec)
            except Exception as e:
                logger.warning(f"Error reading JSONL fixture {path}: {e}")
        return records

    # --------------------------------------------------------------------------
    # DETERMINISTIC EXPLANATION GENERATOR
    # --------------------------------------------------------------------------
    def _generate_explanation(
        self,
        score: float,
        tier: str,
        supporting: List[MatchedRecordRef],
        unavailable: List[str],
        conflicting: List[MatchedRecordRef],
    ) -> str:
        """Generates a rule-based, deterministic explanation without calling external AI models."""
        sup_families = [s.source_family for s in supporting]
        sup_str = ", ".join(dict.fromkeys(sup_families)) if sup_families else "None"
        unav_str = ", ".join(unavailable) if unavailable else "None"

        parts = [
            f"Multi-source evidence fusion evaluated support score of {score:.1f}/100 ({tier})."
        ]

        if supporting:
            parts.append(f"Supporting evidence families matched: [{sup_str}].")
            for s in supporting:
                d_str = f"{s.distance_km:.1f} km away" if s.distance_km is not None else "co-located"
                t_str = f"{s.time_difference_minutes:+.0f}m time offset" if s.time_difference_minutes is not None else "static"
                parts.append(f"- {s.source_type} ({s.source_family}): {d_str}, {t_str}.")

        if conflicting:
            parts.append(f"Conflicting observations detected:")
            for c in conflicting:
                parts.append(f"- {c.source_type} ({c.source_family}): Matched within window but pollutant values remained within baseline.")

        if unavailable:
            parts.append(f"Sources unavailable or unobserved in window: [{unav_str}].")

        return " ".join(parts)

    def save_fusion_result(self, result: EvidenceFusionResult) -> Path:
        """Persists EvidenceFusionResult JSON artifact under data/processed/fusion/<fusion_id>.json."""
        target_path = self.fusion_dir / f"{result.fusion_id}.json"
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(result.model_dump_json(indent=2))
            logger.info(f"Persisted fusion result artifact to {target_path}")
            return target_path
        except Exception as e:
            raise FusionPersistenceError(f"Failed to persist fusion result artifact: {e}")

    def get_fusion_result(self, fusion_id: str) -> Optional[EvidenceFusionResult]:
        """Retrieves a persisted fusion result artifact by its fusion_id."""
        target_path = self.fusion_dir / f"{fusion_id}.json"
        if not target_path.exists():
            return None
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return EvidenceFusionResult.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to read fusion artifact {target_path}: {e}")
            return None

    def get_fusion_result_by_evidence_id(self, evidence_id: str) -> Optional[EvidenceFusionResult]:
        """Finds the most recent fusion result artifact anchored to evidence_id."""
        best_result = None
        for path in self.fusion_dir.glob("fu_*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("event_anchor_id") == evidence_id:
                    res = EvidenceFusionResult.model_validate(data)
                    if best_result is None or res.created_at > best_result.created_at:
                        best_result = res
            except Exception:
                continue
        return best_result
