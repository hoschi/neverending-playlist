from loguru import logger
from returns.pipeline import is_successful
from returns.result import Result, Success

from src.core.models import (
    SongAdditionStatus,
    SongRequest,
    SyncFailure,
    SyncResult,
)
from src.core.protocols import SpotifyClient, SupabaseClient


async def fetch_pending_song_requests(
    supabase_client: SupabaseClient, max_count: int
) -> Result[list[SongRequest], Exception]:
    """Fetches a list of pending song requests from Supabase."""
    logger.info(
        "Fetching up to {max_count} pending song requests.", max_count=max_count
    )
    result = await supabase_client.fetch_pending_song_requests(max_count)
    if is_successful(result):
        requests = result.unwrap()
        logger.debug(
            "Fetched {count} pending song requests",
            count=len(requests),
        )
    return result


async def add_songs_to_spotify(
    spotify_client: SpotifyClient, songs: list[SongRequest]
) -> Result[list[tuple[SongRequest, SongAdditionStatus]], Exception]:
    """Adds a list of songs to the Spotify playlist and returns individual status for each song."""
    if not songs:
        return Success([])
    logger.info("Adding {count} songs to Spotify.", count=len(songs))

    result = await spotify_client.add_songs_to_playlist(songs)
    if not is_successful(result):
        return result

    # Log individual song statuses
    song_statuses = result.unwrap()
    logger.debug("Individual song statuses: {statuses}", statuses=song_statuses)
    successful_count = sum(
        1 for _, status in song_statuses if status.value == "SUCCESS"
    )
    not_found_count = sum(
        1 for _, status in song_statuses if status.value == "NOT_FOUND"
    )
    error_count = sum(1 for _, status in song_statuses if status.value == "ERROR")

    logger.info(
        "Song addition results: {successful} successful, {not_found} not found, {errors} errors",
        successful=successful_count,
        not_found=not_found_count,
        errors=error_count,
    )

    return result


async def sync_playlist(
    supabase_client: SupabaseClient, spotify_client: SpotifyClient, max_count: int
) -> Result[SyncResult, Exception]:
    """
    Orchestrates the synchronization of the playlist.
    Returns detailed results of the sync operation.
    """
    logger.info("Starting playlist synchronization.")

    requests_result = await fetch_pending_song_requests(supabase_client, max_count)
    if not is_successful(requests_result):
        logger.error(
            "Playlist sync failed during fetch: {error}",
            error=requests_result.failure(),
        )
        return Result.from_failure(requests_result.failure())

    requests = requests_result.unwrap()
    logger.debug("After unwrap: found {count} requests", count=len(requests))
    if not requests:
        logger.info("No pending requests found.")
        return Success(SyncResult(success_count=0, failure_count=0, failures=[]))

    add_result = await add_songs_to_spotify(spotify_client, requests)
    if not is_successful(add_result):
        logger.error(
            "Playlist sync failed during spotify add: {error}",
            error=add_result.failure(),
        )
        return Result.from_failure(add_result.failure())

    # Extract song statuses from the add_result
    song_statuses = add_result.unwrap()
    logger.debug(
        "After unwrap add_result: song_statuses count = {count}",
        count=len(song_statuses),
    )
    # Extract only the SongRequest objects for the database update
    song_requests_only = [song_request for song_request, _ in song_statuses]
    update_result = await supabase_client.update_song_requests_as_added(
        song_requests_only
    )
    if not is_successful(update_result):
        logger.error(
            "Playlist sync failed during supabase update: {error}",
            error=update_result.failure(),
        )
        return Result.from_failure(update_result.failure())

    # Categorize songs by status
    successful = [
        song_request
        for song_request, status in song_statuses
        if status.value == "SUCCESS"
    ]
    not_found = [
        song_request
        for song_request, status in song_statuses
        if status.value == "NOT_FOUND"
    ]
    errors = [
        song_request
        for song_request, status in song_statuses
        if status.value == "ERROR"
    ]

    success_count = len(successful)
    successful_ids = [str(req.id) for req in successful]
    not_found_ids = [str(req.id) for req in not_found]
    error_ids = [str(req.id) for req in errors]
    failures = [
        SyncFailure(song_id=str(req.id), reason="Not found") for req in not_found
    ] + [SyncFailure(song_id=str(req.id), reason="Error") for req in errors]
    failure_count = len(failures)

    logger.info("Playlist sync successful. Added {count} songs.", count=success_count)
    return Success(
        SyncResult(
            success_count=success_count,
            failure_count=failure_count,
            failures=failures,
            successful=successful_ids,
            not_found=not_found_ids,
            errors=error_ids,
        )
    )
