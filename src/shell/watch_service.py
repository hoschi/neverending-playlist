"""In-Memory WatchService für Clear Played Watchmode Funktionalität.

This module implements the Background Task Management for the automatic
removal of played tracks from playlists with configurable interval timing using asyncio.
"""

import asyncio
import contextlib
import time
from datetime import UTC, datetime, timedelta
from threading import current_thread

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
        self._timing_metrics: dict[str, float] = {}  # For tracking execution times

    def _log_trace_state(
        self, operation: str, event_state: bool, thread_id: str | None = None
    ) -> None:
        """TRACE-Level logging for state transitions.

        Args:
            operation: Name of the current operation
            event_state: Current state of shutdown event
            thread_id: Thread identifier for async context
        """
        if thread_id is None:
            thread_id = str(current_thread())

        logger.trace(
            f"[{thread_id}] {operation} - Shutdown event state: {event_state}, "
            f"Task: {self._task}, Task done: {self._task.done() if self._task else 'N/A'}"
        )

    def _log_trace_timing(
        self, operation: str, start_time: float, thread_id: str | None = None
    ) -> None:
        """TRACE-Level timing metrics logging.

        Args:
            operation: Name of the operation
            start_time: Start timestamp
            thread_id: Thread identifier for async context
        """
        if thread_id is None:
            thread_id = str(current_thread())

        elapsed = time.time() - start_time
        self._timing_metrics[operation] = elapsed

        logger.trace(f"[{thread_id}] {operation} completed in {elapsed:.3f}s")

    async def start_watch_service(self) -> CheckerState:
        """Starts the Background WatchService Task.

        Initializes the recurring background task that monitors for active playback
        and automatically removes played tracks from the playlist in configurable intervals.

        Returns:
            CheckerState: The current state of the WatchService after starting
        """
        start_time = time.time()
        thread_id = str(current_thread())

        # CRITICAL: State validation checks
        current_state = await get_checker_state()
        shutdown_event_state = self._shutdown_event.is_set()

        # Verify is_running vs shutdown_event consistency
        if current_state.is_running != (not shutdown_event_state):
            logger.error(
                f"STATE INCONSISTENCY! is_running={current_state.is_running} shutdown_set={shutdown_event_state}"
            )
            logger.error("State machine inconsistency detected - attempting recovery")
            # Recovery: Reset shutdown event if it contradicts is_running state
            if current_state.is_running and shutdown_event_state:
                logger.error(
                    "CRITICAL: Service marked as running but shutdown event is set - clearing shutdown"
                )
                self._shutdown_event.clear()
            elif not current_state.is_running and not shutdown_event_state:
                logger.error(
                    "CRITICAL: Service marked as stopped but shutdown event is clear - setting shutdown"
                )
                self._shutdown_event.set()

        # Capture state snapshot
        logger.info(
            f"STATE SNAPSHOT before start: is_running={current_state.is_running}, shutdown_event={shutdown_event_state}, task={self._task}"
        )

        # TRACE: Entry point with initial state
        self._log_trace_state(
            "start_watch_service_entry", self._shutdown_event.is_set(), thread_id
        )
        logger.trace(
            f"[{thread_id}] Starting WatchService with current retries: {current_state.retries_left}"
        )

        if current_state.is_running:
            # Additional health check for already running service
            if self._task and self._task.done():
                logger.error(
                    "HEALTH CHECK FAILURE: Service marked as running but task is completed - recovering"
                )
                await update_checker_state(is_running=False)
                current_state = await get_checker_state()
            else:
                logger.info("WatchService already running, returning current state")
                self._log_trace_timing(
                    "start_watch_service_already_running", start_time, thread_id
                )
                return current_state

        try:
            # CRITICAL FIX: Clear shutdown event before starting new task
            # Without this, the background task terminates immediately after restart
            # because the event is still set from the previous stop_watch_service() call
            if self._shutdown_event.is_set():
                logger.trace(
                    f"[{thread_id}] CRITICAL: Shutdown event is SET before restart - clearing it"
                )
                logger.debug(
                    "Clearing shutdown event from previous stop before restart"
                )
                self._shutdown_event.clear()

            # TRACE: Shutdown event state after clear
            self._log_trace_state(
                "start_watch_service_after_clear",
                self._shutdown_event.is_set(),
                thread_id,
            )

            # Reset retry counter FIRST before playback check when restarting
            # This allows restart after retry exhaustion when playback is available
            if current_state.retries_left < 5:
                logger.trace(
                    f"[{thread_id}] Resetting retry counter from {current_state.retries_left} to 5"
                )
                logger.info(
                    f"Resetting retry counter from {current_state.retries_left} to 5 for restart"
                )
                await update_checker_state(retries_left=5)
                # Update local reference to reflect the reset
                current_state = await get_checker_state()

                logger.trace(
                    f"[{thread_id}] Retry counter reset complete, new retries: {current_state.retries_left}"
                )

            # Check for active playback before starting
            playback_start = time.time()
            logger.trace(f"[{thread_id}] Starting playback check...")
            playback_result = await self._check_active_playback()
            self._log_trace_timing("playback_check", playback_start, thread_id)

            logger.trace(f"[{thread_id}] Playback check result: {playback_result}")

            if not playback_result:
                logger.trace(
                    f"[{thread_id}] No active playback detected, calculating new retry count"
                )
                new_retries_left = max(0, current_state.retries_left - 1)
                await update_checker_state(retries_left=new_retries_left)

                if new_retries_left <= 0:
                    logger.trace(
                        f"[{thread_id}] No retries left ({new_retries_left}), failing start_watch_service"
                    )
                    raise ValueError(
                        "No active playback detected. WatchService not started."
                    )
                else:
                    logger.trace(
                        f"[{thread_id}] Playback check failed, retries left: {new_retries_left}"
                    )
                    logger.warning(
                        f"No active playback detected. Retries left: {new_retries_left}"
                    )
                    self._log_trace_timing(
                        "start_watch_service_no_playback", start_time, thread_id
                    )
                    return await get_checker_state()

            # Setze State auf "gestartet"
            logger.trace(f"[{thread_id}] Setting service state to running...")
            settings = get_settings()
            await update_checker_state(
                is_running=True,
                retries_left=5,
                last_playback_detected=True,
                next_check=datetime.now(UTC)
                + timedelta(minutes=settings.watch_service_timeout_minutes),
            )

            logger.trace(
                f"[{thread_id}] Service state updated to running with {settings.watch_service_timeout_minutes}min timeout"
            )
            logger.info("WatchService successfully started with asyncio")

            # Starte Background Task
            logger.trace(f"[{thread_id}] Creating background task...")
            task_start = time.time()

            # Task lifecycle tracking
            logger.debug(
                f"Creating background task {id(self._task) if self._task else 'None'} -> {id(asyncio.current_task())}"
            )

            # Async task health check before creation
            if self._task and not self._task.done():
                logger.warning(
                    f"Background task health check: existing task {id(self._task)} is still running"
                )
                # Clean up old task first
                self._task.cancel()
                with contextlib.suppress(
                    asyncio.CancelledError, asyncio.InvalidStateError
                ):
                    await self._task

            self._task = asyncio.create_task(self._watch_loop())
            self._log_trace_timing("task_creation", task_start, thread_id)

            logger.trace(
                f"[{thread_id}] Background task created: {self._task}, task_id: {id(self._task)}"
            )

            # Immediate task health verification
            if self._task.done():
                logger.error(
                    "CRITICAL: Background task completed immediately after creation!"
                )
                raise RuntimeError(
                    "Background task terminated immediately after creation"
                )

            # TRACE: Final state validation with snapshot
            self._log_trace_state(
                "start_watch_service_final", self._shutdown_event.is_set(), thread_id
            )
            final_state = await get_checker_state()
            final_shutdown_state = self._shutdown_event.is_set()

            logger.info(
                f"STATE SNAPSHOT after start: is_running={final_state.is_running}, shutdown_event={final_shutdown_state}, task_id={id(self._task)}"
            )
            logger.trace(
                f"[{thread_id}] Final service state: running={final_state.is_running}, retries={final_state.retries_left}"
            )

            # Post-start validation
            if final_state.is_running == final_shutdown_state:
                logger.error(
                    "POST-START VALIDATION FAILURE: is_running matches shutdown_event state (should be opposite)"
                )
                raise RuntimeError(
                    "State machine validation failed after task creation"
                )

            self._log_trace_timing(
                "start_watch_service_complete", start_time, thread_id
            )
            return final_state

        except Exception as e:
            logger.trace(
                f"[{thread_id}] Exception in start_watch_service: {type(e).__name__}: {e}"
            )
            logger.error(f"Error starting WatchService: {e}")
            await update_checker_state(is_running=False)
            raise

    async def stop_watch_service(self) -> CheckerState:
        """Stops the Background WatchService Task.

        Returns:
            CheckerState: The current state of the WatchService after stopping
        """
        # Capture state snapshot before stopping
        current_state = await get_checker_state()
        logger.info(
            f"STATE SNAPSHOT before stop: is_running={current_state.is_running}, shutdown_event={self._shutdown_event.is_set()}, task={self._task}"
        )

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

        finally:
            # Final state validation
            final_state = await get_checker_state()
            logger.info(
                f"STATE SNAPSHOT after stop: is_running={final_state.is_running}, shutdown_event={self._shutdown_event.is_set()}"
            )

        return final_state

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
        thread_id = str(current_thread())
        logger.info("WatchService Background Task started")

        # TRACE: Task loop entry point
        logger.trace(
            f"[{thread_id}] _watch_loop task started, task_id: {id(asyncio.current_task())}"
        )

        # Task lifecycle tracking - log task creation
        logger.debug(f"Task lifecycle: CREATED task_id={id(asyncio.current_task())}")

        try:
            iteration_count = 0
            settings = (
                get_settings()
            )  # Move settings outside loop to avoid scope issues
            while not self._shutdown_event.is_set():
                iteration_count += 1
                logger.trace(
                    f"[{thread_id}] Starting watch loop iteration {iteration_count}"
                )

                loop_start = time.time()
                self._log_trace_state(
                    "watch_loop_iteration_start",
                    self._shutdown_event.is_set(),
                    thread_id,
                )

                try:
                    await self._execute_clear_task()
                except Exception as e:
                    logger.trace(
                        f"[{thread_id}] Exception in _execute_clear_task: {type(e).__name__}: {e}"
                    )
                    raise

                self._log_trace_timing(
                    f"watch_loop_iteration_{iteration_count}", loop_start, thread_id
                )

                # Warte konfigurierbare Zeit oder bis Shutdown Signal
                try:
                    timeout = (
                        settings.watch_service_timeout_minutes * 60.0
                    )  # in seconds
                    logger.trace(
                        f"[{thread_id}] Waiting for shutdown event or {settings.watch_service_timeout_minutes}min timeout..."
                    )

                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=timeout,
                    )
                    logger.trace(
                        f"[{thread_id}] Shutdown signal received, breaking loop"
                    )
                    break  # Shutdown Signal erhalten
                except TimeoutError:
                    logger.trace(
                        f"[{thread_id}] Timeout reached after {settings.watch_service_timeout_minutes}min, starting next iteration"
                    )
                    continue  # 10 Minuten vorbei, nächster Durchlauf

        except asyncio.CancelledError:
            logger.trace(f"[{thread_id}] WatchService Background Task was cancelled")
            logger.info("WatchService Background Task cancelled")
            # Task lifecycle tracking - log task cancellation
            logger.debug(
                f"Task lifecycle: CANCELLED task_id={id(asyncio.current_task())}"
            )
        except Exception as e:
            logger.trace(
                f"[{thread_id}] Unexpected error in WatchService Loop: {type(e).__name__}: {e}"
            )
            logger.error(f"Unexpected error in WatchService Loop: {e}")
            # Task lifecycle tracking - log task error
            logger.debug(
                f"Task lifecycle: ERROR task_id={id(asyncio.current_task())} error={e}"
            )
        finally:
            logger.trace(
                f"[{thread_id}] WatchService Background Task ending after {iteration_count} iterations"
            )
            logger.info("WatchService Background Task ended")
            # Task lifecycle tracking - log task destruction
            logger.debug(
                f"Task lifecycle: DESTROYED task_id={id(asyncio.current_task())} iterations={iteration_count}"
            )

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
