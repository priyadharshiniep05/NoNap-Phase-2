"""Timezone utilities for NoNap (Indian Standard Time - Asia/Kolkata)."""

from datetime import datetime, timezone
import zoneinfo

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    """Return current datetime in Asia/Kolkata timezone."""
    return datetime.now(IST)


def now_utc() -> datetime:
    """Return current datetime in UTC timezone."""
    return datetime.now(timezone.utc)


def format_ist_time(dt: datetime) -> str:
    """Format datetime as 'HH:mm IST' (24-hour)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%H:%M IST")


def format_ist_datetime(dt: datetime) -> str:
    """Format datetime as 'DD MMM YYYY, HH:mm:ss IST'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST)
    return ist_dt.strftime("%d %b %Y, %H:%M:%S IST")


def to_ist_iso(dt: datetime) -> str:
    """Convert datetime to ISO 8601 string in Asia/Kolkata timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).isoformat()


def ist_wall_now() -> datetime:
    """Naive IST wall-clock time, the storage convention for alert_logs,
    session_stats and devices in ops_db (SQLite drops tzinfo)."""
    return datetime.now(IST).replace(tzinfo=None)


def as_ist(dt: datetime | None) -> datetime | None:
    """Attach IST to a stored naive IST wall-clock value (aware values are converted)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=IST)
    return dt.astimezone(IST)


def ist_midnight_wall() -> datetime:
    """Naive IST wall-clock for 00:00 today, for "today" queries."""
    return ist_wall_now().replace(hour=0, minute=0, second=0, microsecond=0)
