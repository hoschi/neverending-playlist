import pytest
from returns.result import Failure, Result, Success

from src.core.models import (
    PlaylistClearFailure,
    Song,
    SongAdditionStatus,
    SongRequest,
    SyncResult,
)
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.playlist_service import (
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
    ):
        self.pending_requests = pending_requests if pending_requests is not None else []
        self.updated_requests: list[SongRequest] = []
        self.fetch_should_fail = fetch_should_fail
        self.update_should_fail = update_should_fail

    async def fetch_pending_song_requests(
        self,
        max_count: int,  # noqa: ARG002
    ) -> Result[list[SongRequest], Exception]:
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
        remove_should_fail: bool = False,
    ):
        self.added_songs: list[SongRequest] = []
        self.should_fail = should_fail
        self.song_statuses = song_statuses or []
        self.get_current_user_should_fail = get_current_user_should_fail
        self.playback_info = playback_info
        self.playlist_items = playlist_items or []
        self.remove_should_fail = remove_should_fail

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
        if self.should_fail:
            return Failure(Exception("Spotify API failed"))
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

    # Act
    result = await clear_played_tracks_from_playlist(spotify_mock, config_playlist_id)

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() == 2  # 2 tracks should be removed


@pytest.mark.asyncio
async def test_clear_played_tracks_no_active_playback() -> None:
    """Tests handling when there is no active playback."""
    # Arrange
    config_playlist_id = "playlist123"
    spotify_mock = MockSpotifyClient(playback_info=None)

    # Act
    result = await clear_played_tracks_from_playlist(spotify_mock, config_playlist_id)

    # Assert
    assert isinstance(result, Failure)
    assert result.failure() == PlaylistClearFailure.PLAYBACK_INACTIVE


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

    # Act
    result = await clear_played_tracks_from_playlist(spotify_mock, config_playlist_id)

    # Assert
    assert isinstance(result, Failure)
    assert result.failure() == PlaylistClearFailure.WRONG_PLAYLIST


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

    # Act
    result = await clear_played_tracks_from_playlist(spotify_mock, config_playlist_id)

    # Assert
    assert isinstance(result, Failure)
    assert result.failure() == PlaylistClearFailure.PLAYBACK_INACTIVE


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

    # Act
    result = await clear_played_tracks_from_playlist(spotify_mock, config_playlist_id)

    # Assert
    assert isinstance(result, Failure)
    assert result.failure() == PlaylistClearFailure.PLAYBACK_INACTIVE


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

    # Act
    result = await clear_played_tracks_from_playlist(spotify_mock, config_playlist_id)

    # Assert
    assert isinstance(result, Failure)
    assert result.failure() == PlaylistClearFailure.PLAYBACK_INACTIVE


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

    # Act
    result = await clear_played_tracks_from_playlist(spotify_mock, config_playlist_id)

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() == 0  # No tracks to remove


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

    # Act
    result = await clear_played_tracks_from_playlist(spotify_mock, config_playlist_id)

    # Assert
    assert isinstance(result, Failure)
    assert result.failure() == PlaylistClearFailure.PLAYBACK_INACTIVE
