from datetime import datetime, timedelta, timezone

from app.time_utils import ensure_utc, is_older_than, utc_now


def test_ensure_utc_naive():
    naive = datetime(2026, 6, 25, 12, 0, 0)
    result = ensure_utc(naive)
    assert result.tzinfo == timezone.utc


def test_is_older_than_with_mixed_tz():
    recent = datetime.now(timezone.utc) - timedelta(seconds=5)
    assert is_older_than(recent.replace(tzinfo=None), 30) is False
    old = datetime.now(timezone.utc) - timedelta(seconds=120)
    assert is_older_than(old.replace(tzinfo=None), 30) is True


def test_is_older_than_none():
    assert is_older_than(None, 30) is True
