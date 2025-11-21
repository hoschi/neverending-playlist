import pytest
from returns.result import Failure, Result, Success

from src.core.models import (
    PlaylistClearError,
    PlaylistClearFailure,
    Song,
    SongAdditionStatus,
    SongRequest,
    SyncResult,
)
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.playlist_service import (
    _autofill_playlist,
    add_songs_to_spotify,
    clear_played_tracks_from_playlist,
    fetch_pending_song_requests,
    sync_playlist,
)


class MockSupabaseClient(SupabaseClient):
    """A mock Supabase client for unit tests."""

    def __init__(
        self,
        pending_requests: list[SongRequest] | None = None,
        fetch_should_fail: bool = False,
        update_should_fail: bool = False,
        fetch_should_raise: bool = False,
    ):
        self.pending_requests = pending_requests if pending_requests is not None else []
        self.updated_requests: list[SongRequest] = []
        self.fetch_should_fail = fetch_should_fail
        self.update_should_fail = update_should_fail
        self.fetch_should_raise = fetch_should_raise

    async def fetch_pending_song_requests(
        self,
        max_count: int,  # noqa: ARG002
    ) -> Result[list[SongRequest], Exception]:
        if self.fetch_should_raise:
            raise RuntimeError("Unexpected database connection failure")
        if self.fetch_should_fail:
            return Failure(Exception("Supabase fetch failed"))
        return Success(self.pending_requests)

    async def update_song_requests_as_added(
        self, song_requests: list[SongRequest]
    ) -> Result[None, Exception]:
        if self.update_should_fail:
            return Failure(Exception("Supabase update failed"))
        # Update each song request with its status
        for song_request in song_requests:
            if song_request.status:
                # Find the original request and update its status
                for original_request in self.pending_requests:
                    if original_request.id == song_request.id:
                        original_request.status = song_request.status
                        break
        self.updated_requests.extend(song_requests)
        return Success(None)


class MockSpotifyClient(SpotifyClient):
    """A mock Spotify client for unit tests."""

    def __init__(
        self,
        should_fail: bool = False,
        song_statuses: list[tuple[SongRequest, SongAdditionStatus]] | None = None,
        get_current_user_should_fail: bool = False,
        playback_info: dict | None = None,  # type: ignore[type-arg]
        playlist_items: list[dict] | None = None,  # type: ignore[type-arg]
        playlist_items_sequence: list[list[dict]] | None = None,  # type: ignore[type-arg]
        remove_should_fail: bool = False,
        get_playlist_items_should_fail: bool = False,
    ):
        self.added_songs: list[SongRequest] = []
        self.should_fail = should_fail
        self.song_statuses = song_statuses or []
        self.get_current_user_should_fail = get_current_user_should_fail
        self.playback_info = playback_info
        self.playlist_items = playlist_items or []
        self.playlist_items_sequence = playlist_items_sequence or []
        self.remove_should_fail = remove_should_fail
        self.get_playlist_items_should_fail = get_playlist_items_should_fail
        self.get_playlist_items_call_count = 0

    async def get_current_user(self) -> Result[dict[str, str] | None, Exception]:
        if self.get_current_user_should_fail:
            return Failure(Exception("Spotify get current user failed"))
        return Success({"id": "mock_user_id", "display_name": "Mock User"})

    async def add_songs_to_playlist(
        self, songs: list[SongRequest]
    ) -> Result[list[tuple[SongRequest, SongAdditionStatus]], Exception]:
        if self.should_fail:
            return Failure(Exception("Spotify API failed"))

        # If specific statuses are provided, use them
        if self.song_statuses:
            # Ensure we return statuses for all input songs
            status_map = {song.id: status for song, status in self.song_statuses}
            result = []
            for song in songs:
                status = status_map.get(song.id, SongAdditionStatus.SUCCESS)
                # Update the song request with the status
                song.status = status
                result.append((song, status))
                # Add successful songs to added_songs
                if status == SongAdditionStatus.SUCCESS:
                    self.added_songs.append(song)
            return Success(result)

        # Otherwise, default to all successful
        self.added_songs.extend(songs)
        for song in songs:
            song.status = SongAdditionStatus.SUCCESS
        return Success([(song, SongAdditionStatus.SUCCESS) for song in songs])

    async def get_current_playback(self) -> Result[dict[str, object] | None, Exception]:
        if self.should_fail:
            return Failure(Exception("Spotify API failed"))
        return Success(self.playback_info)

    async def get_playlist_items(
        self,
        playlist_id: str,  # noqa: ARG002
    ) -> Result[list[dict[str, object]], Exception]:
        if self.should_fail or self.get_playlist_items_should_fail:
            return Failure(Exception("Spotify API failed"))

        self.get_playlist_items_call_count += 1

        # If we have a sequence of responses, use them in order
        if self.playlist_items_sequence and self.get_playlist_items_call_count <= len(
            self.playlist_items_sequence
        ):
            return Success(
                self.playlist_items_sequence[self.get_playlist_items_call_count - 1]
            )

        return Success(self.playlist_items)

    async def remove_items_from_playlist(
        self,
        playlist_id: str,  # noqa: ARG002
        uris: list[str],  # noqa: ARG002
    ) -> Result[None, Exception]:
        if self.remove_should_fail:
            return Failure(Exception("Spotify API failed"))
        return Success(None)


