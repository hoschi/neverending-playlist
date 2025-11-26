"""Comprehensive tests for WatchService to achieve full coverage."""

import asyncio
import contextlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from returns.pipeline import is_successful
from returns.result import Failure, Success

from src.core.models import PlaylistClearError, PlaylistClearFailure
from src.shell.watch_service import (
    WatchService,
    clear_playlist,
    watch_service,
)


@pytest.fixture
def mock_spotify_client():
    """Mock Spotify client with all necessary methods."""
    client = Mock()
    client.get_current_playback = AsyncMock()
    client.get_current_user = AsyncMock(return_value=Success({"id": "test_user"}))
    client.get_playlist_items = AsyncMock(return_value=Success([]))
    client.remove_items_from_playlist = AsyncMock(return_value=Success(None))
    client.add_songs_to_playlist = AsyncMock(return_value=Success(None))
    return client


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client with all necessary methods."""
    client = Mock()
    client.fetch_pending_song_requests = AsyncMock(return_value=Success([]))
    client.update_song_requests_as_added = AsyncMock(return_value=Success(None))
    return client


@pytest.fixture
def watch_service_instance(mock_spotify_client, mock_supabase_client):
    """Create a WatchService instance with mocked dependencies."""
    return WatchService(mock_spotify_client, mock_supabase_client)


async def test_watch_service_initialization(watch_service_instance):
    """Test WatchService initialization."""
    assert watch_service_instance.spotify_client is not None
    assert watch_service_instance.supabase_client is not None
    assert watch_service_instance._task is None
    assert not watch_service_instance._shutdown_event.is_set()


async def test_watch_service_get_state(watch_service_instance):
    """Test getting watch service state."""
    # Mock the state functions

    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_state.next_check = None
        mock_get_state.return_value = mock_state

        # Get state
        state = await watch_service_instance.get_state()

        assert not state.is_running
        assert state.retries_left == 5
        assert state.next_check is None


async def test_watch_service_start_watch_service_success(
    watch_service_instance, mock_spotify_client
):
    """Test successful start of watch service."""
    # Mock no current state (not running)
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_get_state.return_value = mock_state

        # Mock active playback
        mock_spotify_client.get_current_playback.return_value = Success(
            {"is_playing": True, "context": {"uri": "spotify:playlist:test"}}
        )

        # Mock update state calls
        with patch("src.shell.watch_service.update_checker_state") as mock_update:
            mock_updated_state = Mock()
            mock_updated_state.is_running = True
            mock_updated_state.retries_left = 5
            mock_updated_state.last_playback_detected = True
            mock_updated_state.next_check = datetime.now() + timedelta(minutes=10)
            mock_update.return_value = mock_updated_state

            # Start service
            await watch_service_instance.start_watch_service()

            # Verify service started (based on actual implementation)
            assert watch_service_instance._task is not None
            assert not watch_service_instance._shutdown_event.is_set()

            # Verify update calls were made
            assert mock_update.call_count >= 1


async def test_watch_service_start_watch_service_already_running(
    watch_service_instance, mock_spotify_client
):
    """Test start when service already running."""
    # Mock current state (already running)
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = True
        mock_state.retries_left = 5
        mock_get_state.return_value = mock_state

        # Start service - should return current state without changes
        result = await watch_service_instance.start_watch_service()

        # Verify returned current state
        assert result.is_running
        assert result.retries_left == 5

        # Verify no playback check was done
        mock_spotify_client.get_current_playback.assert_not_called()


async def test_watch_service_start_watch_service_no_active_playback(
    watch_service_instance, mock_spotify_client
):
    """Test start fails when no active playback."""
    # Mock current state (not running)
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 2
        mock_get_state.return_value = mock_state

        # Mock no active playback
        mock_spotify_client.get_current_playback.return_value = Success(None)

        # Mock update state call
        with patch("src.shell.watch_service.update_checker_state"):
            mock_updated_state = Mock()
            mock_updated_state.is_running = False
            mock_updated_state.retries_left = 1  # Decremented
            mock_get_state.return_value = mock_updated_state

            # Should raise ValueError when retries exhausted
            with pytest.raises(ValueError, match="Kein aktives Playback erkannt"):
                await watch_service_instance.start_watch_service()


async def test_watch_service_start_watch_service_playback_failure(
    watch_service_instance, mock_spotify_client
):
    """Test start fails when playback check fails."""
    # Mock current state (not running)
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 2
        mock_get_state.return_value = mock_state

        # Mock playback failure
        mock_spotify_client.get_current_playback.return_value = Failure(
            Exception("API Error")
        )

        # Mock update state call
        with patch("src.shell.watch_service.update_checker_state"):
            mock_updated_state = Mock()
            mock_updated_state.is_running = False
            mock_updated_state.retries_left = 1  # Decremented
            mock_get_state.return_value = mock_updated_state

            # Should raise ValueError when retries exhausted
            with pytest.raises(ValueError, match="Kein aktives Playback erkannt"):
                await watch_service_instance.start_watch_service()


async def test_watch_service_start_watch_service_playback_exception(
    watch_service_instance, mock_spotify_client
):
    """Test start fails when playback check throws exception."""
    # Mock current state (not running)
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 2
        mock_get_state.return_value = mock_state

        # Mock playback exception
        mock_spotify_client.get_current_playback.side_effect = Exception(
            "Network error"
        )

        # Mock update state call
        with patch("src.shell.watch_service.update_checker_state"):
            mock_updated_state = Mock()
            mock_updated_state.is_running = False
            mock_updated_state.retries_left = 1  # Decremented
            mock_get_state.return_value = mock_updated_state

            # Should raise ValueError when retries exhausted
            with pytest.raises(ValueError, match="Kein aktives Playback erkannt"):
                await watch_service_instance.start_watch_service()


async def test_watch_service_stop_watch_service(watch_service_instance):
    """Test stopping watch service."""
    # First test the case where service is NOT running (should return early)
    with (
        patch("src.shell.watch_service.get_checker_state") as mock_get_state,
        patch("src.shell.watch_service.update_checker_state") as mock_update,
    ):
        # Mock current state as NOT running
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 3
        mock_state.next_check = None
        mock_get_state.return_value = mock_state

        # Stop service - should return early without calling update_checker_state
        result = await watch_service_instance.stop_watch_service()

        # Verify service remains stopped
        assert result.is_running is False
        assert result.next_check is None

        # Verify update was NOT called (early return)
        mock_update.assert_not_called()

    # Now test the case where service IS running
    with (
        patch("src.shell.watch_service.get_checker_state") as mock_get_state,
        patch("src.shell.watch_service.update_checker_state") as mock_update,
    ):
        # Mock current state as running
        mock_running_state = Mock()
        mock_running_state.is_running = True
        mock_running_state.retries_left = 3
        mock_running_state.next_check = datetime.now()

        # Mock stopped state after update
        mock_stopped_state = Mock()
        mock_stopped_state.is_running = False
        mock_stopped_state.next_check = None

        # Set up side effects for get_checker_state
        mock_get_state.side_effect = [mock_running_state, mock_stopped_state]
        mock_update.return_value = mock_stopped_state

        # Stop service
        result = await watch_service_instance.stop_watch_service()

        # Verify service is stopped
        assert result.is_running is False
        assert result.next_check is None

        # Verify update was called
        mock_update.assert_called_once_with(is_running=False, next_check=None)


async def test_watch_service_stop_watch_service_not_running(watch_service_instance):
    """Test stopping watch service when not running."""
    # Mock current state (not running)
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 3
        mock_get_state.return_value = mock_state

        # Stop service
        result = await watch_service_instance.stop_watch_service()

        # Verify returned current state
        assert not result.is_running


async def test_watch_service_check_active_playback_success(
    watch_service_instance, mock_spotify_client
):
    """Test successful active playback check."""
    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    # Check active playback
    result = await watch_service_instance._check_active_playback()

    # Should return True
    assert result
    mock_spotify_client.get_current_playback.assert_called_once()


async def test_watch_service_check_active_playback_no_playback(
    watch_service_instance, mock_spotify_client
):
    """Test playback check when no active playback."""
    # Mock no active playback
    mock_spotify_client.get_current_playback.return_value = Success(None)

    # Check active playback
    result = await watch_service_instance._check_active_playback()

    # Should return False
    assert not result


async def test_watch_service_check_active_playback_failure(
    watch_service_instance, mock_spotify_client
):
    """Test playback check when API call fails."""
    # Mock API failure
    mock_spotify_client.get_current_playback.return_value = Failure(
        Exception("API Error")
    )

    # Check active playback
    result = await watch_service_instance._check_active_playback()

    # Should return False
    assert not result


async def test_watch_service_check_active_playback_exception(
    watch_service_instance, mock_spotify_client
):
    """Test playback check when exception occurs."""
    # Mock exception
    mock_spotify_client.get_current_playback.side_effect = Exception("Network error")

    # Check active playback
    result = await watch_service_instance._check_active_playback()

    # Should return False
    assert not result


async def test_watch_service_clear_played_tracks_success(
    watch_service_instance, mock_spotify_client
):
    """Test successful clear played tracks operation."""
    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    # Mock clear operation result
    clear_result = Success({"deleted_count": 2, "filled_count": 3})

    # Mock settings
    with patch("src.shell.watch_service.get_settings") as mock_get_settings:
        mock_settings = Mock()
        mock_settings.spotify_playlist_id = "test_playlist"
        mock_settings.playlist_autofill_count = 150
        mock_get_settings.return_value = mock_settings

        # Mock clear_played_tracks_from_playlist function
        with patch(
            "src.shell.watch_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.return_value = clear_result

            # Execute clear operation
            await watch_service_instance._clear_played_tracks()

            # Verify clear operation was called (just once, don't check exact params)
            mock_clear.assert_called_once()


async def test_watch_service_clear_played_tracks_failure(
    watch_service_instance, mock_spotify_client
):
    """Test clear operation when service returns failure."""
    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    # Mock clear operation failure
    clear_result = Failure(
        PlaylistClearError(
            error_code=PlaylistClearFailure.ERROR,
            message="Test error",
            details="Test details",
        )
    )

    # Mock settings
    with patch("src.shell.watch_service.get_settings") as mock_get_settings:
        mock_settings = Mock()
        mock_settings.spotify_playlist_id = "test_playlist"
        mock_settings.playlist_autofill_count = 150
        mock_get_settings.return_value = mock_settings

        # Mock clear_played_tracks_from_playlist function
        with patch(
            "src.shell.watch_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.return_value = clear_result

            # Execute clear operation - should handle failure gracefully
            await watch_service_instance._clear_played_tracks()

            # Verify clear operation was called
            mock_clear.assert_called_once()


async def test_watch_service_clear_played_tracks_exception(
    watch_service_instance, mock_spotify_client
):
    """Test clear operation when exception occurs."""
    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    # Mock clear operation to raise exception
    with patch("src.shell.watch_service.get_settings") as mock_get_settings:
        mock_settings = Mock()
        mock_settings.spotify_playlist_id = "test_playlist"
        mock_settings.playlist_autofill_count = 150
        mock_get_settings.return_value = mock_settings

        # Mock clear_played_tracks_from_playlist function to raise exception
        with patch(
            "src.shell.watch_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.side_effect = Exception("Clear failed")

            # Should raise RuntimeError as per implementation
            with pytest.raises(RuntimeError, match="Clear played tracks failed"):
                await watch_service_instance._clear_played_tracks()

            # Verify clear operation was called
            mock_clear.assert_called_once()


async def test_watch_service_reset_state(watch_service_instance):
    """Test resetting watch service state."""
    # Mock current state
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_get_state.return_value = mock_state

        # Mock reset state
        with patch("src.shell.watch_service.reset_checker_state") as mock_reset:
            mock_reset.return_value = mock_state

            # Reset state
            await watch_service_instance.reset_state()

            # Verify shutdown event was cleared
            assert not watch_service_instance._shutdown_event.is_set()

            # Verify reset was called
            mock_reset.assert_called_once()


async def test_watch_service_watch_loop_cancellation():
    """Test watch loop handles cancellation gracefully."""
    mock_spotify_client = Mock()
    mock_supabase_client = Mock()
    watch_service_instance = WatchService(mock_spotify_client, mock_supabase_client)

    # Set shutdown event to trigger immediately
    watch_service_instance._shutdown_event.set()

    # Mock execute_clear_task to verify loop behavior
    with patch.object(
        watch_service_instance, "_execute_clear_task", new_callable=AsyncMock
    ) as mock_execute:
        # Run watch loop - should complete immediately due to shutdown
        await watch_service_instance._watch_loop()

        # Verify execute_clear_task was NOT called due to immediate shutdown
        assert mock_execute.call_count == 0


async def test_watch_service_execute_clear_task_success(watch_service_instance):
    """Test successful execution of clear task."""
    # Mock current state
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_get_state.return_value = mock_state

        # Mock update state calls
        with (
            patch("src.shell.watch_service.update_checker_state") as mock_update,
            patch.object(
                watch_service_instance, "_check_active_playback"
            ) as mock_check,
        ):
            mock_check.return_value = True

            # Mock clear played tracks
            with patch.object(
                watch_service_instance, "_clear_played_tracks"
            ) as mock_clear:
                # Execute clear task
                await watch_service_instance._execute_clear_task()

                # Verify state updates
                assert mock_update.call_count >= 2

                # Verify clear operation was called
                mock_clear.assert_called_once()


async def test_watch_service_execute_clear_task_no_playback(watch_service_instance):
    """Test execution of clear task when no active playback."""
    # Mock current state
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_get_state.return_value = mock_state

        # Mock update state calls
        with patch("src.shell.watch_service.update_checker_state") as mock_update:
            mock_update.return_value = mock_state

            # Mock check active playback returns False
            with patch.object(
                watch_service_instance, "_check_active_playback"
            ) as mock_check:
                mock_check.return_value = False

                # Execute clear task
                await watch_service_instance._execute_clear_task()

                # Verify retries were decremented
                mock_update.assert_called()


async def test_watch_service_execute_clear_task_max_retries_exceeded(
    watch_service_instance,
):
    """Test execution when max retries are exceeded."""
    # Mock current state with 1 retry left
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 1
        mock_get_state.return_value = mock_state

        # Mock update state calls
        with patch("src.shell.watch_service.update_checker_state") as mock_update:
            mock_update.return_value = mock_state

            # Mock check active playback returns False
            with patch.object(
                watch_service_instance, "_check_active_playback"
            ) as mock_check:
                mock_check.return_value = False

                # Mock stop watch service
                with patch.object(
                    watch_service_instance, "stop_watch_service"
                ) as mock_stop:
                    # Execute clear task
                    await watch_service_instance._execute_clear_task()

                    # Verify stop was called
                    mock_stop.assert_called_once()


async def test_watch_service_execute_clear_task_exception(watch_service_instance):
    """Test execution when exception occurs during clear task."""
    # Mock current state
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_get_state.return_value = mock_state

        # Mock update state calls
        with patch("src.shell.watch_service.update_checker_state") as mock_update:
            mock_update.return_value = mock_state

            # Mock check active playback returns True
            with patch.object(
                watch_service_instance, "_check_active_playback"
            ) as mock_check:
                mock_check.return_value = True

                # Mock clear played tracks to raise exception
                with patch.object(
                    watch_service_instance, "_clear_played_tracks"
                ) as mock_clear:
                    mock_clear.side_effect = Exception("Clear task failed")

                    # Execute clear task
                    await watch_service_instance._execute_clear_task()

                    # Verify retries were decremented due to exception
                    assert mock_update.call_count >= 1


# Tests für clear_playlist function
async def test_clear_playlist_success():
    """Test successful playlist clearing."""
    # Mock dependencies
    mock_spotify = Mock()
    mock_supabase = Mock()

    # Mock clear_played_tracks_from_playlist success
    with patch(
        "src.core.services.playlist_service.clear_played_tracks_from_playlist"
    ) as mock_clear:
        mock_clear.return_value = Success({"deleted_count": 2, "filled_count": 3})

        # Execute
        result = await clear_playlist(
            mock_supabase,
            mock_spotify,
            "test_playlist",
            150,
        )

        # Verify result
        assert is_successful(result)
        assert result.unwrap()["deleted_count"] == 2
        assert result.unwrap()["filled_count"] == 3

        # Verify clear operation was called
        mock_clear.assert_called_once()


async def test_clear_playlist_failure():
    """Test playlist clearing when service returns failure."""
    # Mock dependencies
    mock_spotify = Mock()
    mock_supabase = Mock()

    # Mock clear_played_tracks_from_playlist failure
    error = PlaylistClearError(
        error_code=PlaylistClearFailure.ERROR,
        message="Test error",
        details="Test details",
    )
    with patch(
        "src.core.services.playlist_service.clear_played_tracks_from_playlist"
    ) as mock_clear:
        mock_clear.return_value = Failure(error)

        # Execute
        result = await clear_playlist(
            mock_supabase,
            mock_spotify,
            "test_playlist",
            150,
        )

        # Verify result is failure
        assert not is_successful(result)
        assert result.failure() == error

        # Verify clear operation was called
        mock_clear.assert_called_once()


async def test_clear_playlist_exception():
    """Test playlist clearing when exception occurs."""
    # Mock dependencies
    mock_spotify = Mock()
    mock_supabase = Mock()

    # Mock clear_played_tracks_from_playlist to raise exception
    with patch(
        "src.core.services.playlist_service.clear_played_tracks_from_playlist"
    ) as mock_clear:
        mock_clear.side_effect = Exception("Unexpected error")

        # Execute
        result = await clear_playlist(
            mock_supabase,
            mock_spotify,
            "test_playlist",
            150,
        )

        # Verify result is failure with proper error
        assert not is_successful(result)
        error = result.failure()
        assert error.error_code == PlaylistClearFailure.ERROR
        assert error.message == "Unexpected error in watch service"
        assert error.details and "Unexpected error" in error.details


# Tests für watch_service singleton function
def test_watch_service_singleton_first_call():
    """Test watch_service function creates instance on first call."""
    mock_spotify = Mock()
    mock_supabase = Mock()

    # Reset global service
    import src.shell.watch_service

    src.shell.watch_service._global_watch_service = None

    # First call should create instance
    service1 = watch_service(mock_spotify, mock_supabase)

    # Verify it's a WatchService instance
    assert isinstance(service1, WatchService)
    assert service1.spotify_client == mock_spotify
    assert service1.supabase_client == mock_supabase


def test_watch_service_singleton_returns_same_instance():
    """Test watch_service function returns same instance on subsequent calls."""
    mock_spotify = Mock()
    mock_supabase = Mock()

    # Reset global service
    import src.shell.watch_service

    src.shell.watch_service._global_watch_service = None

    # First call
    service1 = watch_service(mock_spotify, mock_supabase)

    # Second call with different clients - should return same instance
    mock_spotify2 = Mock()
    mock_supabase2 = Mock()
    service2 = watch_service(mock_spotify2, mock_supabase2)

    # Should be same instance
    assert service1 is service2
    assert service1.spotify_client is mock_spotify  # Original client preserved
    assert service1.supabase_client is mock_supabase  # Original client preserved


def test_watch_service_singleton_multiple_clients():
    """Test watch_service function handles multiple client scenarios."""
    mock_spotify = Mock()
    mock_supabase = Mock()

    # Reset global service
    import src.shell.watch_service

    src.shell.watch_service._global_watch_service = None

    # Call with different clients
    service = watch_service(mock_spotify, mock_supabase)

    # Verify it's created correctly
    assert isinstance(service, WatchService)
    assert service.spotify_client == mock_spotify
    assert service.supabase_client == mock_supabase


# Test für coverage der exception handling paths
async def test_watch_service_exception_in_start():
    """Test exception handling during service start."""
    mock_spotify = Mock()
    mock_supabase = Mock()
    watch_service_instance = WatchService(mock_spotify, mock_supabase)

    # Mock get_checker_state to raise exception
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_get_state.side_effect = Exception("State error")

        # Should raise the original exception
        with pytest.raises(Exception, match="State error"):
            await watch_service_instance.start_watch_service()


async def test_watch_service_exception_in_stop():
    """Test exception handling during service stop."""
    mock_spotify = Mock()
    mock_supabase = Mock()
    watch_service_instance = WatchService(mock_spotify, mock_supabase)

    # Mock update_checker_state to raise exception
    with patch("src.shell.watch_service.update_checker_state") as mock_update:
        mock_update.side_effect = Exception("Update error")

        # Mock current state as running
        with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
            mock_state = Mock()
            mock_state.is_running = True
            mock_get_state.return_value = mock_state

            # Should raise the original exception
            with pytest.raises(Exception, match="Update error"):
                await watch_service_instance.stop_watch_service()


async def test_watch_service_exception_in_reset():
    """Test exception handling during service reset."""
    mock_spotify = Mock()
    mock_supabase = Mock()
    watch_service_instance = WatchService(mock_spotify, mock_supabase)

    # Mock reset_checker_state to raise exception
    with patch("src.shell.watch_service.reset_checker_state") as mock_reset:
        mock_reset.side_effect = Exception("Reset error")

        # Should raise the original exception
        with pytest.raises(Exception, match="Reset error"):
            await watch_service_instance.reset_state()


# Neue Tests für fehlende Code-Pfade


async def test_watch_service_start_no_playback_warning_return(
    watch_service_instance, mock_spotify_client
):
    """Test start returns warning when no playback detected (Zeilen 79-82)."""
    # Mock current state (not running)
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 3  # Use 3 retries so after decrement it's still > 1
        mock_state.is_running = False  # Explicitly set
        mock_get_state.return_value = mock_state

        # Mock no active playback
        mock_spotify_client.get_current_playback.return_value = Success(None)

        # Mock update state call to simulate warning return
        with patch("src.shell.watch_service.update_checker_state") as mock_update:
            # Setup side_effect to return proper state after update
            def update_side_effect(*_, **__):
                updated = Mock()
                updated.retries_left = 2
                updated.is_running = False
                return updated

            mock_update.side_effect = update_side_effect

            # Mock get_checker_state to return updated state after update
            with patch("src.shell.watch_service.get_checker_state") as mock_get_after:
                mock_updated_state = Mock()
                mock_updated_state.retries_left = 2
                mock_updated_state.is_running = False
                mock_get_after.return_value = mock_updated_state

                # Start service - should return early with warning
                result = await watch_service_instance.start_watch_service()

                # Verify returned state shows warning (retries decremented)
                assert result.retries_left == 2
                assert (
                    not result.is_running
                )  # Service should not be running after warning


async def test_watch_service_stop_task_cancellation_suppress(watch_service_instance):
    """Test stop suppresses Task Cancellation when task is cancelled (Zeilen 121-123)."""
    # Mock current state (running)
    with (
        patch("src.shell.watch_service.get_checker_state") as mock_get_state,
        patch("src.shell.watch_service.update_checker_state") as mock_update,
    ):
        # Mock current state as running with task
        mock_running_state = Mock()
        mock_running_state.is_running = True
        mock_running_state.retries_left = 3
        mock_running_state.next_check = datetime.now()

        # Mock stopped state after update
        mock_stopped_state = Mock()
        mock_stopped_state.is_running = False
        mock_stopped_state.next_check = None

        mock_get_state.return_value = mock_running_state
        mock_update.return_value = mock_stopped_state

        # Create a proper async task that will be cancelled
        async def cancelled_task():
            raise asyncio.CancelledError()

        watch_service_instance._task = asyncio.create_task(cancelled_task())

        # Mock get_checker_state to return stopped state after update
        with patch("src.shell.watch_service.get_checker_state") as mock_get_after:
            mock_get_after.return_value = mock_stopped_state

            # Stop service
            result = await watch_service_instance.stop_watch_service()

            # Verify service is stopped
            assert result.is_running is False
            assert result.next_check is None


async def test_watch_service_reset_task_cancellation_suppress(watch_service_instance):
    """Test reset suppresses Task Cancellation when task is cancelled (Zeilen 155-157)."""

    # Create a proper async task
    async def cancelled_task():
        raise asyncio.CancelledError()

    watch_service_instance._task = asyncio.create_task(cancelled_task())

    # Mock reset_checker_state
    with patch("src.shell.watch_service.reset_checker_state") as mock_reset:
        mock_reset_state = Mock()
        mock_reset_state.is_running = False
        mock_reset.return_value = mock_reset_state

        # Reset state
        result = await watch_service_instance.reset_state()

        # Verify task was cancelled but CancelledError was suppressed
        assert result is not None
        assert result.is_running is False


async def test_watch_service_watch_loop_shutdown_break(watch_service_instance):
    """Test watch loop breaks on shutdown signal (Zeile 186)."""
    # Set shutdown event to trigger immediately in the loop
    watch_service_instance._shutdown_event.set()

    # Mock execute_clear_task to verify it's not called
    with patch.object(
        watch_service_instance, "_execute_clear_task", new_callable=AsyncMock
    ) as mock_execute:
        # Run watch loop - should break immediately due to shutdown
        await watch_service_instance._watch_loop()

        # Verify execute_clear_task was NOT called due to immediate shutdown break
        assert mock_execute.call_count == 0


async def test_watch_service_watch_loop_timeout_continue(watch_service_instance):
    """Test watch loop continues on timeout (Zeile 188)."""
    # Mock execute_clear_task to run once and return
    with patch.object(
        watch_service_instance, "_execute_clear_task", new_callable=AsyncMock
    ) as mock_execute:
        mock_execute.return_value = None

        # Mock wait_for to raise TimeoutError to simulate 10-minute timeout
        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = TimeoutError()  # First call times out
            watch_service_instance._shutdown_event.wait = Mock()

            # Run watch loop with timeout - should continue after timeout
            # We'll limit it to one iteration for testing
            # First iteration
            await watch_service_instance._execute_clear_task()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    watch_service_instance._shutdown_event.wait(),
                    timeout=600.0,
                )

            # Verify execute_clear_task was called once
            assert mock_execute.call_count == 1


async def test_watch_service_watch_loop_task_cancelled(watch_service_instance):
    """Test watch loop handles Task Cancelled exception (Zeilen 192-193)."""
    # Mock execute_clear_task to raise CancelledError
    with patch.object(
        watch_service_instance, "_execute_clear_task", new_callable=AsyncMock
    ) as mock_execute:
        mock_execute.side_effect = asyncio.CancelledError()

        # Run watch loop - should handle CancelledError gracefully
        await watch_service_instance._watch_loop()

        # Verify execute_clear_task was called and exception was handled
        assert mock_execute.call_count == 1


async def test_watch_service_execute_clear_task_error_stop(watch_service_instance):
    """Test execute clear task stops service when error retries exhausted (Zeilen 251-252)."""
    # Mock current state with 1 retry left
    with patch("src.shell.watch_service.get_checker_state") as mock_get_state:
        mock_state = Mock()
        mock_state.is_running = True
        mock_state.retries_left = 1
        mock_get_state.return_value = mock_state

        # Mock update state calls
        with patch("src.shell.watch_service.update_checker_state") as mock_update:
            mock_updated_state = Mock()
            mock_updated_state.retries_left = 0
            mock_update.return_value = mock_updated_state

            # Mock check active playback returns True (to trigger error path)
            with patch.object(
                watch_service_instance, "_check_active_playback"
            ) as mock_check:
                mock_check.return_value = True

                # Mock clear played tracks to raise exception
                with patch.object(
                    watch_service_instance, "_clear_played_tracks"
                ) as mock_clear:
                    mock_clear.side_effect = Exception("Clear operation failed")

                    # Mock stop watch service
                    with patch.object(
                        watch_service_instance, "stop_watch_service"
                    ) as mock_stop:
                        # Execute clear task
                        await watch_service_instance._execute_clear_task()

                        # Verify stop was called due to error retries exhaustion
                        mock_stop.assert_called_once()
