from typing import Protocol, runtime_checkable

from returns.result import Result

from src.core.models import SongAdditionStatus, SongRequest


@runtime_checkable
class SupabaseClient(Protocol):
    """Protocol for interacting with the Supabase database."""

    async def fetch_pending_song_requests(
        self, max_count: int
    ) -> Result[list[SongRequest], Exception]: ...

    async def update_song_requests_as_added(
        self, song_requests: list[SongRequest]
    ) -> Result[None, Exception]: ...


@runtime_checkable
class SpotifyClient(Protocol):
    """Protocol for interacting with the Spotify API."""

    async def get_current_user(self) -> Result[dict[str, str] | None, Exception]: ...

    async def add_songs_to_playlist(
        self, songs: list[SongRequest]
    ) -> Result[list[tuple[SongRequest, SongAdditionStatus]], Exception]: ...

    async def get_current_playback(self) -> Result[dict | None, Exception]: ...  # type: ignore[type-arg]

    async def get_playlist_items(
        self, playlist_id: str
    ) -> Result[list[dict], Exception]: ...  # type: ignore[type-arg]

    async def remove_items_from_playlist(
        self, playlist_id: str, uris: list[str]
    ) -> Result[None, Exception]: ...
