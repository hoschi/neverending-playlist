from loguru import logger
from returns.pipeline import is_successful
from returns.result import Result, Success

from src.core.models import SongRequest
from src.core.protocols import SpotifyClient, SupabaseClient


async def fetch_pending_song_requests(
    supabase_client: SupabaseClient, max_count: int
) -> Result[list[SongRequest], Exception]:
    """Fetches a list of pending song requests from Supabase."""
    logger.info(
        "Fetching up to {max_count} pending song requests.", max_count=max_count
    )
    return await supabase_client.fetch_pending_song_requests(max_count)


async def add_songs_to_spotify(
    spotify_client: SpotifyClient, songs: list[SongRequest]
) -> Result[None, Exception]:
    """Adds a list of songs to the Spotify playlist."""
    if not songs:
        return Success(None)
    logger.info("Adding {count} songs to Spotify.", count=len(songs))
    return await spotify_client.add_songs_to_playlist(songs)


async def sync_playlist(
    supabase_client: SupabaseClient, spotify_client: SpotifyClient, max_count: int
) -> Result[int, Exception]:
    """
    Orchestrates the synchronization of the playlist.
    Returns the number of songs added.
    """
    logger.info("Starting playlist synchronization.")

    requests_result = await fetch_pending_song_requests(supabase_client, max_count)
    if not is_successful(requests_result):
        logger.error(
            "Playlist sync failed during fetch: {error}",
            error=requests_result.failure(),
        )
        return requests_result.map(len)

    requests = requests_result.unwrap()
    if not requests:
        logger.info("No pending requests found.")
        return Success(0)

    add_result = await add_songs_to_spotify(spotify_client, requests)
    if not is_successful(add_result):
        logger.error(
            "Playlist sync failed during spotify add: {error}",
            error=add_result.failure(),
        )
        return add_result.map(lambda _: len(requests))

    update_result = await supabase_client.update_song_requests_as_added(requests)
    if not is_successful(update_result):
        logger.error(
            "Playlist sync failed during supabase update: {error}",
            error=update_result.failure(),
        )
        return update_result.map(lambda _: len(requests))

    count = len(requests)
    logger.info("Playlist sync successful. Added {count} songs.", count=count)
    return Success(count)
