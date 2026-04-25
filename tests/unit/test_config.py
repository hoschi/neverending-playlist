import pytest
from pydantic import ValidationError

from src.core.config import BYTES_PER_GB, Settings


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


def test_settings_uses_legacy_sqlite_max_size_bytes_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SQLITE_MAX_SIZE_GB", raising=False)
    monkeypatch.setenv("SQLITE_MAX_SIZE_BYTES", str(10 * BYTES_PER_GB))

    settings = Settings(
        song_source="SQLITE",
        song_source_rest_urls=["https://example.com/source.json?station=110"],
        spotify_client_id="test-client-id",
        spotify_client_secret="dummy",
        spotify_redirect_uri="https://localhost:6361/callback",
        spotify_playlist_id="test-playlist-id",
        encryption_key="dummy-encryption-key-for-settings-tests",
    )

    assert settings.sqlite_max_size_gb == 10
    assert settings.sqlite_max_size_bytes == 10 * BYTES_PER_GB


def test_settings_prefers_sqlite_max_size_gb_over_legacy_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SQLITE_MAX_SIZE_GB", "3")
    monkeypatch.setenv("SQLITE_MAX_SIZE_BYTES", str(10 * BYTES_PER_GB))

    settings = Settings(
        song_source="SQLITE",
        song_source_rest_urls=["https://example.com/source.json?station=110"],
        spotify_client_id="test-client-id",
        spotify_client_secret="dummy",
        spotify_redirect_uri="https://localhost:6361/callback",
        spotify_playlist_id="test-playlist-id",
        encryption_key="dummy-encryption-key-for-settings-tests",
    )

    assert settings.sqlite_max_size_gb == 3
    assert settings.sqlite_max_size_bytes == 3 * BYTES_PER_GB
