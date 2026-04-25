from loguru import logger
from returns.pipeline import is_successful
from returns.result import Result, Success

from src.core.models import (
    PlaylistClearError,
    PlaylistClearFailure,
    SongAdditionStatus,
    SongRequest,
    SyncFailure,
    SyncResult,
)
from src.core.protocols import SpotifyClient, SupabaseClient


async def fetch_pending_song_requests(
    song_request_client: SupabaseClient, max_count: int
) -> Result[list[SongRequest], Exception]:
    """Fetches a list of pending song requests from the configured backend."""
    logger.info(
        "Fetching up to {max_count} pending song requests.", max_count=max_count
    )
    result = await song_request_client.fetch_pending_song_requests(max_count)
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
    song_request_client: SupabaseClient, spotify_client: SpotifyClient, max_count: int
) -> Result[SyncResult, Exception]:
    """
    Orchestrates the synchronization of the playlist.
    Returns detailed results of the sync operation.
    """
    logger.info("Starting playlist synchronization.")

    requests_result = await fetch_pending_song_requests(song_request_client, max_count)
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
    update_result = await song_request_client.update_song_requests_as_added(
        song_requests_only
    )
    if not is_successful(update_result):
        logger.error(
            "Playlist sync failed during backend update: {error}",
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


async def _autofill_playlist(
    song_request_client: SupabaseClient,
    spotify_client: SpotifyClient,
    config_playlist_id: str,
    minimum_track_count: int,
) -> Result[int, PlaylistClearError]:
    """
    Autofill logic to maintain a minimum number of tracks in the playlist.

    This function ensures that the playlist always contains at least minimum_track_count tracks.
    It repeatedly fetches and adds new songs until either:
    - The minimum count is reached, OR
    - No more songs are available, OR
    - A real error occurs (not just "not found" songs)

    Args:
        song_request_client: The configured song request backend client
        spotify_client: The Spotify client to interact with the API
        config_playlist_id: The configured playlist ID from settings
        minimum_track_count: Minimum number of tracks that should be in the playlist

    Returns:
        Result[int, PlaylistClearError]:
            - Success(filled_count): Number of tracks successfully added during autofill
            - Failure(PlaylistClearError): Detailed error information
    """
    logger.info(
        "Starting autofill to maintain minimum {count} tracks in playlist",
        count=minimum_track_count,
    )

    max_attempts = 5  # Prevent infinite loops
    attempt = 0
    total_filled_count = 0

    while attempt < max_attempts:
        attempt += 1

        # Get current playlist state to check how many tracks we have
        playlist_items_result = await spotify_client.get_playlist_items(
            config_playlist_id
        )
        if not is_successful(playlist_items_result):
            logger.error(
                "Failed to get playlist items during autofill attempt {attempt}: {error}",
                attempt=attempt,
                error=playlist_items_result.failure(),
            )
            return Result.from_failure(
                PlaylistClearError(
                    error_code=PlaylistClearFailure.ERROR,
                    message="Failed to retrieve playlist items during autofill",
                    details=str(playlist_items_result.failure()),
                )
            )

        current_track_count = len(playlist_items_result.unwrap())

        # Check if we already have enough tracks
        if current_track_count >= minimum_track_count:
            logger.info(
                "Playlist has {current} tracks (minimum: {minimum}), autofill complete",
                current=current_track_count,
                minimum=minimum_track_count,
            )
            return Success(total_filled_count)

        # Calculate how many tracks we need to add in this attempt
        tracks_needed = minimum_track_count - current_track_count
        logger.info(
            "Playlist has {current} tracks, need {needed} more (attempt {attempt}/{max_attempts})",
            current=current_track_count,
            needed=tracks_needed,
            attempt=attempt,
            max_attempts=max_attempts,
        )

        # Use sync logic to fetch and add new songs
        try:
            sync_result = await sync_playlist(
                song_request_client, spotify_client, tracks_needed
            )

            if not is_successful(sync_result):
                logger.error(
                    "Autofill sync failed on attempt {attempt}: {error}",
                    attempt=attempt,
                    error=sync_result.failure(),
                )
                return Result.from_failure(
                    PlaylistClearError(
                        error_code=PlaylistClearFailure.ERROR,
                        message="Failed to autofill playlist after clearing",
                        details=str(sync_result.failure()),
                    )
                )

            # Get the successful sync result
            sync_data = sync_result.unwrap()

            # Analyze results
            successful_count = len(sync_data.successful)
            not_found_count = len(sync_data.not_found)
            error_count = len(sync_data.failures)

            logger.info(
                "Autofill attempt {attempt} results: {successful} songs added, {not_found} not found, {errors} errors",
                attempt=attempt,
                successful=successful_count,
                not_found=not_found_count,
                errors=error_count,
            )

            # Check for real errors - these should fail the entire operation
            if error_count > 0:
                logger.error(
                    "Autofill failed with {count} errors on attempt {attempt}",
                    count=error_count,
                    attempt=attempt,
                )
                return Result.from_failure(
                    PlaylistClearError(
                        error_code=PlaylistClearFailure.ERROR,
                        message=f"Autofill failed with {error_count} errors",
                        details=f"Failed to add {error_count} songs during autofill attempt {attempt}",
                    )
                )

            # Track the number of successfully added songs
            total_filled_count += successful_count

            # If no songs were successfully added and no errors, we might be out of songs
            if successful_count == 0:
                logger.warning(
                    "No songs successfully added in autofill attempt {attempt}, stopping autofill",
                    attempt=attempt,
                )
                break

        except Exception as e:
            logger.error(
                "Unexpected error during autofill attempt {attempt}: {error}",
                attempt=attempt,
                error=e,
            )
            return Result.from_failure(
                PlaylistClearError(
                    error_code=PlaylistClearFailure.ERROR,
                    message="Unexpected error during autofill",
                    details=str(e),
                )
            )

    logger.info(
        "Autofill completed after {attempt} attempts. Total tracks filled: {count}",
        attempt=attempt,
        count=total_filled_count,
    )

    return Success(total_filled_count)


async def clear_played_tracks_from_playlist(
    spotify_client: SpotifyClient,
    song_request_client: SupabaseClient,
    config_playlist_id: str,
    autofill_count: int | None,
) -> Result[dict[str, int], PlaylistClearError]:
    """
    Clears tracks that have been played from the beginning of a playlist.

    Args:
        spotify_client: The Spotify client to interact with the API
        song_request_client: The configured song request backend client
        config_playlist_id: The configured playlist ID from settings
        autofill_count: Number of tracks to maintain after clearing (None = no autofill)

    Returns:
        Result[dict[str, int], PlaylistClearError]:
            - Success(dict): Dictionary with 'deleted_count' and 'filled_count' keys
            - Failure(PlaylistClearError): Detailed error information
    """
    logger.info("Starting clear played tracks operation")

    # Get current playback state
    playback_result = await spotify_client.get_current_playback()
    if not is_successful(playback_result):
        logger.error(
            "Failed to get current playback: {error}", error=playback_result.failure()
        )
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.PLAYBACK_INACTIVE,
                message="Playback is inactive or unavailable",
                details="Failed to get current playback state from Spotify API",
            )
        )

    playback = playback_result.unwrap()

    # Check if playback is active (not None)
    if playback is None:
        logger.info("No active playback found")
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.PLAYBACK_INACTIVE,
                message="No active playback found",
                details="User is not currently playing any music",
            )
        )

    # Get current track and its context (playlist info)
    current_track = playback.get("item")
    if not current_track:
        logger.info("No current track in playback")
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.PLAYBACK_INACTIVE,
                message="No current track in playback",
                details="Spotify is not playing any track",
            )
        )

    current_context = playback.get("context")
    if not current_context:
        logger.info("No context in playback")
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.PLAYBACK_INACTIVE,
                message="No playback context available",
                details="Current playback has no context information",
            )
        )

    # Check if the context is a playlist and if it matches our configured playlist
    if current_context.get("type") != "playlist":
        logger.info("Current context is not a playlist")
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.WRONG_PLAYLIST,
                message="Current context is not a playlist",
                details=f"Context type: {current_context.get('type')}",
            )
        )

    current_playlist_uri = current_context.get("uri")
    if not current_playlist_uri:
        logger.info("No playlist URI in current context")
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.WRONG_PLAYLIST,
                message="No playlist URI in current context",
                details="Playlist context is missing URI information",
            )
        )

    # Extract playlist ID from URI (format: spotify:playlist:<id>)
    current_playlist_id = current_playlist_uri.split(":")[-1]

    # Verify this is the configured playlist
    if current_playlist_id != config_playlist_id:
        logger.info(
            "Current playlist {current} does not match configured playlist {config}",
            current=current_playlist_id,
            config=config_playlist_id,
        )
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.WRONG_PLAYLIST,
                message="Current playlist does not match configured playlist",
                details=f"Current: {current_playlist_id}, Configured: {config_playlist_id}",
            )
        )

    # Get all items from the playlist
    playlist_items_result = await spotify_client.get_playlist_items(config_playlist_id)
    if not is_successful(playlist_items_result):
        logger.error(
            "Failed to get playlist items: {error}",
            error=playlist_items_result.failure(),
        )
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.ERROR,
                message="Failed to retrieve playlist items",
                details=str(playlist_items_result.failure()),
            )
        )

    playlist_items = playlist_items_result.unwrap()

    # Find the position of the currently playing track
    current_track_uri = current_track.get("uri")
    if not current_track_uri:
        logger.error("Current track has no URI")
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.ERROR,
                message="Current track has no URI",
                details="The currently playing track is missing URI information",
            )
        )

    # Find the index of the currently playing track in the playlist
    current_track_index = None
    for index, item in enumerate(playlist_items):
        track = item.get("track")
        if track and track.get("uri") == current_track_uri:
            current_track_index = index
            break

    if current_track_index is None:
        logger.error("Could not find currently playing track in playlist")
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.ERROR,
                message="Currently playing track not found in playlist",
                details="The track that's currently playing is not present in the configured playlist",
            )
        )

    # Determine which tracks to remove (all tracks before the current one)
    tracks_to_remove = playlist_items[:current_track_index]

    if not tracks_to_remove:
        logger.info("No tracks to remove (already at the beginning of playlist)")
        return Success({"deleted_count": 0, "filled_count": 0})

    # Extract URIs of tracks to remove
    uris_to_remove = [
        item["track"]["uri"]
        for item in tracks_to_remove
        if item.get("track") and item["track"].get("uri")
    ]

    if not uris_to_remove:
        logger.info("No valid track URIs found to remove")
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.ERROR,
                message="No valid track URIs found to remove",
                details="Playlist tracks are missing valid URI information",
            )
        )

    # Remove the tracks from the playlist
    remove_result = await spotify_client.remove_items_from_playlist(
        config_playlist_id, uris_to_remove
    )
    if not is_successful(remove_result):
        logger.error(
            "Failed to remove tracks from playlist: {error}",
            error=remove_result.failure(),
        )
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.ERROR,
                message="Failed to remove tracks from playlist",
                details=str(remove_result.failure()),
            )
        )

    removed_count = len(uris_to_remove)
    logger.info(
        "Successfully removed {count} tracks from playlist", count=removed_count
    )

    # Autofill logic - only if configured and value is valid
    filled_count = 0
    if autofill_count is not None and autofill_count > 0:
        autofill_result = await _autofill_playlist(
            song_request_client, spotify_client, config_playlist_id, autofill_count
        )

        if not is_successful(autofill_result):
            return Result.from_failure(autofill_result.failure())
        filled_count = autofill_result.unwrap()
    else:
        logger.debug("Autofill disabled or set to 0, skipping refill")

    return Success(
        {
            "deleted_count": removed_count,
            "filled_count": filled_count,
        }
    )
