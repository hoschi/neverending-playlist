from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

import spotipy  # type: ignore
import uvicorn
from dotenv import set_key
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from loguru import logger
from pydantic import SecretStr
from returns.pipeline import is_successful
from spotipy.oauth2 import SpotifyOAuth  # type: ignore

from src.core.config import get_settings
from src.core.models import UserAuthorization
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.encryption_service import EncryptionService
from src.core.services.playlist_service import sync_playlist
from src.shell.clients import ConcreteSpotifyClient, ConcreteSupabaseClient
from src.shell.logging_config import setup_logging


def get_supabase_client() -> SupabaseClient:
    """FastAPI dependency provider for the Supabase client."""
    return ConcreteSupabaseClient()


def get_spotify_client() -> SpotifyClient:
    """FastAPI dependency provider for the Spotify client."""
    return ConcreteSpotifyClient()


def get_spotify_oauth() -> SpotifyOAuth:
    """FastAPI dependency provider for the SpotifyOAuth manager."""
    settings = get_settings()
    return SpotifyOAuth(
        client_id=settings.spotipy_client_id,
        client_secret=settings.spotipy_client_secret,
        redirect_uri=settings.spotipy_redirect_uri,
        scope="playlist-modify-public playlist-modify-private",
    )


def get_encryption_service() -> EncryptionService:
    """FastAPI dependency provider for the EncryptionService."""
    settings = get_settings()
    return EncryptionService(key=SecretStr(settings.encryption_key))


@asynccontextmanager
async def lifespan(_: object) -> AsyncGenerator[None, None]:  # pragma: no cover
    setup_logging()
    logger.info("FastAPI application starting up...")
    yield


app: FastAPI = FastAPI(lifespan=lifespan)


@app.get("/login", status_code=307)
def login(
    oauth_manager: Annotated[SpotifyOAuth, Depends(get_spotify_oauth)],
) -> RedirectResponse:
    """Redirects the user to the Spotify authorization page."""
    auth_url = oauth_manager.get_authorize_url()
    return RedirectResponse(auth_url)


@app.get("/callback")
def callback(
    code: str,
    oauth_manager: Annotated[SpotifyOAuth, Depends(get_spotify_oauth)],
    encryption_service: Annotated[EncryptionService, Depends(get_encryption_service)],
) -> dict[str, str]:
    """
    Handles the callback from Spotify, saves the refresh token,
    and returns a success message.
    """
    try:
        token_info = oauth_manager.get_access_token(code, check_cache=False)
        if not token_info or "refresh_token" not in token_info:
            raise HTTPException(
                status_code=400, detail="Could not retrieve refresh token."
            )

        # Create a temporary client to get the user's ID
        temp_client = spotipy.Spotify(auth=token_info["access_token"])
        user_id = temp_client.current_user()["id"]

        auth_data = UserAuthorization(
            spotify_user_id=user_id,
            access_token=token_info["access_token"],
            refresh_token=token_info["refresh_token"],
            expires_at=token_info["expires_at"],
            scope=token_info["scope"],
        )

        encrypted_token = encryption_service.encrypt(auth_data.refresh_token)
        set_key(".env", "SPOTIFY_REFRESH_TOKEN", encrypted_token)

        logger.info("Successfully authenticated and stored refresh token.")
        return {"status": "success", "message": "Successfully authenticated."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during the callback: {e}")
        raise HTTPException(
            status_code=500, detail="An internal error occurred."
        ) from e


@app.post("/sync-playlist")
async def sync_playlist_endpoint(
    supabase_client: Annotated[SupabaseClient, Depends(get_supabase_client)],
    spotify_client: Annotated[SpotifyClient, Depends(get_spotify_client)],
    max_count: int = Query(10, gt=0, le=50),
) -> dict[str, str | int]:
    """API endpoint to synchronize the playlist."""
    result = await sync_playlist(supabase_client, spotify_client, max_count)

    if not is_successful(result):
        raise HTTPException(status_code=500, detail=str(result.failure()))

    return {"status": "success", "songs_added": result.unwrap()}


def main() -> None:  # pragma: no cover
    """Main function to run the FastAPI application."""
    uvicorn.run(app, host="0.0.0.0", port=6361)


if __name__ == "__main__":  # pragma: no cover
    main()