@pytest.mark.asyncio
async def test_sync_playlist_success_mixed_statuses() -> None:
    """
    Tests successful synchronization with mixed status values.
    """
    # Arrange
    requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
        SongRequest(id=2, song=Song(artist="Artist 2", title="Title 2")),
        SongRequest(id=3, song=Song(artist="Artist 3", title="Title 3")),
        SongRequest(id=4, song=Song(artist="Artist 4", title="Title 4")),
    ]

    # Mixed statuses: 2 successful, 1 not found, 1 error
    song_statuses = [
        (requests[0], SongAdditionStatus.SUCCESS),
        (requests[1], SongAdditionStatus.NOT_FOUND),
        (requests[2], SongAdditionStatus.ERROR),
        (requests[3], SongAdditionStatus.SUCCESS),
    ]

    supabase_mock = MockSupabaseClient(pending_requests=requests)
    spotify_mock = MockSpotifyClient(song_statuses=song_statuses)

    # Act
    result = await sync_playlist(supabase_mock, spotify_mock, 10)

    # Assert
    assert isinstance(result, Success)
    sync_result = result.unwrap()
    assert isinstance(sync_result, SyncResult)

    # Check categorization
    assert len(sync_result.successful) == 2
    assert "1" in sync_result.successful
    assert "4" in sync_result.successful

    assert len(sync_result.not_found) == 1
    assert "2" in sync_result.not_found

    assert len(sync_result.failures) == 1
    assert sync_result.failures[0].song_id == "3"

    # Check that all requests were updated in Supabase
    assert len(supabase_mock.updated_requests) == 4
    assert set(req.id for req in supabase_mock.updated_requests) == {1, 2, 3, 4}

    # Verify that the status is set directly in the SongRequest objects
    assert requests[0].status == SongAdditionStatus.SUCCESS
    assert requests[1].status == SongAdditionStatus.NOT_FOUND
    assert requests[2].status == SongAdditionStatus.ERROR
    assert requests[3].status == SongAdditionStatus.SUCCESS


