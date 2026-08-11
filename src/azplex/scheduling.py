# ============================================================================
# SCHEDULING - Deterministic PIM activation window planning
# ============================================================================

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9 fallback
    ZoneInfo = None

DAILY = "daily"
WEEKDAYS = "weekdays"

# Recurring expansion is capped to keep request volume and horizon bounded.
MAX_HORIZON_DAYS = 30


class ScheduleError(Exception):
    """Raised when a schedule request is invalid."""


def _tzinfo(tz_name: Optional[str]):
    if not tz_name or tz_name.upper() == "UTC":
        return timezone.utc
    if ZoneInfo is None:
        raise ScheduleError("Timezone support requires Python 3.9+ (zoneinfo).")
    try:
        return ZoneInfo(tz_name)
    except Exception as error:
        raise ScheduleError(f"Unknown timezone '{tz_name}': {error}")


def normalize_to_utc(value: str, tz_name: Optional[str] = None) -> datetime:
    """Parses an ISO 8601 timestamp and returns a timezone-aware UTC datetime."""
    if not value or not value.strip():
        raise ScheduleError("timestamp is required")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as error:
        raise ScheduleError(f"Invalid ISO 8601 timestamp '{value}': {error}")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_tzinfo(tz_name))
    return parsed.astimezone(timezone.utc)


def _parse_hhmm(slot: str) -> Tuple[int, int]:
    try:
        hour_text, minute_text = slot.strip().split(":")
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, AttributeError):
        raise ScheduleError(f"Invalid time slot '{slot}'; expected HH:MM")
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ScheduleError(f"Time slot '{slot}' is out of range")
    return hour, minute


class Window:
    """A single planned activation window in UTC."""

    def __init__(self, start_utc: datetime, duration_hours: float):
        self.start_utc = start_utc
        self.duration_hours = duration_hours
        self.end_utc = start_utc + timedelta(hours=duration_hours)

    def overlaps(self, other: "Window") -> bool:
        return self.start_utc < other.end_utc and other.start_utc < self.end_utc

    def to_dict(self) -> dict:
        return {
            "start": self.start_utc.isoformat(),
            "end": self.end_utc.isoformat(),
            "duration_hours": self.duration_hours,
        }


def _dedupe_and_flag_overlaps(windows: List[Window]) -> Tuple[List[Window], List[dict]]:
    accepted: List[Window] = []
    skipped: List[dict] = []
    for window in sorted(windows, key=lambda w: w.start_utc):
        duplicate = any(existing.start_utc == window.start_utc for existing in accepted)
        if duplicate:
            skipped.append({"start": window.start_utc.isoformat(), "reason": "duplicate"})
            continue
        if any(window.overlaps(existing) for existing in accepted):
            skipped.append({"start": window.start_utc.isoformat(), "reason": "overlaps an earlier window"})
            continue
        accepted.append(window)
    return accepted, skipped


def build_one_shot_windows(
    timestamps: List[str],
    duration_hours: float,
    *,
    tz_name: Optional[str] = None,
    horizon_days: int = MAX_HORIZON_DAYS,
    now: Optional[datetime] = None,
) -> Tuple[List[Window], List[dict]]:
    """Builds windows for explicit future timestamps (schedule_activate mode)."""
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    horizon = reference + timedelta(days=_bounded_horizon(horizon_days))
    candidates: List[Window] = []
    skipped: List[dict] = []
    for stamp in timestamps or []:
        start = normalize_to_utc(stamp, tz_name)
        if start <= reference:
            skipped.append({"start": start.isoformat(), "reason": "timestamp is in the past"})
            continue
        if start > horizon:
            skipped.append({"start": start.isoformat(), "reason": "beyond scheduling horizon"})
            continue
        candidates.append(Window(start, duration_hours))
    accepted, overlap_skips = _dedupe_and_flag_overlaps(candidates)
    return accepted, skipped + overlap_skips


def build_recurring_windows(
    daily_times: List[str],
    duration_hours: float,
    *,
    pattern: str = DAILY,
    horizon_days: int = 7,
    tz_name: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Tuple[List[Window], List[dict]]:
    """Expands a daily or weekday recurring pattern into bounded UTC windows."""
    if pattern not in (DAILY, WEEKDAYS):
        raise ScheduleError(f"Unknown pattern '{pattern}'; use '{DAILY}' or '{WEEKDAYS}'")
    if not daily_times:
        raise ScheduleError("At least one daily time slot is required")

    tz = _tzinfo(tz_name)
    reference = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    local_today = reference.astimezone(tz).date()
    horizon = _bounded_horizon(horizon_days)
    slots = [_parse_hhmm(slot) for slot in daily_times]

    candidates: List[Window] = []
    skipped: List[dict] = []
    for day_offset in range(horizon + 1):
        day = local_today + timedelta(days=day_offset)
        if pattern == WEEKDAYS and day.weekday() >= 5:
            continue
        for hour, minute in slots:
            local_start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
            start = local_start.astimezone(timezone.utc)
            if start <= reference:
                continue
            candidates.append(Window(start, duration_hours))

    accepted, overlap_skips = _dedupe_and_flag_overlaps(candidates)
    return accepted, skipped + overlap_skips


def _bounded_horizon(horizon_days: int) -> int:
    if horizon_days < 1:
        raise ScheduleError("horizon_days must be at least 1")
    return min(horizon_days, MAX_HORIZON_DAYS)
