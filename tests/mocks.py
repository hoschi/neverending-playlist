from returns.result import Success

from src.core.models import SongRequest
from src.core.protocols import SpotifyClient, SupabaseClient


class MockSupabaseClient(SupabaseClient):
    """A mock Supabase client for testing."""

    def __init__(self, pending_requests: list[SongRequest] | None = None):
        self.pending_requests = pending_requests if pending_requests is not None else []
        self.updated_requests: list[SongRequest] = []

    async def fetch_pending_song_requests(
        self,
        max_count: int,  # noqa: ARG002
    ) -> Success[list[SongRequest]]:
        return Success(self.pending_requests)

    async def update_song_requests_as_added(
        self, song_requests: list[SongRequest]
    ) -> Success[None]:
        self.updated_requests.extend(song_requests)
        return Success(None)


class MockSpotifyClient(SpotifyClient):
    """A mock Spotify client for testing."""

    def __init__(self, should_fail: bool = False):
        self.added_songs: list[SongRequest] = []
        self.should_fail = should_fail

    async def add_songs_to_playlist(self, songs: list[SongRequest]) -> Success[None]:
        if self.should_fail:
            raise Exception("Spotify API failed")
        self.added_songs.extend(songs)
        return Success(None)
