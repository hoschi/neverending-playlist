from datetime import UTC, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from src.core.services.neverending_songs_service import (
    build_source_url_with_window,
    build_yesterday_utc_window_iso,
    resolve_source_window,
    source_from_url,
)


def test_build_yesterday_utc_window_iso_uses_previous_day() -> None:
    # Arrange
    window_end = datetime(2026, 4, 22, 6, 40, 0, tzinfo=UTC)

    # Act
    start_iso, end_iso = build_yesterday_utc_window_iso(
        window_end=window_end, window_minutes=20
    )

    # Assert
    assert start_iso == "2026-04-21T06:20:00Z"
    assert end_iso == "2026-04-21T06:40:00Z"


def test_build_source_url_with_window_replaces_existing_start_end() -> None:
    # Arrange
    source_url = (
        "https://iris-bob.loverad.io/search.json?station=110&foo=bar"
        "&start=old-start&end=old-end"
    )

    # Act
    resolved_url = build_source_url_with_window(
        source_url,
        "2026-04-21T07:00:00.000+02:00",
        "2026-04-21T22:00:00.000+02:00",
    )

    # Assert
    query = parse_qs(urlsplit(resolved_url).query)
    assert query["station"] == ["110"]
    assert query["foo"] == ["bar"]
    assert query["start"] == ["2026-04-21T07:00:00.000+02:00"]
    assert query["end"] == ["2026-04-21T22:00:00.000+02:00"]


def test_resolve_source_window_builds_yesterday_from_hhmm() -> None:
    # Arrange
    source_url = (
        "https://iris-bob.loverad.io/search.json?station=110&start=07:00&end=22:00"
    )
    now_local = datetime(2026, 4, 22, 8, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    # Act
    start_iso, end_iso = resolve_source_window(
        rest_url=source_url,
        fallback_start_iso="fallback-start",
        fallback_end_iso="fallback-end",
        now_local=now_local,
    )

    # Assert
    assert start_iso == "2026-04-21T07:00:00.000+02:00"
    assert end_iso == "2026-04-21T22:00:00.000+02:00"


def test_resolve_source_window_uses_explicit_datetime_params() -> None:
    # Arrange
    source_url = (
        "https://iris-bob.loverad.io/search.json?station=110&"
        "start=2026-04-21T07%3A00%3A00.000%2B02%3A00&"
        "end=2026-04-21T22%3A00%3A00.000%2B02%3A00"
    )

    # Act
    start_iso, end_iso = resolve_source_window(
        rest_url=source_url,
        fallback_start_iso="fallback-start",
        fallback_end_iso="fallback-end",
        now_local=None,
    )

    # Assert
    assert start_iso == "2026-04-21T07:00:00.000+02:00"
    assert end_iso == "2026-04-21T22:00:00.000+02:00"


def test_resolve_source_window_rejects_mixed_hhmm_and_datetime_formats() -> None:
    # Arrange
    source_url = (
        "https://iris-bob.loverad.io/search.json?station=110&"
        "start=07:00&"
        "end=2026-04-21T22%3A00%3A00.000%2B02%3A00"
    )

    # Act & Assert
    with pytest.raises(ValueError, match="Mixed start/end formats are not supported"):
        resolve_source_window(
            rest_url=source_url,
            fallback_start_iso="fallback-start",
            fallback_end_iso="fallback-end",
            now_local=None,
        )


def test_resolve_source_window_falls_back_when_params_missing() -> None:
    # Arrange
    source_url = "https://iris-bob.loverad.io/search.json?station=110"

    # Act
    start_iso, end_iso = resolve_source_window(
        rest_url=source_url,
        fallback_start_iso="fallback-start",
        fallback_end_iso="fallback-end",
        now_local=None,
    )

    # Assert
    assert start_iso == "fallback-start"
    assert end_iso == "fallback-end"


def test_source_from_url_raises_for_missing_domain() -> None:
    # Act & Assert
    with pytest.raises(ValueError, match="Invalid source URL without domain"):
        source_from_url("/search.json?station=110")
