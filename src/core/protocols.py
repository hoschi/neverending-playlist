from typing import Protocol

from returns.result import Result

from src.core.models import SongRequest


class SupabaseClient(Protocol):
    """Protocol for interacting with the Supabase database."""

    async def fetch_pending_song_requests(
        self, max_count: int
    ) -> Result[list[SongRequest], Exception]: ...

    async def update_song_requests_as_added(
        self, song_requests: list[SongRequest]
    ) -> Result[None, Exception]: ...


class SpotifyClient(Protocol):
    """Protocol for interacting with the Spotify API."""

    async def add_songs_to_playlist(
        self, songs: list[SongRequest]
    ) -> Result[None, Exception]: ...
