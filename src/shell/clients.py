import spotipy  # type: ignore
from loguru import logger
from pydantic import SecretStr
from returns.result import Result, Success
from spotipy.oauth2 import SpotifyOAuth  # type: ignore
from supabase import Client, create_client

from src.core.config import get_settings
from src.core.models import Song, SongAdditionStatus, SongRequest
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.encryption_service import EncryptionService


class ConcreteSupabaseClient(SupabaseClient):
    """A concrete implementation of the Supabase client."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client: Client = create_client(
            settings.supabase_url, settings.supabase_key
        )
        self.table_name = settings.supabase_table

    async def fetch_pending_song_requests(
        self, max_count: int
    ) -> Result[list[SongRequest], Exception]:
        try:
            response = (
                self.client.table(self.table_name)
                .select("*")
                .is_("status", "null")
                .limit(max_count)
                .execute()
            )
            song_requests = [
                SongRequest(
                    id=item["id"],
                    song=Song(artist=item["artist"], title=item["song"]),
                    status=None,
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
            # Update each song request individually with its specific status
            for song_request in song_requests:
                # Update the database with the status
                (
                    self.client.table(self.table_name)
                    .update(
                        {
                            "status": song_request.status.value
                            if song_request.status
                            else None
                        }
                    )
                    .eq("id", song_request.id)
                    .execute()
                )
            return Success(None)
        except Exception as e:
            return Result.from_failure(e)


class ConcreteSpotifyClient(SpotifyClient):
    """A concrete implementation of the Spotify client using user authorization."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.spotify_refresh_token:
            raise ValueError(
                "Spotify refresh token not found in environment. "
                "Please complete the authorization flow via the /login endpoint."
            )

        encryption_service = EncryptionService(key=SecretStr(settings.encryption_key))
        decrypted_token = encryption_service.decrypt(settings.spotify_refresh_token)

        auth_manager = SpotifyOAuth(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret,
            redirect_uri=settings.spotify_redirect_uri,
            scope="playlist-modify-public playlist-modify-private",
            cache_path=None,  # Do not use a cache file
        )
        # Manually prime the auth_manager with the refresh token
        auth_manager.refresh_access_token(decrypted_token)

        self.client = spotipy.Spotify(auth_manager=auth_manager)

    async def get_current_user(self) -> Result[dict[str, str] | None, Exception]:
        """Get the current user's profile information from Spotify."""
        try:
            user_info = self.client.current_user()
            return Success(user_info)
        except Exception as e:
            return Result.from_failure(e)

    async def add_songs_to_playlist(
        self, songs: list[SongRequest]
    ) -> Result[list[tuple[SongRequest, SongAdditionStatus]], Exception]:
        """Add songs to playlist and return individual status for each song.

        Args:
            songs: List of song requests to add to playlist

        Returns:
            Result containing list of tuples (song_request, status) for each song
        """
        try:
            settings = get_settings()
            results: list[tuple[SongRequest, SongAdditionStatus]] = []

            # Process each song individually
            for song in songs:
                query = f"artist:{song.song.artist} track:{song.song.title}"
                try:
                    search_results = self.client.search(q=query, type="track", limit=1)

                    if search_results and search_results["tracks"]["items"]:
                        # Song found, add to playlist and mark as success
                        track_uri = search_results["tracks"]["items"][0]["uri"]
                        self.client.playlist_add_items(
                            settings.spotify_playlist_id, [track_uri]
                        )
                        # Update the song request with the status
                        song.status = SongAdditionStatus.SUCCESS
                        results.append((song, SongAdditionStatus.SUCCESS))
                    else:
                        # Song not found
                        song.status = SongAdditionStatus.NOT_FOUND
                        results.append((song, SongAdditionStatus.NOT_FOUND))

                # recover from error
                except Exception as e:
                    # Error processing individual song
                    song.status = SongAdditionStatus.ERROR
                    logger.error(
                        f"Error during search for song with query '{query}': {e}"
                    )
                    results.append((song, SongAdditionStatus.ERROR))

            return Success(results)
        # can't recover from this error
        except Exception as e:
            return Result.from_failure(e)
