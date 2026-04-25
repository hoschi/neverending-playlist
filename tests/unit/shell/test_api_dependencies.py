from unittest.mock import patch

from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.encryption_service import EncryptionService
from src.shell.api import (
    get_encryption_service,
    get_song_request_client,
    get_spotify_client,
    get_spotify_oauth,
)


def test_get_song_request_client():
    """Test that the song-request client provider returns a valid client."""
    client = get_song_request_client()
    assert isinstance(client, SupabaseClient)


def test_get_spotify_client(mock_get_spotify_client):
    """
    Test that the Spotify client provider returns a valid client.
    Uses the mock client from conftest.py.
    """
    with patch(
        "src.shell.api.ConcreteSpotifyClient", return_value=mock_get_spotify_client
    ):
        client = get_spotify_client()
        assert isinstance(client, SpotifyClient)
        assert mock_get_spotify_client is not None


def test_get_spotify_oauth():
    """Test that the Spotify OAuth provider returns a valid manager."""
    from spotipy.oauth2 import SpotifyOAuth

    oauth_manager = get_spotify_oauth()
    assert isinstance(oauth_manager, SpotifyOAuth)


def test_get_encryption_service():
    """Test that the Encryption service provider returns a valid service."""
    service = get_encryption_service()
    assert isinstance(service, EncryptionService)
