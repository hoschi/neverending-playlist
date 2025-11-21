from returns.result import Success

from src.core.models import SongAdditionStatus, SongRequest
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

    def __init__(
        self,
        should_fail: bool = False,
        playback_info: dict[str, object] | None = None,
        playlist_items: list[dict[str, object]] | None = None,
    ):
        self.added_songs: list[SongRequest] = []
        self.should_fail = should_fail
        self.playback_info = playback_info
        self.playlist_items = playlist_items or []

    async def get_current_user(self) -> Success[dict[str, str] | None]:
        return Success({"id": "test_user"})

    async def add_songs_to_playlist(
        self, songs: list[SongRequest]
    ) -> Success[list[tuple[SongRequest, SongAdditionStatus]]]:
        if self.should_fail:
            raise Exception("Spotify API failed")
        self.added_songs.extend(songs)
        return Success([(song, SongAdditionStatus.SUCCESS) for song in songs])

    async def get_current_playback(self) -> Success[dict[str, object] | None]:
        if self.should_fail:
            raise Exception("Spotify API failed")
        return Success(self.playback_info)

    async def get_playlist_items(
        self,
        playlist_id: str,  # noqa: ARG002
    ) -> Success[list[dict[str, object]]]:
        if self.should_fail:
            raise Exception("Spotify API failed")
        return Success(self.playlist_items)

    async def remove_items_from_playlist(
        self,
        playlist_id: str,  # noqa: ARG002
        uris: list[str],  # noqa: ARG002
    ) -> Success[None]:
        if self.should_fail:
            raise Exception("Spotify API failed")
        return Success(None)
