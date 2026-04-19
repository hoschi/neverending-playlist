"""In-Memory WatchService für Clear Played Watchmode Funktionalität.

This module implements the Background Task Management for the automatic
removal of played tracks from playlists with configurable interval timing using asyncio.
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta

from loguru import logger
from returns.pipeline import is_successful
from returns.result import Result

from src.core.config import get_settings
from src.core.models import (
    PlaylistClearError,
    PlaylistClearFailure,
)
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.playlist_service import clear_played_tracks_from_playlist
from src.shell.state import (
    CheckerState,
    get_checker_state,
    reset_checker_state,
    update_checker_state,
)


class WatchService:
    """In-Memory WatchService für Clear Played Watchmode.

    Manages state and execution of the automatic Playlist-Clearing
    functionality that runs with configurable intervals using asyncio tasks.
    """

    def __init__(
        self,
        spotify_client: SpotifyClient,
        supabase_client: SupabaseClient,
    ) -> None:
        """Initialisiert den WatchService mit Client Instanzen.

        Args:
            spotify_client: Spotify Client Instanz
            supabase_client: Supabase Client Instanz
        """
        self.spotify_client = spotify_client
        self.supabase_client = supabase_client
        self._task: asyncio.Task[None] | None = None
        self._shutdown_event = asyncio.Event()

    async def start_watch_service(self) -> CheckerState:
        """Starts the Background WatchService Task.

        Initializes the recurring background task that monitors for active playback
        and automatically removes played tracks from the playlist in configurable intervals.

        Returns:
            CheckerState: The current state of the WatchService after starting
        """
        current_state = await get_checker_state()

        if current_state.is_running:
            logger.info("WatchService already running, returning current state")
            return current_state

        try:
            # CRITICAL FIX: Clear shutdown event before starting new task
            # Without this, the background task terminates immediately after restart
            # because the event is still set from the previous stop_watch_service() call
            if self._shutdown_event.is_set():
                logger.debug(
                    "Clearing shutdown event from previous stop before restart"
                )
                self._shutdown_event.clear()

            # Check for active playback before starting
            if not await self._check_active_playback():
                new_retries_left = max(0, current_state.retries_left - 1)
                await update_checker_state(retries_left=new_retries_left)

                if current_state.retries_left <= 1:
                    raise ValueError(
                        "No active playback detected. WatchService not started."
                    )
                else:
                    logger.warning(
                        f"No active playback detected. Retries left: {new_retries_left}"
                    )
                    return await get_checker_state()

            # Setze State auf "gestartet"
            settings = get_settings()
            await update_checker_state(
                is_running=True,
                retries_left=5,
                last_playback_detected=True,
                next_check=datetime.now(UTC)
                + timedelta(minutes=settings.watch_service_timeout_minutes),
            )

            logger.info("WatchService successfully started with asyncio")

            # Starte Background Task
            self._task = asyncio.create_task(self._watch_loop())

            return await get_checker_state()

        except Exception as e:
            logger.error(f"Error starting WatchService: {e}")
            await update_checker_state(is_running=False)
            raise

    async def stop_watch_service(self) -> CheckerState:
        """Stops the Background WatchService Task.

        Returns:
            CheckerState: The current state of the WatchService after stopping
        """
        current_state = await get_checker_state()

        if not current_state.is_running:
            logger.info("WatchService not running")
            return current_state

        try:
            # Setze Shutdown Event und warte auf Task Beendigung
            self._shutdown_event.set()

            if self._task and not self._task.done():
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task

            # Setze State auf "gestoppt"
            await update_checker_state(is_running=False, next_check=None)

            logger.info("WatchService stopped successfully")

        except Exception as e:
            logger.error(f"Error stopping WatchService: {e}")
            raise

        return await get_checker_state()

    async def get_state(self) -> CheckerState:
        """Returns the current WatchService State.

        Returns:
            CheckerState: The current state of the WatchService
        """
        return await get_checker_state()

    async def reset_state(self) -> CheckerState:
        """Resets the WatchService State to default values.

        Returns:
            CheckerState: The reset WatchService state
        """
        # Reset shutdown event
        self._shutdown_event.clear()

        # Cancel any running task
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        # Reset internal state
        self._task = None

        return await reset_checker_state()

    async def _watch_loop(self) -> None:
        """Haupt-Loop für den WatchService Background Task.

        This function runs continuously and:
        1. Checks for active playback
        2. Calls the existing clear_played_tracks_from_playlist logic
        3. Updates the WatchService state based on results
        4. Handles retry attempts and stop conditions
        5. Waits configurable time before next iteration
        """
        logger.info("WatchService Background Task started")

        try:
            settings = get_settings()
            while not self._shutdown_event.is_set():
                await self._execute_clear_task()

                # Warte konfigurierbare Zeit oder bis Shutdown Signal
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=settings.watch_service_timeout_minutes
                        * 60.0,  # in seconds
                    )
                    break  # Shutdown Signal erhalten
                except TimeoutError:
                    continue  # 10 Minuten vorbei, nächster Durchlauf

        except asyncio.CancelledError:
            logger.info("WatchService Background Task cancelled")
        except Exception as e:
            logger.error(f"Unexpected error in WatchService Loop: {e}")
        finally:
            logger.info("WatchService Background Task ended")

    async def _execute_clear_task(self) -> None:
        """Führt den Background Task zum Löschen abgespielter Tracks aus.

        Hauptfunktion für den Background Task, die:
        1. Checks for active playback
        2. Calls the existing clear_played_tracks_from_playlist logic
        3. Updates the WatchService state based on results
        4. Handles retry attempts and stop conditions
        """
        try:
            logger.info("Executing Clear Played Tracks Background Task")

            # Aktualisiere last_checked Timestamp
            await update_checker_state(last_checked=datetime.now(UTC))

            # Check for active playback
            active_playback = await self._check_active_playback()
            await update_checker_state(last_playback_detected=active_playback)

            if not active_playback:
                # Handle scenario without active playback
                current_state = await get_checker_state()
                new_retries_left = max(0, current_state.retries_left - 1)
                await update_checker_state(retries_left=new_retries_left)
                logger.warning(
                    f"No active playback detected. Retries left: {new_retries_left}"
                )

                if current_state.retries_left <= 1:
                    logger.error("No retries left, stopping WatchService")
                    await self.stop_watch_service()
                    return

                return
            else:
                # Reset retry counter when playback is detected again
                await update_checker_state(retries_left=5)

            # Führe die Clear Played Tracks Logik aus
            await self._clear_played_tracks()

            # Plane nächsten Check
            settings = get_settings()
            await update_checker_state(
                next_check=datetime.now(UTC)
                + timedelta(minutes=settings.watch_service_timeout_minutes)
            )

            logger.info("Background Task completed successfully")

        except Exception as e:
            logger.error(f"Error in Background Task: {e}")
            current_state = await get_checker_state()
            new_retries_left = max(0, current_state.retries_left - 1)
            await update_checker_state(retries_left=new_retries_left)

            if new_retries_left <= 0:
                logger.error("No retries left due to errors, stopping WatchService")
                await self.stop_watch_service()

    async def _check_active_playback(self) -> bool:
        """Checks if an active playback session exists.

        Returns:
            bool: True if active playback is detected, False otherwise
        """
        try:
            current_playback_result = await self.spotify_client.get_current_playback()

            if not is_successful(current_playback_result):
                return False

            current_playback = current_playback_result.unwrap()
            return current_playback is not None

        except Exception as e:
            logger.error(f"Error checking for active playback: {e}")
            return False

    async def _clear_played_tracks(self) -> None:
        """Führt die Clear Played Tracks Logik mit bestehendem Service aus.

        Ruft die bestehende clear_played_tracks_from_playlist Funktion
        from playlist_service.py that contains the core business logic.
        """
        try:
            settings = get_settings()

            # Rufe die bestehende Kern-Logik zum Löschen abgespielter Tracks auf
            result = await clear_played_tracks_from_playlist(
                self.spotify_client,
                self.supabase_client,
                settings.spotify_playlist_id,
                settings.playlist_autofill_count,
            )

            if is_successful(result):
                logger.info("Played tracks successfully removed from playlist")
            else:
                error = result.failure()
                logger.warning(f"Clearing played tracks failed: {error}")

        except Exception as e:
            logger.error(f"Error clearing played tracks: {e}")
            raise RuntimeError(f"Clear played tracks failed: {e}") from e


async def clear_playlist(
    supabase_client: SupabaseClient,
    spotify_client: SpotifyClient,
    config_playlist_id: str,
    autofill_count: int | None = None,
) -> Result[dict[str, int], PlaylistClearError]:
    """
    This function implements the Clear Played Watchmode Feature through direct usage
    using client instances and returning a Result type with Success/Failure Pattern.

    Args:
        supabase_client: Direkte SupabaseClient Instanz
        spotify_client: Direkte SpotifyClient Instanz
        config_playlist_id: The configured playlist ID
        autofill_count: Number of tracks for automatic refill (None = disabled)

    Returns:
        Result[dict[str, int], PlaylistClearError]:
            - Success(dict): Dictionary mit 'deleted_count' und 'filled_count' Schlüsseln
            - Failure(PlaylistClearError): Detailed error information
    """
    logger.info("Starting watch service operation")

    try:
        # Use the existing clear_played_tracks_from_playlist logic
        from src.core.services.playlist_service import clear_played_tracks_from_playlist

        result = await clear_played_tracks_from_playlist(
            spotify_client,
            supabase_client,
            config_playlist_id,
            autofill_count,
        )

        if is_successful(result):
            logger.info("Watch service completed successfully")
            return result
        else:
            error = result.failure()
            logger.warning("Watch service failed: {error}", error=error.message)
            return Result.from_failure(error)

    except Exception as e:
        logger.error("Unexpected error in watch service: {error}", error=e)
        return Result.from_failure(
            PlaylistClearError(
                error_code=PlaylistClearFailure.ERROR,
                message="Unexpected error in watch service",
                details=str(e),
            )
        )


_global_watch_service: WatchService | None = None


def watch_service(
    spotify_client: SpotifyClient,
    supabase_client: SupabaseClient,
) -> WatchService:
    """This function implements a Singleton Pattern to ensure,
    that only one WatchService instance runs in the application.

    Args:
        spotify_client: Spotify Client instance
        supabase_client: Supabase Client instance

    Returns:
        WatchService: The global WatchService instance
    """
    global _global_watch_service

    if _global_watch_service is None:
        _global_watch_service = WatchService(spotify_client, supabase_client)

    return _global_watch_service
