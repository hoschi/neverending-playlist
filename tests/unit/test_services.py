import pytest
from returns.result import Failure, Result, Success

from src.core.models import Song, SongRequest
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.playlist_service import (
    add_songs_to_spotify,
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
        self.updated_requests.extend(song_requests)
        return Success(None)


class MockSpotifyClient(SpotifyClient):
    """A mock Spotify client for unit tests."""

    def __init__(self, should_fail: bool = False):
        self.added_songs: list[SongRequest] = []
        self.should_fail = should_fail

    async def add_songs_to_playlist(
        self, songs: list[SongRequest]
    ) -> Result[None, Exception]:
        if self.should_fail:
            return Failure(Exception("Spotify API failed"))
        self.added_songs.extend(songs)
        return Success(None)


@pytest.mark.asyncio
async def test_sync_playlist_success() -> None:
    """
    Tests the success path of the sync_playlist service, ensuring all
    interactions with external services occur as expected.
    """
    # Arrange
    requests = [
        SongRequest(
            id=1, song=Song(artist="Artist 1", title="Title 1"), requested_by="User 1"
        ),
        SongRequest(
            id=2, song=Song(artist="Artist 2", title="Title 2"), requested_by="User 2"
        ),
    ]
    supabase_mock = MockSupabaseClient(pending_requests=requests)
    spotify_mock = MockSpotifyClient()

    # Act
    result = await sync_playlist(supabase_mock, spotify_mock, 10)

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() == 2
    assert len(supabase_mock.updated_requests) == 2
    assert len(spotify_mock.added_songs) == 2
    assert supabase_mock.updated_requests == requests
    assert spotify_mock.added_songs == requests


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
    assert result.unwrap() == 0
    assert len(supabase_mock.updated_requests) == 0
    assert len(spotify_mock.added_songs) == 0


@pytest.mark.asyncio
async def test_sync_playlist_aborts_on_fetch_failure() -> None:
    """Tests that the sync process aborts if fetching from Supabase fails."""
    # Arrange
    supabase_mock = MockSupabaseClient(fetch_should_fail=True)
    spotify_mock = MockSpotifyClient()

    # Act
    result = await sync_playlist(supabase_mock, spotify_mock, 10)

    # Assert
    assert isinstance(result, Failure)
    assert "Supabase fetch failed" in str(result.failure())
    assert len(supabase_mock.updated_requests) == 0
    assert len(spotify_mock.added_songs) == 0


@pytest.mark.asyncio
async def test_sync_playlist_aborts_on_spotify_failure() -> None:
    """
    Tests that the sync process aborts and does not update Supabase
    if adding songs to Spotify fails.
    """
    # Arrange
    requests = [
        SongRequest(
            id=1, song=Song(artist="Artist 1", title="Title 1"), requested_by="User 1"
        )
    ]
    supabase_mock = MockSupabaseClient(pending_requests=requests)
    spotify_mock = MockSpotifyClient(should_fail=True)

    # Act
    result = await sync_playlist(supabase_mock, spotify_mock, 10)

    # Assert
    assert isinstance(result, Failure)
    assert "Spotify API failed" in str(result.failure())
    assert len(supabase_mock.updated_requests) == 0
    assert len(spotify_mock.added_songs) == 0


@pytest.mark.asyncio
async def test_sync_playlist_aborts_on_update_failure() -> None:
    """Tests that the sync process fails if the final Supabase update fails."""
    # Arrange
    requests = [
        SongRequest(
            id=1, song=Song(artist="Artist 1", title="Title 1"), requested_by="User 1"
        )
    ]
    supabase_mock = MockSupabaseClient(
        pending_requests=requests, update_should_fail=True
    )
    spotify_mock = MockSpotifyClient()

    # Act
    result = await sync_playlist(supabase_mock, spotify_mock, 10)

    # Assert
    assert isinstance(result, Failure)
    assert "Supabase update failed" in str(result.failure())
    assert len(supabase_mock.updated_requests) == 0
    assert len(spotify_mock.added_songs) == 1


@pytest.mark.asyncio
async def test_add_songs_to_spotify_with_empty_list() -> None:
    """Tests that add_songs_to_spotify handles an empty list gracefully."""
    # Arrange
    spotify_mock = MockSpotifyClient()

    # Act
    result = await add_songs_to_spotify(spotify_mock, [])

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() is None
    assert len(spotify_mock.added_songs) == 0
