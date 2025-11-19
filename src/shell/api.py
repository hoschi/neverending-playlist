import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

import spotipy  # type: ignore
import uvicorn
from dotenv import set_key
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from loguru import logger
from pydantic import SecretStr
from returns.pipeline import is_successful
from spotipy.oauth2 import SpotifyOAuth  # type: ignore

from src.core.config import get_settings
from src.core.models import (
    ClearPlayedTracksResponse,
    PlaylistClearFailure,
    UserAuthorization,
)
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.encryption_service import EncryptionService
from src.core.services.playlist_service import (
    clear_played_tracks_from_playlist,
    sync_playlist,
)
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
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=settings.spotify_redirect_uri,
        scope="playlist-modify-public playlist-modify-private user-read-playback-state",
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
        current_user = temp_client.current_user()
        if current_user is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to retrieve user information from Spotify.",
            )
        user_id = current_user["id"]

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
) -> Response:
    """API endpoint to synchronize the playlist."""
    result = await sync_playlist(supabase_client, spotify_client, max_count)

    if not is_successful(result):
        raise HTTPException(status_code=500, detail=str(result.failure()))

    sync_result = result.unwrap()

    failure_count = len(sync_result.failures)
    if failure_count > 0:
        return JSONResponse(
            status_code=status.HTTP_207_MULTI_STATUS,
            content={
                "successful": sync_result.successful,
                "not_found": sync_result.not_found,
                "errors": [
                    f"{failure.song_id}: {failure.reason}"
                    for failure in sync_result.failures
                ],
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "successful": sync_result.successful,
            "not_found": sync_result.not_found,
            "errors": [],
        },
    )


@app.post("/clear-played")
async def clear_played_endpoint(
    spotify_client: Annotated[SpotifyClient, Depends(get_spotify_client)],
) -> ClearPlayedTracksResponse:
    """API endpoint to clear played tracks from the configured playlist."""
    settings = get_settings()

    try:
        result = await clear_played_tracks_from_playlist(
            spotify_client, settings.spotify_playlist_id
        )
    except Exception as e:
        # Fallback for unknown error types
        raise HTTPException(
            status_code=500,
            detail={
                "error": "unknown_error",
                "message": "An unknown error occurred.",
                "details": str(e),
            },
        ) from e

    if not is_successful(result):
        error = result.failure()

        if error.error_code == PlaylistClearFailure.PLAYBACK_INACTIVE:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "playback_inactive",
                    "message": error.message,
                    "details": error.details,
                },
            )
        elif error.error_code == PlaylistClearFailure.WRONG_PLAYLIST:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "wrong_playlist",
                    "message": error.message,
                    "details": error.details,
                },
            )
        elif error.error_code == PlaylistClearFailure.ERROR:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "internal_server_error",
                    "message": error.message,
                    "details": error.details,
                },
            )

    deleted_count = result.unwrap()
    return ClearPlayedTracksResponse(deleted_count=deleted_count)


def main() -> None:  # pragma: no cover
    """Main function to run the FastAPI application."""
    settings = get_settings()
    # Create SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    print("STARTING with main config")
    ssl_context.load_cert_chain(settings.ssl_cert_path, settings.ssl_key_path)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=6361,
        ssl_certfile=settings.ssl_cert_path,
        ssl_keyfile=settings.ssl_key_path,
    )


if __name__ == "__main__":  # pragma: no cover
    main()
