from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from loguru import logger
from returns.pipeline import is_successful

from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services import sync_playlist
from src.shell.clients import ConcreteSpotifyClient, ConcreteSupabaseClient
from src.shell.logging_config import setup_logging


def get_supabase_client() -> SupabaseClient:
    """FastAPI dependency provider for the Supabase client."""
    return ConcreteSupabaseClient()


def get_spotify_client() -> SpotifyClient:
    """FastAPI dependency provider for the Spotify client."""
    return ConcreteSpotifyClient()


@asynccontextmanager
async def lifespan(_: object) -> AsyncGenerator[None, None]:  # pragma: no cover
    setup_logging()
    logger.info("FastAPI application starting up...")
    yield


app: FastAPI = FastAPI(lifespan=lifespan)


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
