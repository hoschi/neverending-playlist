from datetime import datetime, timedelta


def should_run_daily_import(
    now_local: datetime,
    last_successful_run_at: datetime | None,
    scheduled_hour: int = 2,
) -> bool:
    """Returns whether the daily import should run at the current hourly check."""
    if not 0 <= scheduled_hour <= 23:
        raise ValueError("scheduled_hour must be between 0 and 23")
    if now_local.tzinfo is None:
        raise ValueError("now_local must be timezone-aware")

    if now_local.hour < scheduled_hour:
        return False

    if last_successful_run_at is None:
        return True

    last_success_local = last_successful_run_at.astimezone(now_local.tzinfo)
    return last_success_local.date() < now_local.date()


def seconds_until_next_hour(now_local: datetime) -> float:
    """Returns the seconds until the next full hour in local time."""
    if now_local.tzinfo is None:
        raise ValueError("now_local must be timezone-aware")

    next_hour = now_local.replace(minute=0, second=0, microsecond=0) + timedelta(
        hours=1
    )
    seconds = (next_hour - now_local).total_seconds()
    return max(seconds, 1.0)
