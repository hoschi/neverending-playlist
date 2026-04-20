from urllib.parse import urlsplit


def source_from_url(rest_url: str) -> str:
    """Derives a source identifier from the URL domain."""
    domain = urlsplit(rest_url).netloc
    if not domain:
        raise ValueError(f"Invalid source URL without domain: {rest_url}")
    return domain