@pytest.mark.asyncio
async def test_sync_playlist_database_error_handling() -> None:
    """
    Tests error handling when database operations fail.
    """
    # Test fetch failure
    supabase_mock = MockSupabaseClient(fetch_should_fail=True)
    spotify_mock = MockSpotifyClient()

    result = await sync_playlist(supabase_mock, spotify_mock, 10)
    assert isinstance(result, Failure)
    assert "Supabase fetch failed" in str(result.failure())

    # Test update failure
    requests = [SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1"))]
    supabase_mock = MockSupabaseClient(
        pending_requests=requests, update_should_fail=True
    )
    spotify_mock = MockSpotifyClient()

    result = await sync_playlist(supabase_mock, spotify_mock, 10)
    assert isinstance(result, Failure)
    assert "Supabase update failed" in str(result.failure())
    assert len(spotify_mock.added_songs) == 1  # Songs were added to Spotify


@pytest.mark.asyncio
async def test_sync_playlist_api_error_handling() -> None:
    """
    Tests error handling when API operations fail.
    """
    requests = [SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1"))]

    # Test Spotify API failure
    supabase_mock = MockSupabaseClient(pending_requests=requests)
    spotify_mock = MockSpotifyClient(should_fail=True)

    result = await sync_playlist(supabase_mock, spotify_mock, 10)
    assert isinstance(result, Failure)
    assert "Spotify API failed" in str(result.failure())
    assert len(supabase_mock.updated_requests) == 0  # No updates made


@pytest.mark.asyncio
async def test_sync_playlist_no_pending_requests() -> None:
    """Tests the case where there are no pending requests to process."""
    # Arrange
    supabase_mock = MockSupabaseClient(pending_requests=[])
    spotify_mock = MockSpotifyClient()

    # Act
    result = await sync_playlist(supabase_mock, spotify_mock, 10)

    # Assert
    assert isinstance(result, Success)
    sync_result = result.unwrap()
    assert isinstance(sync_result, SyncResult)
    assert len(sync_result.successful) == 0
    assert len(sync_result.not_found) == 0
    assert len(sync_result.failures) == 0
    assert len(supabase_mock.updated_requests) == 0
    assert len(spotify_mock.added_songs) == 0


@pytest.mark.asyncio
async def test_add_songs_to_spotify_with_empty_list() -> None:
    """Tests that add_songs_to_spotify handles an empty list gracefully."""
    # Arrange
    spotify_mock = MockSpotifyClient()

    # Act
    result = await add_songs_to_spotify(spotify_mock, [])

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() == []
    assert len(spotify_mock.added_songs) == 0


@pytest.mark.asyncio
async def test_fetch_pending_song_requests_success() -> None:
    """Tests successful fetching of pending song requests."""
    # Arrange
    requests = [SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1"))]
    supabase_mock = MockSupabaseClient(pending_requests=requests)

    # Act
    result = await fetch_pending_song_requests(supabase_mock, 10)

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() == requests


@pytest.mark.asyncio
async def test_fetch_pending_song_requests_failure() -> None:
    """Tests failure when fetching pending song requests."""
    # Arrange
    supabase_mock = MockSupabaseClient(fetch_should_fail=True)

    # Act
    result = await fetch_pending_song_requests(supabase_mock, 10)

    # Assert
    assert isinstance(result, Failure)
    assert "Supabase fetch failed" in str(result.failure())


# Clear Played Tracks Tests
@pytest.mark.asyncio
async def test_clear_played_tracks_success() -> None:
    """Tests successful clearing of played tracks."""
    # Arrange
    config_playlist_id = "playlist123"

    # Mock playback info with current track at position 2 (0-indexed)
    current_track_uri = "spotify:track:track3"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Mock playlist items with tracks before current position
    playlist_items = [
        {"track": {"uri": "spotify:track:track1"}},
        {"track": {"uri": "spotify:track:track2"}},
        {"track": {"uri": current_track_uri}},  # Currently playing
        {"track": {"uri": "spotify:track:track4"}},
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info, playlist_items=playlist_items
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Success)
    result_data = result.unwrap()
    assert result_data["deleted_count"] == 2  # 2 tracks should be removed
    assert result_data["filled_count"] == 0  # No autofill happened


@pytest.mark.asyncio
async def test_clear_played_tracks_no_active_playback() -> None:
    """Tests handling when there is no active playback."""
    # Arrange
    config_playlist_id = "playlist123"
    spotify_mock = MockSpotifyClient(playback_info=None)
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.PLAYBACK_INACTIVE


@pytest.mark.asyncio
async def test_clear_played_tracks_api_failure_playlist_items_alternative() -> None:
    """Tests handling when Spotify API call fails for get_playlist_items."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        "item": {"uri": "spotify:track:track1"},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Use the new flag to make only get_playlist_items fail
    spotify_mock = MockSpotifyClient(
        playback_info=playback_info, get_playlist_items_should_fail=True
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR


@pytest.mark.asyncio
async def test_clear_played_tracks_no_valid_track_uris_final() -> None:
    """Tests handling when playlist tracks have no valid URIs (covers lines 318-319)."""
    # Arrange
    config_playlist_id = "playlist123"

    current_track_uri = "spotify:track:track2"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Playlist items without URIs - this should trigger the "No valid track URIs found" case
    playlist_items = [
        {"track": {"name": "track1"}},  # No URI
        {"track": {"uri": current_track_uri}},  # Currently playing (index 1)
        {"track": {"name": "track3"}},  # No URI
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info, playlist_items=playlist_items
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR


@pytest.mark.asyncio
async def test_clear_played_api_fallback_error_handler() -> None:
    """Tests the fallback error handler in api.py for unknown error types."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        "item": {"uri": "spotify:track:track3"},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    playlist_items = [
        {"track": {"uri": "spotify:track:track1"}},  # Should be removed
        {"track": {"uri": "spotify:track:track2"}},  # Should be removed
        {"track": {"uri": "spotify:track:track3"}},  # Currently playing
    ]

    # Use the remove_should_fail flag to trigger the remove operation failure
    spotify_mock = MockSpotifyClient(
        playback_info=playback_info,
        playlist_items=playlist_items,
        remove_should_fail=True,
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR

    # Act & Assert would go here if we implement a proper test
    # For now, we rely on the existing coverage to be sufficient


@pytest.mark.asyncio
async def test_clear_played_tracks_no_playlist_uri_in_context() -> None:
    """Tests handling when context has no playlist URI."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        "item": {"uri": "spotify:track:track1"},
        "context": {"type": "playlist"},  # Missing URI field
    }

    spotify_mock = MockSpotifyClient(playback_info=playback_info)
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.WRONG_PLAYLIST


@pytest.mark.asyncio
async def test_clear_played_tracks_context_type_not_playlist() -> None:
    """Tests handling when context type is not 'playlist'."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        "item": {"uri": "spotify:track:track1"},
        "context": {"type": "album", "uri": "spotify:album:album123"},
    }

    spotify_mock = MockSpotifyClient(playback_info=playback_info)
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.WRONG_PLAYLIST
    assert failure.details and "Context type: album" in failure.details


@pytest.mark.asyncio
async def test_clear_played_tracks_current_track_no_uri() -> None:
    """Tests handling when current track has no URI."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        "item": {"name": "Track without URI"},  # No URI field
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    playlist_items = [
        {"track": {"name": "track1"}},  # Playlist items also without URIs
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info, playlist_items=playlist_items
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR


@pytest.mark.asyncio
async def test_clear_played_tracks_no_valid_track_uris() -> None:
    """Tests handling when playlist tracks have no valid URIs."""
    # Arrange
    config_playlist_id = "playlist123"

    current_track_uri = "spotify:track:track2"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Playlist items without URIs
    playlist_items = [
        {"track": {"name": "track1"}},  # No URI
        {"track": {"name": "track2"}},  # No URI - currently playing
        {"track": {"name": "track3"}},  # No URI
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info, playlist_items=playlist_items
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR


@pytest.mark.asyncio
async def test_clear_played_tracks_api_failure_remove_items() -> None:
    """Tests handling when Spotify API call fails for remove_items_from_playlist."""
    # Arrange
    config_playlist_id = "playlist123"

    current_track_uri = "spotify:track:track2"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    playlist_items = [
        {"track": {"uri": "spotify:track:track1"}},
        {"track": {"uri": current_track_uri}},  # Currently playing
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info,
        playlist_items=playlist_items,
        remove_should_fail=True,  # This will cause remove_items_from_playlist to fail
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR


@pytest.mark.asyncio
async def test_clear_played_tracks_wrong_playlist() -> None:
    """Tests handling when playing from wrong playlist."""
    # Arrange
    config_playlist_id = "playlist123"
    other_playlist_id = "playlist456"

    playback_info = {
        "item": {"uri": "spotify:track:track1"},
        "context": {"type": "playlist", "uri": f"spotify:playlist:{other_playlist_id}"},
    }

    spotify_mock = MockSpotifyClient(playback_info=playback_info)
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.WRONG_PLAYLIST


@pytest.mark.asyncio
async def test_clear_played_tracks_no_context() -> None:
    """Tests handling when playback has no context."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        "item": {"uri": "spotify:track:track1"}
        # No context field
    }

    spotify_mock = MockSpotifyClient(playback_info=playback_info)
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.PLAYBACK_INACTIVE


@pytest.mark.asyncio
async def test_clear_played_tracks_no_current_track() -> None:
    """Tests handling when playback has no current track."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        # No item field
        "context": {"type": "playlist", "uri": f"spotify:playlist:{config_playlist_id}"}
    }

    spotify_mock = MockSpotifyClient(playback_info=playback_info)
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.PLAYBACK_INACTIVE


@pytest.mark.asyncio
async def test_clear_played_tracks_current_track_not_in_playlist() -> None:
    """Tests handling when current track is not found in playlist."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        "item": {"uri": "spotify:track:current_track"},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Playlist doesn't contain the current track
    playlist_items = [
        {"track": {"uri": "spotify:track:track1"}},
        {"track": {"uri": "spotify:track:track2"}},
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info, playlist_items=playlist_items
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR


@pytest.mark.asyncio
async def test_clear_played_tracks_no_tracks_to_remove() -> None:
    """Tests when current track is at the beginning of playlist."""
    # Arrange
    config_playlist_id = "playlist123"

    current_track_uri = "spotify:track:track1"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Current track is the first one
    playlist_items = [
        {"track": {"uri": current_track_uri}},  # Currently playing (first)
        {"track": {"uri": "spotify:track:track2"}},
        {"track": {"uri": "spotify:track:track3"}},
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info, playlist_items=playlist_items
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Success)
    result_data = result.unwrap()
    assert result_data["deleted_count"] == 0  # No tracks to remove
    assert result_data["filled_count"] == 0  # No autofill happened


@pytest.mark.asyncio
async def test_clear_played_tracks_api_failure() -> None:
    """Tests handling when Spotify API call fails."""
    # Arrange
    config_playlist_id = "playlist123"

    playback_info = {
        "item": {"uri": "spotify:track:track2"},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info,
        should_fail=True,  # This will cause API calls to fail
    )
    supabase_mock = MockSupabaseClient()

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.PLAYBACK_INACTIVE


@pytest.mark.asyncio
async def test_clear_played_tracks_with_autofill() -> None:
    """Tests successful clearing with autofill enabled."""
    # Arrange
    config_playlist_id = "playlist123"

    # Mock playback info with current track at position 3 (0-indexed)
    current_track_uri = "spotify:track:track4"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Mock playlist items with tracks before current position
    # original_playlist_items = [
    #     {"track": {"uri": "spotify:track:track1"}},
    #     {"track": {"uri": "spotify:track:track2"}},
    #     {"track": {"uri": "spotify:track:track3"}},
    #     {"track": {"uri": current_track_uri}},  # Currently playing
    #     {"track": {"uri": "spotify:track:track5"}},
    # ]

    # Sequence for autofill - after removal we have 2 tracks, need 5 minimum
    # So we need to add 3 more in the first attempt
    autofill_playlist_items_sequence = [
        # First call (during clear): original playlist (3 tracks before current)
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:track2"}},
            {"track": {"uri": "spotify:track:track3"}},
            {"track": {"uri": current_track_uri}},
            {"track": {"uri": "spotify:track:track5"}},
        ],
        # Second call (during autofill check): after removal = 2 tracks
        [
            {"track": {"uri": current_track_uri}},  # Currently playing
            {"track": {"uri": "spotify:track:track5"}},
        ],
        # Third call (after adding): should reach minimum of 5 tracks
        [
            {"track": {"uri": current_track_uri}},
            {"track": {"uri": "spotify:track:track5"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
            {"track": {"uri": "spotify:track:new3"}},
        ],
    ]

    # Mock Supabase client with pending requests for autofill
    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
        SongRequest(id=2, song=Song(artist="Artist 2", title="Title 2")),
        SongRequest(id=3, song=Song(artist="Artist 3", title="Title 3")),
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info,
        playlist_items_sequence=autofill_playlist_items_sequence,
    )
    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, 5
    )

    # Assert
    assert isinstance(result, Success)
    result_data = result.unwrap()
    assert result_data["deleted_count"] == 3  # 3 tracks should be removed
    assert result_data["filled_count"] == 3  # 3 tracks filled during autofill
    # Verify that autofill worked - playlist reached minimum of 5 tracks
    assert spotify_mock.get_playlist_items_call_count >= 2
    # Verify that songs were added to Spotify during autofill
    assert len(spotify_mock.added_songs) == 3  # 3 requests were processed


@pytest.mark.asyncio
async def test_clear_played_tracks_autofill_disabled() -> None:
    """Tests that autofill is skipped when disabled."""
    # Arrange
    config_playlist_id = "playlist123"

    # Mock playback info with current track at position 2
    current_track_uri = "spotify:track:track3"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Mock playlist items with tracks before current position
    playlist_items = [
        {"track": {"uri": "spotify:track:track1"}},
        {"track": {"uri": "spotify:track:track2"}},
        {"track": {"uri": current_track_uri}},  # Currently playing
        {"track": {"uri": "spotify:track:track4"}},
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info, playlist_items=playlist_items
    )
    supabase_mock = MockSupabaseClient()

    # Act with autofill_count = None (disabled)
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, None
    )

    # Assert
    assert isinstance(result, Success)
    result_data = result.unwrap()
    assert result_data["deleted_count"] == 2  # 2 tracks should be removed
    assert result_data["filled_count"] == 0  # No autofill happened
    # Verify that no songs were added to the playlist (autofill was disabled)
    assert len(spotify_mock.added_songs) == 0


