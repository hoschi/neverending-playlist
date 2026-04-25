from datetime import UTC, datetime, time, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def build_yesterday_utc_window_iso(
    window_end: datetime | None,
    window_minutes: int,
) -> tuple[str, str]:
    """Builds an ISO UTC time window for yesterday relative to now."""
    if window_minutes <= 0:
        raise ValueError("window_minutes must be greater than 0")

    end_dt = window_end or datetime.now(UTC)
    normalized_end = end_dt.astimezone(UTC) - timedelta(days=1)
    normalized_start = normalized_end - timedelta(minutes=window_minutes)

    start_iso = normalized_start.isoformat().replace("+00:00", "Z")
    end_iso = normalized_end.isoformat().replace("+00:00", "Z")
    return start_iso, end_iso


def build_source_url_with_window(rest_url: str, start_iso: str, end_iso: str) -> str:
    """Adds or replaces start/end query params in a source URL."""
    split_result = urlsplit(rest_url)
    query_pairs = parse_qsl(split_result.query, keep_blank_values=True)
    filtered_pairs = [
        (key, value) for key, value in query_pairs if key not in {"start", "end"}
    ]
    filtered_pairs.extend([("start", start_iso), ("end", end_iso)])
    encoded_query = urlencode(filtered_pairs, doseq=True)

    return urlunsplit(
        (
            split_result.scheme,
            split_result.netloc,
            split_result.path,
            encoded_query,
            split_result.fragment,
        )
    )


def build_yesterday_local_window_from_time(
    start_time_hhmm: str,
    end_time_hhmm: str,
    now_local: datetime | None,
) -> tuple[str, str]:
    """Builds ISO datetimes for yesterday using local HH:MM clock times."""
    start_clock = _parse_hhmm(start_time_hhmm)
    end_clock = _parse_hhmm(end_time_hhmm)

    if now_local is None:
        reference_local = datetime.now().astimezone()
    elif now_local.tzinfo is None:
        reference_local = now_local.astimezone()
    else:
        reference_local = now_local
    yesterday = (reference_local - timedelta(days=1)).date()

    start_dt = datetime.combine(yesterday, start_clock, tzinfo=reference_local.tzinfo)
    end_dt = datetime.combine(yesterday, end_clock, tzinfo=reference_local.tzinfo)
    return (
        start_dt.isoformat(timespec="milliseconds"),
        end_dt.isoformat(timespec="milliseconds"),
    )


def resolve_source_window(
    rest_url: str,
    fallback_start_iso: str,
    fallback_end_iso: str,
    now_local: datetime | None,
) -> tuple[str, str]:
    """Resolves source window from URL params or falls back to computed defaults."""
    split_result = urlsplit(rest_url)
    query_values = dict(parse_qsl(split_result.query, keep_blank_values=True))

    start_param = query_values.get("start")
    end_param = query_values.get("end")
    if start_param and end_param:
        start_is_hhmm = _is_hhmm(start_param)
        end_is_hhmm = _is_hhmm(end_param)

        if start_is_hhmm != end_is_hhmm:
            raise ValueError(
                "Mixed start/end formats are not supported: use either HH:MM for both "
                "or full timestamps for both"
            )

        if start_is_hhmm and end_is_hhmm:
            return build_yesterday_local_window_from_time(
                start_param,
                end_param,
                now_local=now_local,
            )
        return start_param, end_param

    return fallback_start_iso, fallback_end_iso


def _is_hhmm(value: str) -> bool:
    try:
        _parse_hhmm(value)
    except ValueError:
        return False
    return True


def _parse_hhmm(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def source_from_url(rest_url: str) -> str:
    """Derives a source identifier from the URL domain."""
    domain = urlsplit(rest_url).netloc
    if not domain:
        raise ValueError(f"Invalid source URL without domain: {rest_url}")
    return domain
