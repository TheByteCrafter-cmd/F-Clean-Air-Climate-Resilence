"""
VayuDrishti — Temporal Parsing & Timestamp Alignment Utilities

Provides strict UTC timestamp parsing, record sorting by station and timestamp,
deduplication, and irregular interval detection.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple, Union


def parse_utc_timestamp(ts: Union[str, datetime]) -> datetime:
    """
    Parses a timestamp string or datetime object into a normalized UTC datetime.

    Raises:
        ValueError: If timestamp format is invalid.
    """
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts.astimezone(timezone.utc)

    if not isinstance(ts, str):
        raise ValueError(f"Invalid timestamp type: {type(ts)}")

    clean_ts = ts.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean_ts)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception as e:
        raise ValueError(f"Could not parse timestamp string '{ts}': {e}")


def sort_and_deduplicate_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Normalizes timestamps to UTC, sorts by (station_id, timestamp), and deduplicates
    exact (station_id, pollutant, timestamp) combinations.
    """
    if not records:
        return []

    processed: List[Dict[str, Any]] = []
    seen_keys: Set[Tuple[str, str, str]] = set()

    for r in records:
        station_id = str(r.get("station_id") or r.get("source_record_id") or "UNKNOWN_STATION")
        pollutant = str(r.get("pollutant", "PM2.5")).upper().replace(".", "").replace(" ", "")
        raw_t = r.get("timestamp") or r.get("datetime")
        if not raw_t:
            continue

        try:
            dt = parse_utc_timestamp(raw_t)
        except ValueError:
            continue

        dedup_key = (station_id, pollutant, dt.isoformat())
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        r_copy = dict(r)
        r_copy["station_id"] = station_id
        r_copy["pollutant"] = pollutant
        r_copy["parsed_timestamp"] = dt
        processed.append(r_copy)

    # Sort strictly by station_id, pollutant, timestamp
    processed.sort(key=lambda x: (x["station_id"], x["pollutant"], x["parsed_timestamp"]))
    return processed


def detect_irregular_intervals(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyzes timestamp gaps across records per station to detect irregular sampling intervals.
    """
    if not records:
        return {
            "has_irregular_intervals": False,
            "station_gaps": {},
            "median_gap_hours": None,
        }

    station_groups: Dict[str, List[datetime]] = {}
    for r in records:
        st_id = r["station_id"]
        dt = r.get("parsed_timestamp") or parse_utc_timestamp(r["timestamp"])
        if st_id not in station_groups:
            station_groups[st_id] = []
        station_groups[st_id].append(dt)

    all_gaps_hours: List[float] = []
    station_gaps_summary: Dict[str, Dict[str, Any]] = {}

    for st_id, dts in station_groups.items():
        sorted_dts = sorted(dts)
        gaps: List[float] = []
        for i in range(1, len(sorted_dts)):
            diff_h = (sorted_dts[i] - sorted_dts[i - 1]).total_seconds() / 3600.0
            gaps.append(round(diff_h, 2))
            all_gaps_hours.append(diff_h)

        is_irregular = any(g != 1.0 for g in gaps) if gaps else False
        station_gaps_summary[st_id] = {
            "count": len(sorted_dts),
            "gaps_count": len(gaps),
            "min_gap_h": min(gaps) if gaps else None,
            "max_gap_h": max(gaps) if gaps else None,
            "is_irregular": is_irregular,
        }

    all_gaps_hours.sort()
    med_gap = (
        all_gaps_hours[len(all_gaps_hours) // 2]
        if all_gaps_hours
        else None
    )

    has_irregular = any(summary["is_irregular"] for summary in station_gaps_summary.values())

    return {
        "has_irregular_intervals": has_irregular,
        "station_gaps": station_gaps_summary,
        "median_gap_hours": round(med_gap, 2) if med_gap is not None else None,
    }
