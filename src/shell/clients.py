import spotipy  # type: ignore
from returns.result import Result, Success
from spotipy.oauth2 import SpotifyClientCredentials  # type: ignore
from supabase import Client, create_client

from src.core.config import get_settings
from src.core.models import Song, SongRequest
from src.core.protocols import SpotifyClient, SupabaseClient


class ConcreteSupabaseClient(SupabaseClient):
    """A concrete implementation of the Supabase client."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client: Client = create_client(
            settings.supabase_url, settings.supabase_key
        )

    async def fetch_pending_song_requests(
        self, max_count: int
    ) -> Result[list[SongRequest], Exception]:
        try:
            response = (
                self.client.table("song_requests")
                .select("*")
                .eq("is_added", "false")
                .limit(max_count)
                .execute()
            )
            song_requests = [
                SongRequest(
                    id=item["id"],
                    song=Song(artist=item["artist"], title=item["title"]),
                    requested_by=item["requested_by"],
                    is_added=item["is_added"],
                )
                for item in response.data
            ]
            return Success(song_requests)
        except Exception as e:
            return Result.from_failure(e)

    async def update_song_requests_as_added(
        self, song_requests: list[SongRequest]
    ) -> Result[None, Exception]:
        try:
            request_ids = [req.id for req in song_requests]
            (
                self.client.table("song_requests")
                .update({"is_added": True})
                .in_("id", request_ids)
                .execute()
            )
            return Success(None)
        except Exception as e:
            return Result.from_failure(e)


class ConcreteSpotifyClient(SpotifyClient):
    """A concrete implementation of the Spotify client."""

    def __init__(self) -> None:
        settings = get_settings()
        auth_manager = SpotifyClientCredentials(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
        )
        self.client = spotipy.Spotify(client_credentials_manager=auth_manager)

    async def add_songs_to_playlist(
        self, songs: list[SongRequest]
    ) -> Result[None, Exception]:
        try:
            settings = get_settings()
            track_uris: list[str] = []
            for song in songs:
                query = f"artist:{song.song.artist} track:{song.song.title}"
                results = self.client.search(q=query, type="track", limit=1)
                if results and results["tracks"]["items"]:
                    track_uris.append(results["tracks"]["items"][0]["uri"])

            if track_uris:
                self.client.playlist_add_items(settings.spotify_playlist_id, track_uris)
            return Success(None)
        except Exception as e:
            return Result.from_failure(e)
