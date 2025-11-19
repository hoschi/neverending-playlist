from loguru import logger
from returns.pipeline import is_successful
from returns.result import Result, Success

from src.core.models import (
    PlaylistClearFailure,
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
    logger.debug(
        "Individual song statuses fetched: {statuses}", statuses=len(song_statuses)
    )
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
        return Success(SyncResult(failures=[], successful=[], not_found=[]))

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
    failures = [SyncFailure(song_id=str(req.id), reason="Error") for req in errors]

    logger.info("Playlist sync successful. Added {count} songs.", count=success_count)
    return Success(
        SyncResult(
            failures=failures,
            successful=successful_ids,
            not_found=not_found_ids,
        )
    )


async def clear_played_tracks_from_playlist(
    spotify_client: SpotifyClient, config_playlist_id: str
) -> Result[int, PlaylistClearFailure]:
    """
    Clears tracks that have been played from the beginning of a playlist.

    Args:
        spotify_client: The Spotify client to interact with the API
        config_playlist_id: The configured playlist ID from settings

    Returns:
        Result[int, PlaylistClearFailure]:
            - Success(int): Number of tracks removed
            - Failure(PlaylistClearFailure): Error indicating why operation failed
    """
    logger.info("Starting clear played tracks operation")

    # Get current playback state
    playback_result = await spotify_client.get_current_playback()
    if not is_successful(playback_result):
        logger.error(
            "Failed to get current playback: {error}", error=playback_result.failure()
        )
        return Result.from_failure(PlaylistClearFailure.PLAYBACK_INACTIVE)

    playback = playback_result.unwrap()

    # Check if playback is active (not None)
    if playback is None:
        logger.info("No active playback found")
        return Result.from_failure(PlaylistClearFailure.PLAYBACK_INACTIVE)

    # Get current track and its context (playlist info)
    current_track = playback.get("item")
    if not current_track:
        logger.info("No current track in playback")
        return Result.from_failure(PlaylistClearFailure.PLAYBACK_INACTIVE)

    current_context = playback.get("context")
    if not current_context:
        logger.info("No context in playback")
        return Result.from_failure(PlaylistClearFailure.PLAYBACK_INACTIVE)

    # Check if the context is a playlist and if it matches our configured playlist
    if current_context.get("type") != "playlist":
        logger.info("Current context is not a playlist")
        return Result.from_failure(PlaylistClearFailure.WRONG_PLAYLIST)

    current_playlist_uri = current_context.get("uri")
    if not current_playlist_uri:
        logger.info("No playlist URI in current context")
        return Result.from_failure(PlaylistClearFailure.WRONG_PLAYLIST)

    # Extract playlist ID from URI (format: spotify:playlist:<id>)
    current_playlist_id = current_playlist_uri.split(":")[-1]

    # Verify this is the configured playlist
    if current_playlist_id != config_playlist_id:
        logger.info(
            "Current playlist {current} does not match configured playlist {config}",
            current=current_playlist_id,
            config=config_playlist_id,
        )
        return Result.from_failure(PlaylistClearFailure.WRONG_PLAYLIST)

    # Get all items from the playlist
    playlist_items_result = await spotify_client.get_playlist_items(config_playlist_id)
    if not is_successful(playlist_items_result):
        logger.error(
            "Failed to get playlist items: {error}",
            error=playlist_items_result.failure(),
        )
        return Result.from_failure(PlaylistClearFailure.PLAYBACK_INACTIVE)

    playlist_items = playlist_items_result.unwrap()

    # Find the position of the currently playing track
    current_track_uri = current_track.get("uri")
    if not current_track_uri:
        logger.error("Current track has no URI")
        # TODO: should be PlaylistClearFailure.ERROR
        return Result.from_failure(PlaylistClearFailure.PLAYBACK_INACTIVE)

    # Find the index of the currently playing track in the playlist
    current_track_index = None
    for index, item in enumerate(playlist_items):
        track = item.get("track")
        if track and track.get("uri") == current_track_uri:
            current_track_index = index
            break

    if current_track_index is None:
        logger.error("Could not find currently playing track in playlist")
        # TODO: should be PlaylistClearFailure.ERROR
        return Result.from_failure(PlaylistClearFailure.PLAYBACK_INACTIVE)

    # Determine which tracks to remove (all tracks before the current one)
    tracks_to_remove = playlist_items[:current_track_index]

    if not tracks_to_remove:
        logger.info("No tracks to remove (already at the beginning of playlist)")
        # TODO: should be PlaylistClearFailure.PLAYBACK_INACTIVE
        return Success(0)

    # Extract URIs of tracks to remove
    uris_to_remove = [
        item["track"]["uri"]
        for item in tracks_to_remove
        if item.get("track") and item["track"].get("uri")
    ]

    if not uris_to_remove:
        logger.info("No valid track URIs found to remove")
        # TODO: should be PlaylistClearFailure.ERROR
        return Success(0)

    # Remove the tracks from the playlist
    remove_result = await spotify_client.remove_items_from_playlist(
        config_playlist_id, uris_to_remove
    )
    if not is_successful(remove_result):
        logger.error(
            "Failed to remove tracks from playlist: {error}",
            error=remove_result.failure(),
        )
        # TODO: should be PlaylistClearFailure.ERROR
        return Result.from_failure(PlaylistClearFailure.PLAYBACK_INACTIVE)

    removed_count = len(uris_to_remove)
    logger.info(
        "Successfully removed {count} tracks from playlist", count=removed_count
    )

    return Success(removed_count)
