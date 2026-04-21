import sqlite3

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
from src.core.sqlite_schema import SONG_REQUESTS_TABLE, SQLITE_SCHEMA_STATEMENTS


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
            logger.debug(f"Fetching pending song requests with max_count: {max_count}")
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
            ids = [sr.id for sr in song_requests]
            logger.debug(f"Retrieved song request IDs: {ids}")
            return Success(song_requests)
        except Exception as e:
            return Result.from_failure(e)

    async def update_song_requests_as_added(
        self, song_requests: list[SongRequest]
    ) -> Result[None, Exception]:
        try:
            ids = [sr.id for sr in song_requests]
            statuses = [sr.status.value if sr.status else None for sr in song_requests]
            logger.debug(f"Updating song requests: IDs {ids}, statuses {statuses}")
            for song_request in song_requests:
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


class ConcreteSqliteClient(SupabaseClient):
    """A SQLite-backed implementation for song request operations."""

    def __init__(self) -> None:
        settings = get_settings()
        self.sqlite_db_path = settings.sqlite_db_path

    def _get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_db_path)
        connection.row_factory = sqlite3.Row
        cursor = connection.cursor()
        for statement in SQLITE_SCHEMA_STATEMENTS:
            cursor.execute(statement)
        connection.commit()
        return connection

    async def fetch_pending_song_requests(
        self, max_count: int
    ) -> Result[list[SongRequest], Exception]:
        try:
            logger.debug(
                f"Fetching pending song requests from SQLite with max_count: {max_count}"
            )
            connection = self._get_connection()
            try:
                cursor = connection.cursor()
                rows = cursor.execute(
                    f"""
                    SELECT id, artist, song, status
                    FROM {SONG_REQUESTS_TABLE}
                    WHERE status IS NULL
                    ORDER BY id ASC
                    LIMIT ?
                    """,
                    (max_count,),
                ).fetchall()

                song_requests = [
                    SongRequest(
                        id=int(row["id"]),
                        song=Song(artist=str(row["artist"]), title=str(row["song"])),
                        status=None,
                    )
                    for row in rows
                ]
                return Success(song_requests)
            finally:
                connection.close()
        except Exception as e:
            return Result.from_failure(e)

    async def update_song_requests_as_added(
        self, song_requests: list[SongRequest]
    ) -> Result[None, Exception]:
        try:
            connection = self._get_connection()
            try:
                cursor = connection.cursor()
                for song_request in song_requests:
                    cursor.execute(
                        f"""
                        UPDATE {SONG_REQUESTS_TABLE}
                        SET status = ?
                        WHERE id = ?
                        """,
                        (
                            song_request.status.value if song_request.status else None,
                            song_request.id,
                        ),
                    )
                connection.commit()
                return Success(None)
            finally:
                connection.close()
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
            scope="playlist-modify-public playlist-modify-private user-read-playback-state",
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
                logger.trace(f"Searching for song with query: '{query}'")
                try:
                    search_results = self.client.search(q=query, type="track", limit=1)

                    if search_results and search_results["tracks"]["items"]:
                        # Song found, add to playlist and mark as success
                        track_uri = search_results["tracks"]["items"][0]["uri"]
                        logger.debug(
                            f"Found track URI: '{track_uri}' for query '{query}'"
                        )
                        self.client.playlist_add_items(
                            settings.spotify_playlist_id, [track_uri]
                        )
                        # Update the song request with the status
                        song.status = SongAdditionStatus.SUCCESS
                        results.append((song, SongAdditionStatus.SUCCESS))
                    else:
                        # Song not found
                        logger.debug(f"No track found for query: '{query}'")
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

    async def get_current_playback(self) -> Result[dict | None, Exception]:  # type: ignore[type-arg]
        """Get the current playback state from Spotify."""
        try:
            playback = self.client.current_playback()
            return Success(playback)
        except Exception as e:
            return Result.from_failure(e)

    async def get_playlist_items(
        self, playlist_id: str
    ) -> Result[list[dict], Exception]:  # type: ignore[type-arg]
        """Get all items from a playlist."""
        try:
            items = []
            offset = 0
            limit = 100

            while True:
                response = self.client.playlist_items(
                    playlist_id,
                    limit=limit,
                    offset=offset,
                    fields="items(track(uri,name,artists(name))),total",
                )

                if not response or not response.get("items"):
                    break

                items.extend(response["items"])

                if len(response["items"]) < limit:
                    break

                offset += limit

            return Success(items)
        except Exception as e:
            return Result.from_failure(e)

    async def remove_items_from_playlist(
        self, playlist_id: str, uris: list[str]
    ) -> Result[None, Exception]:
        """Remove items from a playlist.

        Args:
            playlist_id: The ID of the playlist to remove items from
            uris: List of track URIs to remove

        Note:
            Spotify Web API allows maximum 100 objects per DELETE request.
            Reference: https://developer.spotify.com/documentation/web-api/reference/remove-tracks-playlist
        """
        try:
            # Spotify API limit: maximum 100 objects per delete request
            batch_size = 100

            for i in range(0, len(uris), batch_size):
                batch = uris[i : i + batch_size]
                self.client.playlist_remove_all_occurrences_of_items(playlist_id, batch)

            return Success(None)
        except Exception as e:
            return Result.from_failure(e)
