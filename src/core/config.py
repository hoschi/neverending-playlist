from functools import lru_cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads and validates application settings from environment variables."""

    log_level: str = "INFO"
    log_to_file: bool = False

    # Supabase
    supabase_url: str
    supabase_key: str

    # Spotify
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    spotify_playlist_id: str

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached instance of the application settings.
    This function is decorated with @lru_cache to ensure the settings
    are loaded only once.
    """
    return Settings()  # type: ignore[call-arg]