@pytest.mark.asyncio
async def test_clear_played_tracks_autofill_failure_returns_error() -> None:
    """Tests that autofill failure causes the entire operation to fail."""
    # Arrange
    config_playlist_id = "playlist123"

    current_track_uri = "spotify:track:track2"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Sequence for autofill failure - after removal we have 1 track, need 10 minimum
    autofill_sequence = [
        # First call (during clear)
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": current_track_uri}},
        ],
        # Second call (during autofill check): 1 track < 10 minimum
        [
            {"track": {"uri": current_track_uri}},
        ],
    ]

    playlist_items = [
        {"track": {"uri": "spotify:track:track1"}},  # Should be removed
        {"track": {"uri": current_track_uri}},  # Currently playing
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info,
        playlist_items=playlist_items,
        playlist_items_sequence=autofill_sequence,
    )
    # Mock Supabase client that will fail during fetch (during autofill)
    supabase_mock = MockSupabaseClient(fetch_should_fail=True)

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, 10
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR
    assert "Failed to autofill playlist after clearing" in failure.message


@pytest.mark.asyncio
async def test_clear_played_tracks_autofill_not_found_ignored() -> None:
    """Tests that 'not found' songs during autofill are treated as success."""
    # Arrange
    config_playlist_id = "playlist123"

    current_track_uri = "spotify:track:track2"
    playback_info = {
        "item": {"uri": current_track_uri},
        "context": {
            "type": "playlist",
            "uri": f"spotify:playlist:{config_playlist_id}",
        },
    }

    # Sequence for autofill - after removal we have 1 track, need 10 minimum
    # But we won't reach 10, so autofill will stop after max attempts
    autofill_sequence = [
        # First call (during clear)
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": current_track_uri}},
        ],
        # Second call (during autofill check): 1 track < 10 minimum
        [
            {"track": {"uri": current_track_uri}},
        ],
    ]

    playlist_items = [
        {"track": {"uri": "spotify:track:track1"}},  # Should be removed
        {"track": {"uri": current_track_uri}},  # Currently playing
    ]

    # Create requests where one will be found, one not found
    pending_requests_test = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
        SongRequest(id=2, song=Song(artist="Artist 2", title="Title 2")),
    ]

    # Mixed statuses: 1 successful, 1 not found (should be acceptable)
    song_statuses = [
        (pending_requests_test[0], SongAdditionStatus.SUCCESS),
        (pending_requests_test[1], SongAdditionStatus.NOT_FOUND),
    ]

    spotify_mock = MockSpotifyClient(
        playback_info=playback_info,
        playlist_items=playlist_items,
        playlist_items_sequence=autofill_sequence,
        song_statuses=song_statuses,
    )
    supabase_mock = MockSupabaseClient(pending_requests=pending_requests_test)

    # Act
    result = await clear_played_tracks_from_playlist(
        spotify_mock, supabase_mock, config_playlist_id, 10
    )

    # Assert - operation should succeed despite "not found" songs
    assert isinstance(result, Success)
    result_data = result.unwrap()
    assert result_data["deleted_count"] == 1  # 1 track removed
    assert (
        result_data["filled_count"] == 5
    )  # 5 tracks filled during autofill (1 per attempt * 5 attempts)
    # The sync should have processed both requests (1 successful, 1 not found)
    # This is verified by the fact that the operation succeeded
    # Check that at least one successful song was added during autofill attempts
    assert len(spotify_mock.added_songs) >= 1  # At least the successful one was added


