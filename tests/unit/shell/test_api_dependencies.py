from unittest.mock import patch

import pytest
from spotipy.oauth2 import SpotifyOAuth  # type: ignore

from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.encryption_service import EncryptionService
from src.shell.api import (
    get_encryption_service,
    get_spotify_client,
    get_spotify_oauth,
    get_supabase_client,
)


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    """Mock the settings for all tests in this module."""
    monkeypatch.setenv("SUPABASE_URL", "http://test.com")
    monkeypatch.setenv("SUPABASE_KEY", "test_key")
    monkeypatch.setenv("SPOTIPY_CLIENT_ID", "test_id")
    monkeypatch.setenv("SPOTIPY_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("SPOTIPY_REDIRECT_URI", "http://localhost/callback")
    monkeypatch.setenv("SPOTIFY_PLAYLIST_ID", "playlist_id")
    # Generate a valid key for the encryption service
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    # This is needed for the ConcreteSpotifyClient
    monkeypatch.setenv("SPOTIFY_REFRESH_TOKEN", "encrypted_token")

    # We need to clear the lru_cache on get_settings
    # so it picks up the monkeypatched env vars.
    from src.core import config

    config.get_settings.cache_clear()


def test_get_supabase_client():
    """Test that the Supabase client provider returns a valid client."""
    client = get_supabase_client()
    assert isinstance(client, SupabaseClient)


def test_get_spotify_client():
    """
    Test that the Spotify client provider returns a valid client.
    This requires mocking the EncryptionService and the network call.
    """
    with (
        patch("src.shell.clients.EncryptionService") as mock_encryption_service_class,
        patch("spotipy.oauth2.SpotifyOAuth.refresh_access_token") as mock_refresh,
    ):
        mock_encryption_service_class.return_value.decrypt.return_value = (
            "decrypted_token"
        )
        mock_refresh.return_value = {"access_token": "new_token"}

        client = get_spotify_client()

    assert isinstance(client, SpotifyClient)
    mock_encryption_service_class.return_value.decrypt.assert_called_once()
    mock_refresh.assert_called_once_with("decrypted_token")


def test_get_spotify_oauth():
    """Test that the Spotify OAuth provider returns a valid manager."""
    oauth_manager = get_spotify_oauth()
    assert isinstance(oauth_manager, SpotifyOAuth)


def test_get_encryption_service():
    """Test that the Encryption service provider returns a valid service."""
    service = get_encryption_service()
    assert isinstance(service, EncryptionService)
