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


@pytest.fixture(autouse=True)
def mock_environment():
    """Automatisch Mock-Environment für alle Tests."""
    # Cache vor dem Test leeren
    from src.core.config import get_settings

    get_settings.cache_clear()

    # Mock Settings definieren
    test_settings = Settings(
        supabase_url="https://test.supabase.co",
        supabase_key="test_key_12345",
        supabase_table="test_table",
        spotify_client_id="test_client_id_xyz",
        spotify_client_secret="test_client_secret_xyz",
        spotify_redirect_uri="http://localhost:8000/callback",
        spotify_playlist_id="7AVVVQ6TJMTA17a2e6ncFr",  # Fixed: Match test expectations
        spotify_refresh_token="gAAAAABpGuFQSE4nvwWCmEg-S967b70jzXjyS_Av5Jv1ICRsOGD5vamBJmYhuDtFa67th0XLIjB18g4hXOvMACaPyfPHaewNupSX2X3lpbGL6wRCZbWj25g=",  # Properly encrypted token
        playlist_autofill_count=150,  # Enable autofill for tests
        encryption_key="9S2NLcv8dcrVHBaQQsy_rYwVYvGVBDisBm-LjExK5vg=",  # 32-byte Base64
        log_level="DEBUG",
        log_to_file=False,
        ssl_cert_path="ssl-test/cert.pem",
        ssl_key_path="ssl-test/key.pem",
    )

    # Settings und get_settings mocken
    with (
        patch("src.core.config.Settings", return_value=test_settings),
        patch("src.core.config.get_settings", return_value=test_settings),
    ):
        yield test_settings

    # Cleanup nach dem Test
    get_settings.cache_clear()


@pytest.fixture
def client(mock_environment):  # noqa: ARG001
    """Provides a TestClient for testing FastAPI endpoints."""
    return TestClient(app)


@pytest.fixture
def test_settings():
    """Stellt validierte Test-Settings ohne .env Abhängigkeit bereit"""
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_key="test_key_12345",
        supabase_table="test_table",
        spotify_client_id="test_client_id_xyz",
        spotify_client_secret="test_client_secret_xyz",
        spotify_redirect_uri="http://localhost:8000/callback",
        spotify_playlist_id="7AVVVQ6TJMTA17a2e6ncFr",  # Fixed: Match test expectations
        spotify_refresh_token="gAAAAABpGuFQSE4nvwWCmEg-S967b70jzXjyS_Av5Jv1ICRsOGD5vamBJmYhuDtFa67th0XLIjB18g4hXOvMACaPyfPHaewNupSX2X3lpbGL6wRCZbWj25g=",  # Properly encrypted token
        playlist_autofill_count=150,  # Enable autofill for tests
        encryption_key="9S2NLcv8dcrVHBaQQsy_rYwVYvGVBDisBm-LjExK5vg=",  # 32-byte Base64
        log_level="DEBUG",
        log_to_file=False,
        ssl_cert_path="ssl-test/cert.pem",
        ssl_key_path="ssl-test/key.pem",
    )


@pytest.fixture
def mock_settings_no_autofill():
    """Mock Settings ohne Autofill für Tests die Edge-Cases prüfen"""
    return Settings(
        supabase_url="https://test.supabase.co",
        supabase_key="test_key_12345",
        supabase_table="test_table",
        spotify_client_id="test_client_id_xyz",
        spotify_client_secret="test_client_secret_xyz",
        spotify_redirect_uri="http://localhost:8000/callback",
        spotify_playlist_id="7AVVVQ6TJMTA17a2e6ncFr",
        spotify_refresh_token="gAAAAABpGuFQSE4nvwWCmEg-S967b70jzXjyS_Av5Jv1ICRsOGD5vamBJmYhuDtFa67th0XLIjB18g4hXOvMACaPyfPHaewNupSX2X3lpbGL6wRCZbWj25g=",
        playlist_autofill_count=None,  # Disabled autofill
        encryption_key="9S2NLcv8dcrVHBaQQsy_rYwVYvGVBDisBm-LjExK5vg=",
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