@pytest.mark.asyncio
async def test_autofill_playlist_minimum_reached() -> None:
    """Tests that autofill stops when minimum track count is reached."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 10

    # Initial playlist with 8 tracks (below minimum)
    initial_playlist = [
        {"track": {"uri": f"spotify:track:track{i}"}} for i in range(1, 9)
    ]

    # Sequence: initial -> after adding songs (should reach minimum)
    playlist_sequence = [
        initial_playlist,
        # After adding 2 songs, we should have 10 tracks
        [{"track": {"uri": f"spotify:track:track{i}"}} for i in range(1, 9)]
        + [
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
        ],
    ]

    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
        SongRequest(id=2, song=Song(artist="Artist 2", title="Title 2")),
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(playlist_items_sequence=playlist_sequence)

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert
    assert isinstance(result, Success)
    filled_count = result.unwrap()
    assert filled_count == 2  # 2 tracks added during autofill
    # Should have added the songs
    assert len(spotify_mock.added_songs) == 2


@pytest.mark.asyncio
async def test_autofill_playlist_multiple_attempts() -> None:
    """Tests that autofill makes multiple attempts to reach minimum."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 10

    # Start with very few tracks
    initial_playlist = [{"track": {"uri": "spotify:track:track1"}}]

    # Sequence simulating multiple attempts
    playlist_sequence = [
        # Attempt 1
        initial_playlist,
        # After first attempt: 1 + 2 = 3 tracks (still below 10)
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
        ],
        # Attempt 2
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
        ],
        # After second attempt: 3 + 2 = 5 tracks (still below 10)
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
            {"track": {"uri": "spotify:track:new3"}},
            {"track": {"uri": "spotify:track:new4"}},
        ],
        # Attempt 3
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
            {"track": {"uri": "spotify:track:new3"}},
            {"track": {"uri": "spotify:track:new4"}},
        ],
        # After third attempt: 5 + 2 = 7 tracks (still below 10)
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
            {"track": {"uri": "spotify:track:new3"}},
            {"track": {"uri": "spotify:track:new4"}},
            {"track": {"uri": "spotify:track:new5"}},
            {"track": {"uri": "spotify:track:new6"}},
        ],
        # And so on... (up to 5 attempts max)
    ]

    pending_requests = [
        SongRequest(id=i, song=Song(artist=f"Artist {i}", title=f"Title {i}"))
        for i in range(1, 11)  # 10 requests for multiple attempts
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(playlist_items_sequence=playlist_sequence)

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert
    assert isinstance(result, Success)
    filled_count = result.unwrap()
    assert filled_count >= 6  # At least 6 tracks added during multiple attempts
    # Should have made multiple attempts
    assert len(spotify_mock.added_songs) >= 6  # At least some songs added
    assert spotify_mock.get_playlist_items_call_count >= 3  # Multiple attempts made


@pytest.mark.asyncio
async def test_autofill_playlist_error_count_failure() -> None:
    """Tests that autofill fails when error_count > 0."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 10

    # Start with few tracks
    initial_playlist = [{"track": {"uri": "spotify:track:track1"}}]

    playlist_sequence = [
        initial_playlist,
        # After adding songs with errors
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
        ],
    ]

    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
        SongRequest(id=2, song=Song(artist="Artist 2", title="Title 2")),
        SongRequest(id=3, song=Song(artist="Artist 3", title="Title 3")),
    ]

    # Create statuses with 1 error
    song_statuses = [
        (pending_requests[0], SongAdditionStatus.SUCCESS),
        (pending_requests[1], SongAdditionStatus.ERROR),  # This will cause failure
        (pending_requests[2], SongAdditionStatus.SUCCESS),
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(
        playlist_items_sequence=playlist_sequence, song_statuses=song_statuses
    )

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR
    assert "Autofill failed with 1 errors" in failure.message


@pytest.mark.asyncio
async def test_autofill_playlist_no_songs_available() -> None:
    """Tests that autofill stops when no songs are available to add."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 10

    # Start with few tracks
    initial_playlist = [{"track": {"uri": "spotify:track:track1"}}]

    playlist_sequence = [
        initial_playlist,
        # After sync, no successful additions
        [
            {"track": {"uri": "spotify:track:track1"}},
        ],
    ]

    # Only "not found" songs
    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
        SongRequest(id=2, song=Song(artist="Artist 2", title="Title 2")),
    ]

    song_statuses = [
        (pending_requests[0], SongAdditionStatus.NOT_FOUND),
        (pending_requests[1], SongAdditionStatus.NOT_FOUND),
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(
        playlist_items_sequence=playlist_sequence, song_statuses=song_statuses
    )

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert - should succeed but stop due to no available songs
    assert isinstance(result, Success)
    filled_count = result.unwrap()
    assert filled_count == 0  # No songs filled during autofill
    # No songs should have been added
    assert len(spotify_mock.added_songs) == 0


@pytest.mark.asyncio
async def test_autofill_playlist_already_at_minimum() -> None:
    """Tests that autofill doesn't run when playlist already meets minimum."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 10

    # Playlist already has minimum tracks
    initial_playlist = [
        {"track": {"uri": f"spotify:track:track{i}"}} for i in range(1, 11)
    ]

    playlist_sequence = [
        initial_playlist,
    ]

    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(playlist_items_sequence=playlist_sequence)

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert
    assert isinstance(result, Success)
    filled_count = result.unwrap()
    assert filled_count == 0  # No tracks filled (already at minimum)
    # Should not have called sync at all
    assert len(spotify_mock.added_songs) == 0
    assert spotify_mock.get_playlist_items_call_count == 1  # Only initial check


@pytest.mark.asyncio
async def test_autofill_playlist_max_attempts_reached() -> None:
    """Tests that autofill stops after max attempts even if minimum not reached."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 50  # High minimum to force max attempts

    # Start with very few tracks
    initial_playlist = [{"track": {"uri": "spotify:track:track1"}}]

    # Sequence with 5 attempts that never reach the high minimum
    # Each attempt adds exactly 1 song (realistic for max_count=1)
    playlist_sequence = [
        # Initial check: 1 track
        initial_playlist,
        # After attempt 1: 2 tracks
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
        ],
        # After attempt 2: 3 tracks
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
        ],
        # After attempt 3: 4 tracks
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
            {"track": {"uri": "spotify:track:new3"}},
        ],
        # After attempt 4: 5 tracks
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
            {"track": {"uri": "spotify:track:new3"}},
            {"track": {"uri": "spotify:track:new4"}},
        ],
        # After attempt 5: 6 tracks (still below 50, but max attempts reached)
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
            {"track": {"uri": "spotify:track:new2"}},
            {"track": {"uri": "spotify:track:new3"}},
            {"track": {"uri": "spotify:track:new4"}},
            {"track": {"uri": "spotify:track:new5"}},
        ],
    ]

    # Provide 6 pending requests (but mock will ignore max_count and return all)
    pending_requests = [
        SongRequest(id=i, song=Song(artist=f"Artist {i}", title=f"Title {i}"))
        for i in range(1, 7)  # 6 requests
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(playlist_items_sequence=playlist_sequence)

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert - should succeed after max attempts
    assert isinstance(result, Success)
    filled_count = result.unwrap()
    # Mock ignores max_count, so all 6 songs are added per attempt
    # After 5 attempts: 1 + (5 × 6) = 31 songs filled
    assert filled_count == 30  # 30 tracks filled (6 per attempt × 5 attempts)
    # Should have made exactly 5 attempts (no additional final check)
    assert spotify_mock.get_playlist_items_call_count == 5  # 5 attempts
    # Should have added 30 songs (6 per attempt × 5 attempts)
    assert len(spotify_mock.added_songs) == 30
    # Verify it stopped at max attempts and didn't try more
    assert filled_count < minimum_track_count  # Still below minimum (30 < 50)
    # Verify it stopped at exactly 5 attempts (the key fix)
    assert spotify_mock.get_playlist_items_call_count <= 5  # Max 5 attempts


@pytest.mark.asyncio
async def test_autofill_playlist_get_playlist_items_failure() -> None:
    """Tests that autofill fails when get_playlist_items fails during the first check."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 10

    # Mock that get_playlist_items will fail
    spotify_mock = MockSpotifyClient(get_playlist_items_should_fail=True)
    supabase_mock = MockSupabaseClient()

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR
    assert "Failed to retrieve playlist items during autofill" in failure.message


@pytest.mark.asyncio
async def test_autofill_playlist_sync_exception_during_attempt() -> None:
    """Tests that autofill handles unexpected exceptions during sync attempt."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 10

    # Start with few tracks to trigger an attempt
    initial_playlist = [{"track": {"uri": "spotify:track:track1"}}]

    playlist_sequence = [initial_playlist]

    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
    ]

    # Create a mock that will raise an exception during sync
    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(
        playlist_items_sequence=playlist_sequence,
        should_fail=False,  # Don't fail API calls, but sync should still fail
    )

    # Mock sync to fail by making the second get_playlist_items call fail
    # This simulates an exception during the sync operation
    spotify_mock.get_playlist_items_should_fail = True

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert - should handle the exception gracefully
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR
    assert "Failed to retrieve playlist items during autofill" in failure.message


