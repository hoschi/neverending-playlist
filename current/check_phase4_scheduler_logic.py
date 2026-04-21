from datetime import UTC, datetime

from src.core.services.neverending_scheduler_service import (
    seconds_until_next_hour,
    should_run_daily_import,
)


def main() -> None:
    tz = UTC

    scenarios = [
        (
            "before_2am_no_last_run",
            datetime(2026, 4, 22, 1, 0, tzinfo=tz),
            None,
        ),
        (
            "exactly_2am_no_last_run",
            datetime(2026, 4, 22, 2, 0, tzinfo=tz),
            None,
        ),
        (
            "after_2am_same_day_already_success",
            datetime(2026, 4, 22, 15, 0, tzinfo=tz),
            datetime(2026, 4, 22, 2, 5, tzinfo=tz),
        ),
        (
            "after_2am_missed_today_last_success_yesterday",
            datetime(2026, 4, 22, 10, 0, tzinfo=tz),
            datetime(2026, 4, 21, 2, 1, tzinfo=tz),
        ),
    ]

    for name, now_local, last_success in scenarios:
        should_run = should_run_daily_import(
            now_local=now_local,
            last_successful_run_at=last_success,
            scheduled_hour=2,
        )
        wait_seconds = int(seconds_until_next_hour(now_local))
        print(
            f"{name}: should_run={should_run}, wait_seconds_to_next_hour={wait_seconds}"
        )


if __name__ == "__main__":
    main()
