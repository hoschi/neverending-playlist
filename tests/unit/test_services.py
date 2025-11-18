import pytest
from returns.result import Failure, Result, Success

from src.core.models import Song, SongAdditionStatus, SongRequest, SyncResult
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.playlist_service import (
    add_songs_to_spotify,
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
    ):
        self.added_songs: list[SongRequest] = []
        self.should_fail = should_fail
        self.song_statuses = song_statuses or []
        self.get_current_user_should_fail = get_current_user_should_fail

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
