from datetime import datetime, timedelta


def should_run_daily_import(
    now_local: datetime,
    last_successful_run_at: datetime | None,
    scheduled_hour: int = 2,
) -> bool:
    """Returns whether the daily import should run at the scheduled local hour."""
    if not 0 <= scheduled_hour <= 23:
        raise ValueError("scheduled_hour must be between 0 and 23")
    if now_local.tzinfo is None:
        raise ValueError("now_local must be timezone-aware")

    if now_local.hour != scheduled_hour:
        return False

    if last_successful_run_at is None:
        return True

    last_success_local = last_successful_run_at.astimezone(now_local.tzinfo)
    return last_success_local.date() < now_local.date()


def seconds_until_scheduled_hour(
    now_local: datetime,
    scheduled_hour: int = 2,
) -> float:
    """Returns the seconds until the next scheduled local hour."""
    if not 0 <= scheduled_hour <= 23:
        raise ValueError("scheduled_hour must be between 0 and 23")
    if now_local.tzinfo is None:
        raise ValueError("now_local must be timezone-aware")

    target = now_local.replace(hour=scheduled_hour, minute=0, second=0, microsecond=0)
    if now_local >= target:
        target += timedelta(days=1)
    seconds = (target - now_local).total_seconds()
    return max(seconds, 1.0)
