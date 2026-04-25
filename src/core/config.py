import os
from functools import lru_cache
from typing import ClassVar, Literal

from loguru import logger
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BYTES_PER_GB = 1024 * 1024 * 1024


class Settings(BaseSettings):
    """Loads and validates application settings from environment variables."""

    log_level: str = "INFO"
    log_to_file: bool = False

    # Supabase
    supabase_url: str | None = None
    supabase_key: str | None = None
    supabase_table: str | None = None

    # Song source backend
    song_source: Literal["SUPABASE", "SQLITE"] = "SQLITE"

    # SQLite backend
    sqlite_db_path: str = "neverending_songs.db"
    sqlite_max_size_gb: int = 10

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

    @property
    def sqlite_max_size_bytes(self) -> int:
        """Returns the configured SQLite max size in bytes for consumers."""
        return self.sqlite_max_size_gb * BYTES_PER_GB

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_sqlite_max_size_bytes(cls, data: object) -> object:
        """Converts deprecated SQLITE_MAX_SIZE_BYTES env var into sqlite_max_size_gb."""
        if not isinstance(data, dict):
            return data

        if "sqlite_max_size_gb" in data or "SQLITE_MAX_SIZE_GB" in os.environ:
            return data

        legacy_bytes_value = os.environ.get("SQLITE_MAX_SIZE_BYTES")
        if legacy_bytes_value is None:
            return data

        try:
            legacy_bytes = int(legacy_bytes_value)
        except ValueError as error:
            raise ValueError("SQLITE_MAX_SIZE_BYTES must be an integer number of bytes") from error

        if legacy_bytes <= 0:
            raise ValueError("SQLITE_MAX_SIZE_BYTES must be greater than 0")

        size_gb = max(1, (legacy_bytes + BYTES_PER_GB - 1) // BYTES_PER_GB)
        logger.warning(
            "SQLITE_MAX_SIZE_BYTES is deprecated; use SQLITE_MAX_SIZE_GB instead. "
            "Converted {bytes} bytes to {gb} GB.",
            bytes=legacy_bytes,
            gb=size_gb,
        )
        data["sqlite_max_size_gb"] = size_gb
        return data

    @field_validator("sqlite_max_size_gb", mode="before")
    @classmethod
    def _validate_sqlite_max_size_gb(cls, value: int | str) -> int:
        """Parses SQLite max size from GB input and validates positivity."""
        size_gb = int(value)
        if size_gb <= 0:
            raise ValueError("SQLITE_MAX_SIZE_GB must be greater than 0")
        return size_gb

    @model_validator(mode="after")
    def _validate_song_source_requirements(self) -> "Settings":
        """Ensures source-specific settings are present."""
        if self.song_source == "SUPABASE":
            missing_fields = [
                field_name
                for field_name, value in (
                    ("SUPABASE_URL", self.supabase_url),
                    ("SUPABASE_KEY", self.supabase_key),
                    ("SUPABASE_TABLE", self.supabase_table),
                )
                if not value
            ]
            if missing_fields:
                missing = ", ".join(missing_fields)
                raise ValueError(
                    f"Missing required settings for SUPABASE source: {missing}"
                )

        return self

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
