from datetime import datetime, timedelta, timezone

from src.core.services.neverending_scheduler_service import (
    seconds_until_scheduled_hour,
    should_run_daily_import,
)

TZ = timezone(timedelta(hours=2))


def test_should_run_daily_import_only_at_scheduled_hour() -> None:
    at_two = datetime(2026, 8, 26, 2, 0, tzinfo=TZ)
    at_ten = datetime(2026, 8, 26, 10, 0, tzinfo=TZ)

    assert should_run_daily_import(at_two, last_successful_run_at=None) is True
    assert should_run_daily_import(at_ten, last_successful_run_at=None) is False


def test_should_run_daily_import_skips_when_already_succeeded_today() -> None:
    now = datetime(2026, 8, 26, 2, 5, tzinfo=TZ)
    last_success = datetime(2026, 8, 26, 2, 0, tzinfo=TZ)

    assert should_run_daily_import(now, last_successful_run_at=last_success) is False


def test_seconds_until_scheduled_hour_waits_until_2am_same_day() -> None:
    now = datetime(2026, 8, 26, 1, 30, 0, tzinfo=TZ)

    seconds = seconds_until_scheduled_hour(now, scheduled_hour=2)

    assert seconds == 30 * 60


def test_seconds_until_scheduled_hour_after_2am_waits_until_next_day() -> None:
    now = datetime(2026, 8, 26, 10, 0, 0, tzinfo=TZ)

    seconds = seconds_until_scheduled_hour(now, scheduled_hour=2)

    next_run = datetime(2026, 8, 27, 2, 0, 0, tzinfo=TZ)
    assert seconds == (next_run - now).total_seconds()
