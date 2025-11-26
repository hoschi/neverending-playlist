"""Background task checker for Clear Played Watchmode functionality.

This module implements the background task management for automatically clearing
played tracks from playlists every 10 minutes using asyncio.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from loguru import logger
from pydantic import BaseModel
from returns.pipeline import is_successful

from src.core.config import get_settings
from src.core.protocols import SpotifyClient, SupabaseClient
from src.core.services.playlist_service import clear_played_tracks_from_playlist


class CheckerState(BaseModel):
    """Represents the state of the background checker.

    This Pydantic model tracks the status of the watchmode background task,
    including retry counts, playback detection status, and scheduling information.
    """

    is_running: bool = False
    retries_left: int = 5
    last_playback_detected: bool = False
    last_checked: datetime | None = None
    next_check: datetime | None = None


class Checker:
    """Background task checker for Clear Played Watchmode.

    Manages the state and execution of the automatic playlist clearing
    functionality that runs every 10 minutes using dramatiq.
    """

    def __init__(
        self,
        spotify_client_factory: Callable[[], SpotifyClient],
        supabase_client_factory: Callable[[], SupabaseClient],
    ) -> None:
        """Initialize the checker with client factories.

        Args:
            spotify_client_factory: Factory function to create Spotify clients
            supabase_client_factory: Factory function to create Supabase clients
        """
        self.spotify_client_factory = spotify_client_factory
        self.supabase_client_factory = supabase_client_factory
        self.state: CheckerState = CheckerState()

    async def start_checker(self) -> CheckerState:
        """Start the background checker task.

        Initiates the recurring background task that monitors for active playback
        and automatically clears played tracks from the playlist every 10 minutes.

        Returns:
            CheckerState: The current state of the checker after starting
        """
        if self.state.is_running:
            logger.info("Checker is already running, returning current state")
            return self.state

        try:
            # Check for active playback before starting
            if not await self._check_active_playback():
                if self.state.retries_left <= 1:
                    raise ValueError(
                        "No active playback detected. Checker not started."
                    )
                else:
                    logger.warning(
                        f"No active playback detected. Retries left: {self.state.retries_left - 1}"
                    )
                    self.state.retries_left -= 1
                    return self.state

            # Reset retry counter on successful playback detection
            self.state.retries_left = 5
            self.state.last_playback_detected = True

            # Schedule the background task
            self.state.is_running = True
            self.state.next_check = datetime.now(UTC) + timedelta(minutes=10)

            logger.info("Checker started successfully with dramatiq")

            # Execute initial task
            await self._execute_clear_task()

        except Exception as e:
            logger.error(f"Failed to start checker: {e}")
            raise

        return self.state

    def stop_checker(self) -> CheckerState:
        """Stop the background checker task.

        Returns:
            CheckerState: The current state of the checker after stopping
        """
        if not self.state.is_running:
            logger.info("Checker is not running")
            return self.state

        try:
            # Update state
            self.state.is_running = False
            self.state.next_check = None

            logger.info("Checker stopped successfully")

        except Exception as e:
            logger.error(f"Failed to stop checker: {e}")
            raise

        return self.state

    def get_state(self) -> CheckerState:
        """Get the current checker state.

        Returns:
            CheckerState: The current state of the checker
        """
        return self.state

    async def _execute_clear_task(self) -> None:
        """Execute the background task to clear played tracks.

        This is the main background task function that:
        1. Checks for active playback
        2. Calls the existing clear_played_tracks_from_playlist logic
        3. Updates the checker state based on results
        4. Handles retries and stopping conditions
        """
        try:
            logger.info("Executing clear played tracks background task")

            # Update last checked timestamp
            self.state.last_checked = datetime.now(UTC)

            # Check for active playback
            active_playback = await self._check_active_playback()
            self.state.last_playback_detected = active_playback

            if not active_playback:
                # Handle no active playback scenario
                self.state.retries_left -= 1
                logger.warning(
                    f"No active playback detected. Retries left: {self.state.retries_left}"
                )

                if self.state.retries_left <= 0:
                    logger.error("No retries left, stopping checker")
                    self.stop_checker()
                    return

                return

            # Execute the clear played tracks logic
            await self._clear_played_tracks()

            # Reset retry counter on successful operation
            self.state.retries_left = 5

            # Schedule next check
            self.state.next_check = datetime.now(UTC) + timedelta(minutes=10)

            logger.info("Background task completed successfully")

        except Exception as e:
            logger.error(f"Error in background task: {e}")
            self.state.retries_left -= 1

            if self.state.retries_left <= 0:
                logger.error("No retries left due to errors, stopping checker")
                self.stop_checker()

    async def _check_active_playback(self) -> bool:
        """Check if there is an active playback session.

        Returns:
            bool: True if active playback is detected, False otherwise
        """
        try:
            spotify_client = self.spotify_client_factory()
            current_playback_result = await spotify_client.get_current_playback()

            if not is_successful(current_playback_result):
                return False

            current_playback = current_playback_result.unwrap()
            return current_playback is not None

        except Exception as e:
            logger.error(f"Failed to check active playback: {e}")
            return False

    async def _clear_played_tracks(self) -> None:
        """Execute the clear played tracks logic using existing service.

        This calls the existing clear_played_tracks_from_playlist function
        from playlist_service.py which contains the core business logic.
        """
        try:
            settings = get_settings()
            spotify_client = self.spotify_client_factory()
            supabase_client = self.supabase_client_factory()

            # Call the existing core logic for clearing played tracks
            result = await clear_played_tracks_from_playlist(
                spotify_client,
                supabase_client,
                settings.spotify_playlist_id,
                settings.playlist_autofill_count,
            )

            if is_successful(result):
                logger.info("Successfully cleared played tracks from playlist")
            else:
                error = result.failure()
                logger.warning(f"Clear played tracks failed: {error}")

        except Exception as e:
            logger.error(f"Failed to clear played tracks: {e}")
            raise RuntimeError(f"Clear played tracks failed: {e}") from e


# Global checker instance for single instance pattern
_global_checker: Checker | None = None


def get_checker(
    spotify_client_factory: Callable[[], SpotifyClient],
    supabase_client_factory: Callable[[], SupabaseClient],
) -> Checker:
    """Get the global checker instance.

    This function implements a singleton pattern to ensure only one
    checker instance runs across the application.

    Args:
        spotify_client_factory: Factory function to create Spotify clients
        supabase_client_factory: Factory function to create Supabase clients

    Returns:
        Checker: The global checker instance
    """
    global _global_checker

    if _global_checker is None:
        _global_checker = Checker(spotify_client_factory, supabase_client_factory)

    return _global_checker
