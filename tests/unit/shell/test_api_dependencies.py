from types import SimpleNamespace
from unittest.mock import patch

from src.core.protocols import SpotifyClient
from src.core.services.encryption_service import EncryptionService
from src.shell.api import (
    get_encryption_service,
    get_song_request_client,
    get_spotify_client,
    get_spotify_oauth,
)


def test_get_song_request_client_returns_sqlite_backend_client():
    """Test that the song-request client provider picks SQLite backend when configured."""
    sqlite_client = object()

    with (
        patch(
            "src.shell.api.get_settings",
            return_value=SimpleNamespace(song_source="SQLITE"),
        ),
        patch("src.shell.api.ConcreteSqliteClient", return_value=sqlite_client) as mock_sqlite,
        patch("src.shell.api.ConcreteSupabaseClient") as mock_supabase,
    ):
        client = get_song_request_client()

    assert client is sqlite_client
    mock_sqlite.assert_called_once_with()
    mock_supabase.assert_not_called()


def test_get_song_request_client_returns_supabase_backend_client():
    """Test that the song-request client provider picks Supabase backend when configured."""
    supabase_client = object()

    with (
        patch(
            "src.shell.api.get_settings",
            return_value=SimpleNamespace(song_source="SUPABASE"),
        ),
        patch("src.shell.api.ConcreteSupabaseClient", return_value=supabase_client) as mock_supabase,
        patch("src.shell.api.ConcreteSqliteClient") as mock_sqlite,
    ):
        client = get_song_request_client()

    assert client is supabase_client
    mock_supabase.assert_called_once_with()
    mock_sqlite.assert_not_called()


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
