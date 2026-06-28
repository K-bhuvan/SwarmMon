from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_older_than(value: datetime | None, seconds: int, *, now: datetime | None = None) -> bool:
    if value is None:
        return True
    reference = ensure_utc(now or utc_now())
    return ensure_utc(value) < reference - timedelta(seconds=seconds)