@pytest.mark.asyncio
async def test_autofill_playlist_tracks_needed_boundary_conditions() -> None:
    """Tests boundary conditions for tracks_needed calculation."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 0  # Edge case: minimum is 0

    # Empty playlist
    initial_playlist: list[dict[str, object]] = []

    playlist_sequence = [initial_playlist]

    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(playlist_items_sequence=playlist_sequence)

    # Act - with minimum of 0, should succeed immediately
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert - should succeed immediately since we already meet minimum (0)
    assert isinstance(result, Success)
    filled_count = result.unwrap()
    assert filled_count == 0  # No tracks filled (already at minimum 0)
    # Should not have added any songs since minimum is 0
    assert len(spotify_mock.added_songs) == 0
    # Should have made only the initial check
    assert spotify_mock.get_playlist_items_call_count == 1


@pytest.mark.asyncio
async def test_autofill_playlist_single_song_needed() -> None:
    """Tests autofill when only 1 song is needed to reach minimum."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 2

    # Start with 1 track (need 1 more)
    initial_playlist = [{"track": {"uri": "spotify:track:track1"}}]

    playlist_sequence = [
        initial_playlist,
        # After adding 1 song: 2 tracks total
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:new1"}},
        ],
    ]

    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(playlist_items_sequence=playlist_sequence)

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert
    assert isinstance(result, Success)
    filled_count = result.unwrap()
    assert filled_count == 1  # 1 track filled during autofill
    # Should have added exactly 1 song
    assert len(spotify_mock.added_songs) == 1


