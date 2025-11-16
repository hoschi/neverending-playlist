import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.core.config import Settings
from src.shell.api import app
from tests.mocks import MockSpotifyClient


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    """Required for pytest-asyncio."""
    return "asyncio"


@pytest.fixture
def client(mock_settings):  # noqa: ARG001
    """Provides a TestClient for testing FastAPI endpoints."""
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def enable_testing_mode():
    """Aktiviert den Testing-Modus für die gesamte Test-Session"""
    os.environ["TESTING"] = "true"
    yield
    if "TESTING" in os.environ:
        del os.environ["TESTING"]


@pytest.fixture
def test_settings():
    """Stellt validierte Test-Settings ohne .env Abhängigkeit bereit"""
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_key="test_key_12345",
        supabase_table="test_table",
        spotipy_client_id="test_client_id_xyz",
        spotipy_client_secret="test_client_secret_xyz",
        spotipy_redirect_uri="http://localhost:8000/callback",
        spotify_playlist_id="test_playlist_id_abc",
        spotify_refresh_token="gAAAAABpGuFQSE4nvwWCmEg-S967b70jzXjyS_Av5Jv1ICRsOGD5vamBJmYhuDtFa67th0XLIjB18g4hXOvMACaPyfPHaewNupSX2X3lpbGL6wRCZbWj25g=",  # Properly encrypted token
        encryption_key="9S2NLcv8dcrVHBaQQsy_rYwVYvGVBDisBm-LjExK5vg=",  # 32-byte Base64
        log_level="DEBUG",
        log_to_file=False,
        ssl_cert_path="ssl-test/cert.pem",
        ssl_key_path="ssl-test/key.pem",
    )


@pytest.fixture
def mock_spotify_client():
    """Provides a MockSpotifyClient instance for testing."""
    return MockSpotifyClient()


@pytest.fixture
def mock_settings(test_settings):
    """Mockt die globale Settings-Instanz mit Test-Werten"""
    from src.core.config import get_settings

    # Cache vor und nach jedem Test komplett leeren
    get_settings.cache_clear()
    with patch("src.core.config.Settings", return_value=test_settings):
        yield test_settings
    get_settings.cache_clear()


@pytest.fixture
def mock_get_spotify_client(mock_spotify_client):
    """Mockt die get_spotify_client Funktion um den Mock-Client zu verwenden."""

    with patch("src.shell.api.get_spotify_client", return_value=mock_spotify_client):
        yield mock_spotify_client
