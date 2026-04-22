from functools import lru_cache
from typing import ClassVar, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads and validates application settings from environment variables."""

    log_level: str = "INFO"
    log_to_file: bool = False

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_table: str

    # Song source backend
    song_source: Literal["SUPABASE", "SQLITE"] = "SQLITE"

    # SQLite backend
    sqlite_db_path: str = "neverending_songs.db"
    sqlite_max_size_bytes: int = 10 * 1024 * 1024 * 1024

    # Source URLs for NeverendingSongs import (must be provided via env)
    song_source_rest_urls: list[str]

    # Scheduler debug override
    debug_sync_at_startup: bool = False

    # Notifications
    enable_mac_notifications: bool = False

    # Spotify
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    spotify_playlist_id: str

    # Spotify User Authorization
    spotify_refresh_token: str | None = None

    # Playlist Autofill (optional)
    playlist_autofill_count: int | None = None

    # Watch Service (optional)
    watch_service_timeout_minutes: int = 10

    # Encryption
    encryption_key: str

    # SSL
    ssl_cert_path: str = "ssl/cert.pem"
    ssl_key_path: str = "ssl/key.pem"

    @field_validator("sqlite_max_size_bytes", mode="before")
    @classmethod
    def _convert_sqlite_max_size_gb_to_bytes(cls, value: int | str) -> int:
        """Parses SQLITE_MAX_SIZE_BYTES as GB and converts to bytes."""
        size_gb = int(value)
        if size_gb <= 0:
            raise ValueError("SQLITE_MAX_SIZE_BYTES must be greater than 0 GB")
        return size_gb * 1024 * 1024 * 1024

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached instance of the application settings.
    This function is decorated with @lru_cache to ensure the settings
    are loaded only once.
    """
    return Settings()  # type: ignore[call-arg]
