import pytest
from pydantic import ValidationError

from src.core.config import Settings


def test_settings_allow_missing_supabase_fields_for_sqlite_source() -> None:
    settings = Settings(
        song_source="SQLITE",
        song_source_rest_urls=["https://example.com/source.json?station=110"],
        spotify_client_id="test-client-id",
        spotify_client_secret="dummy",
        spotify_redirect_uri="https://localhost:6361/callback",
        spotify_playlist_id="test-playlist-id",
        encryption_key="dummy-encryption-key-for-settings-tests",
    )

    assert settings.song_source == "SQLITE"
    assert settings.supabase_url is None
    assert settings.supabase_key is None
    assert settings.supabase_table is None


def test_settings_require_supabase_fields_for_supabase_source() -> None:
    with pytest.raises(ValidationError, match="Missing required settings for SUPABASE source"):
        Settings(
            song_source="SUPABASE",
            song_source_rest_urls=["https://example.com/source.json?station=110"],
            spotify_client_id="test-client-id",
            spotify_client_secret="dummy",
            spotify_redirect_uri="https://localhost:6361/callback",
            spotify_playlist_id="test-playlist-id",
            encryption_key="dummy-encryption-key-for-settings-tests",
        )
