from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def build_utc_window_iso(
    window_end: datetime | None,
    window_minutes: int,
) -> tuple[str, str]:
    """Builds an ISO UTC time window used for REST source queries."""
    if window_minutes <= 0:
        raise ValueError("window_minutes must be greater than 0")

    end_dt = window_end or datetime.now(UTC)
    normalized_end = end_dt.astimezone(UTC)
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


def source_from_url(rest_url: str) -> str:
    """Derives a source identifier from the URL domain."""
    domain = urlsplit(rest_url).netloc
    if not domain:
        raise ValueError(f"Invalid source URL without domain: {rest_url}")
    return domain