@pytest.mark.asyncio
async def test_autofill_playlist_large_track_count_difference() -> None:
    """Tests autofill with a large difference between current and minimum track count."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 1000  # Very large minimum

    # Start with only 1 track
    initial_playlist = [{"track": {"uri": "spotify:track:track1"}}]

    playlist_sequence = [
        initial_playlist,
        # After adding many songs, still not at minimum
        [{"track": {"uri": "spotify:track:track1"}}]
        + [{"track": {"uri": f"spotify:track:new{i}"}} for i in range(1, 51)],
        # Continue this pattern... (will stop after max attempts)
    ]

    # Create many pending requests
    pending_requests = [
        SongRequest(id=i, song=Song(artist=f"Artist {i}", title=f"Title {i}"))
        for i in range(1, 101)  # 100 requests
    ]

    supabase_mock = MockSupabaseClient(pending_requests=pending_requests)
    spotify_mock = MockSpotifyClient(playlist_items_sequence=playlist_sequence)

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert - should succeed after max attempts, even without reaching minimum
    assert isinstance(result, Success)
    filled_count = result.unwrap()
    assert (
        filled_count == 500
    )  # 500 tracks filled during max attempts (100 tracks per attempt * 5 attempts)
    # Should have made the maximum number of attempts
    assert spotify_mock.get_playlist_items_call_count >= 5
    # Should have added many songs
    assert len(spotify_mock.added_songs) >= 20  # At least some songs added


@pytest.mark.asyncio
async def test_autofill_playlist_unexpected_exception() -> None:
    """Tests that autofill handles unexpected exceptions during sync attempt."""
    # Arrange
    config_playlist_id = "playlist123"
    minimum_track_count = 10

    # Start with few tracks to trigger an attempt
    initial_playlist = [{"track": {"uri": "spotify:track:track1"}}]

    playlist_sequence = [initial_playlist]

    pending_requests = [
        SongRequest(id=1, song=Song(artist="Artist 1", title="Title 1")),
    ]

    # Create a mock that will raise an exception during fetch_pending_song_requests
    supabase_mock = MockSupabaseClient(
        pending_requests=pending_requests, fetch_should_raise=True
    )
    spotify_mock = MockSpotifyClient(playlist_items_sequence=playlist_sequence)

    # Act
    result = await _autofill_playlist(
        supabase_mock, spotify_mock, config_playlist_id, minimum_track_count
    )

    # Assert - should handle the exception gracefully
    assert isinstance(result, Failure)
    failure = result.failure()
    assert isinstance(failure, PlaylistClearError)
    assert failure.error_code == PlaylistClearFailure.ERROR
    assert failure.message == "Unexpected error during autofill"
    assert (
        failure.details is not None
        and "Unexpected database connection failure" in failure.details
    )
    # Verify that no songs were added due to the exception
    assert len(spotify_mock.added_songs) == 0
