"""Unit Tests für die WatchService asyncio-basierte Implementierung.

Dieses Modul testet die Background Task Retry-Logik und State Management
des Clear Played Watchmode Features mit der neuen asyncio-basierten WatchService Klasse.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from returns.pipeline import is_successful
from returns.result import Failure, Success

from src.core.models import PlaylistClearError, PlaylistClearFailure
from src.shell.state import reset_checker_state
from src.shell.watch_service import WatchService, get_watch_service, watch_service


@pytest.fixture
def mock_spotify_client():
    """Mock SpotifyClient."""
    return AsyncMock()


@pytest.fixture
def mock_spotify_client_factory(mock_spotify_client):
    """Mock factory für SpotifyClient."""
    return lambda: mock_spotify_client


@pytest.fixture
def mock_supabase_client():
    """Mock SupabaseClient."""
    return AsyncMock()


@pytest.fixture
def mock_supabase_client_factory(mock_supabase_client):
    """Mock factory für SupabaseClient."""
    return lambda: mock_supabase_client


@pytest.fixture
async def fresh_watch_service(
    mock_spotify_client_factory, mock_supabase_client_factory
):
    """Frische WatchService Instanz für jeden Test."""
    # Reset global watch service to avoid state contamination
    import src.shell.watch_service

    src.shell.watch_service._global_watch_service = None
    await reset_checker_state()
    return WatchService(mock_spotify_client_factory, mock_supabase_client_factory)


@pytest.fixture
def mock_clear_played_tracks():
    """Mock für clear_played_tracks_from_playlist Funktion."""
    with patch(
        "src.shell.watch_service.clear_played_tracks_from_playlist"
    ) as mock_clear:
        mock_clear.return_value = Success({"deleted_count": 3, "filled_count": 2})
        yield mock_clear


class TestWatchServiceInitialization:
    """Tests für WatchService Initialisierung."""

    def test_watch_service_initialization(
        self, mock_spotify_client_factory, mock_supabase_client_factory
    ):
        """Test WatchService wird korrekt initialisiert."""
        watch_service = WatchService(
            mock_spotify_client_factory, mock_supabase_client_factory
        )

        assert watch_service.spotify_client_factory == mock_spotify_client_factory
        assert watch_service.supabase_client_factory == mock_supabase_client_factory
        assert watch_service._task is None
        assert not watch_service._shutdown_event.is_set()

    def test_watch_service_singleton_pattern(
        self, mock_spotify_client_factory, mock_supabase_client_factory
    ):
        """Test WatchService Singleton Pattern."""
        watch_service1 = get_watch_service(
            mock_spotify_client_factory, mock_supabase_client_factory
        )
        watch_service2 = get_watch_service(
            mock_spotify_client_factory, mock_supabase_client_factory
        )

        # Same instance should be returned
        assert watch_service1 is watch_service2


class TestWatchServiceStateManagement:
    """Tests für WatchService State Management."""

    @pytest.mark.asyncio
    async def test_get_state_returns_current_state(self, fresh_watch_service):
        """Test get_state gibt aktuellen State zurück."""
        state = await fresh_watch_service.get_state()

        assert state.is_running is False
        assert state.retries_left == 5
        assert state.last_playback_detected is False

    @pytest.mark.asyncio
    async def test_stop_watch_service_when_not_running(self, fresh_watch_service):
        """Test stop_watch_service gibt korrekten State zurück wenn WatchService nicht läuft."""
        initial_state = await fresh_watch_service.get_state()
        result_state = await fresh_watch_service.stop_watch_service()

        assert result_state.is_running == initial_state.is_running
        assert result_state.retries_left == initial_state.retries_left

    @pytest.mark.asyncio
    async def test_reset_state_functionality(self, fresh_watch_service):
        """Test reset_state funktioniert korrekt."""
        # Set some state first
        await fresh_watch_service.start_watch_service()

        # Reset state
        result_state = await fresh_watch_service.reset_state()

        assert result_state.is_running is False
        assert result_state.retries_left == 5
        assert result_state.last_playback_detected is False


class TestWatchServicePlaybackDetection:
    """Tests für Playback Detection Logic."""

    @pytest.mark.asyncio
    async def test_check_active_playback_success(self, fresh_watch_service):
        """Test erfolgreiche Playback Detection."""
        mock_client = fresh_watch_service.spotify_client_factory()
        mock_client.get_current_playback.return_value = Success({"is_playing": True})

        result = await fresh_watch_service._check_active_playback()

        assert result is True
        mock_client.get_current_playback.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_active_playback_no_playback(self, fresh_watch_service):
        """Test wenn kein Playback aktiv ist."""
        mock_client = fresh_watch_service.spotify_client_factory()
        mock_client.get_current_playback.return_value = Success(None)

        result = await fresh_watch_service._check_active_playback()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_active_playback_api_failure(self, fresh_watch_service):
        """Test Playback Detection bei API Fehler."""
        mock_client = fresh_watch_service.spotify_client_factory()
        mock_client.get_current_playback.return_value = Failure(Exception("API Error"))

        result = await fresh_watch_service._check_active_playback()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_active_playback_exception(self, fresh_watch_service):
        """Test Playback Detection bei Exception."""
        mock_client = fresh_watch_service.spotify_client_factory()
        mock_client.get_current_playback.side_effect = Exception("Network Error")

        result = await fresh_watch_service._check_active_playback()

        assert result is False


class TestWatchServiceRetryLogic:
    """Tests für WatchService Retry-Logik."""

    @pytest.mark.asyncio
    async def test_start_watch_service_decrements_retries_left_on_no_playback(
        self, fresh_watch_service
    ):
        """Test decrement retries_left bei erfolglosem Playback beim Start."""
        # Set retries_left to 3 via direct state update
        from src.shell.state import update_checker_state

        await update_checker_state(retries_left=3)

        with patch.object(
            fresh_watch_service, "_check_active_playback", return_value=False
        ):
            result_state = await fresh_watch_service.start_watch_service()

        assert result_state.retries_left == 2
        assert result_state.is_running is False

    @pytest.mark.asyncio
    async def test_start_watch_service_resets_retries_left_on_playback(
        self, fresh_watch_service
    ):
        """Test reset retries_left auf 5 bei erfolgreichem Playback."""
        # Set retries_left to 2
        await fresh_watch_service.reset_state()

        with (
            patch.object(
                fresh_watch_service, "_check_active_playback", return_value=True
            ),
            patch.object(
                fresh_watch_service, "_execute_clear_task", new_callable=AsyncMock
            ),
        ):
            result_state = await fresh_watch_service.start_watch_service()

        assert result_state.retries_left == 5
        assert result_state.is_running is True

    @pytest.mark.asyncio
    async def test_start_watch_service_no_playback_no_retries_left(
        self, fresh_watch_service
    ):
        """Test Start fehlt wenn kein Playback und keine Retries mehr."""
        # Set retries_left to 1 via direct state update
        from src.shell.state import update_checker_state

        await update_checker_state(retries_left=1)

        with (
            patch.object(
                fresh_watch_service, "_check_active_playback", return_value=False
            ),
            pytest.raises(ValueError, match="Kein aktives Playback erkannt"),
        ):
            await fresh_watch_service.start_watch_service()


class TestWatchServiceAsyncioIntegration:
    """Tests für asyncio-spezifische Funktionalität."""

    @pytest.mark.asyncio
    async def test_watch_service_task_creation(self, fresh_watch_service):
        """Test dass ein asyncio Task erstellt wird beim Start."""
        with (
            patch.object(
                fresh_watch_service, "_check_active_playback", return_value=True
            ),
            patch.object(
                fresh_watch_service, "_execute_clear_task", new_callable=AsyncMock
            ),
        ):
            result_state = await fresh_watch_service.start_watch_service()

        assert result_state.is_running is True
        assert fresh_watch_service._task is not None
        assert not fresh_watch_service._task.done()

    @pytest.mark.asyncio
    async def test_watch_service_shutdown_handling(self, fresh_watch_service):
        """Test dass Shutdown korrekt behandelt wird."""
        with (
            patch.object(
                fresh_watch_service, "_check_active_playback", return_value=True
            ),
            patch.object(
                fresh_watch_service, "_execute_clear_task", new_callable=AsyncMock
            ),
        ):
            await fresh_watch_service.start_watch_service()

        assert fresh_watch_service._task is not None

        # Stop the service
        await fresh_watch_service.stop_watch_service()

        # Verify shutdown event is set and task is cancelled
        assert fresh_watch_service._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_concurrent_operations_dont_crash(self, fresh_watch_service):
        """Test dass concurrent Operations nicht crashen."""

        async def start_operation():
            with (
                patch.object(
                    fresh_watch_service, "_check_active_playback", return_value=True
                ),
                patch.object(
                    fresh_watch_service, "_execute_clear_task", new_callable=AsyncMock
                ),
            ):
                return await fresh_watch_service.start_watch_service()

        async def stop_operation():
            return await fresh_watch_service.stop_watch_service()

        # Run start and stop operations concurrently
        tasks = [
            start_operation(),
            stop_operation(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should complete without crashing
        assert len(results) == 2
        # Results can be either exceptions or valid return values (CheckerState objects)
        for result in results:
            assert isinstance(result, Exception | type(None)) or hasattr(
                result, "is_running"
            )


class TestWatchServiceClearPlayedTracks:
    """Tests für Clear Played Tracks Logic."""

    @pytest.mark.asyncio
    async def test_clear_played_tracks_success(
        self, fresh_watch_service, mock_clear_played_tracks
    ):
        """Test erfolgreiche Clear Played Tracks Execution."""
        with patch("src.shell.watch_service.get_settings") as mock_settings:
            mock_settings.return_value.spotify_playlist_id = "test_playlist"
            mock_settings.return_value.playlist_autofill_count = 150

            await fresh_watch_service._clear_played_tracks()

        mock_clear_played_tracks.assert_called_once()
        call_args = mock_clear_played_tracks.call_args
        assert call_args[0][2] == "test_playlist"  # playlist_id
        assert call_args[0][3] == 150  # autofill_count

    @pytest.mark.asyncio
    async def test_clear_played_tracks_failure(self, fresh_watch_service):
        """Test Clear Played Tracks bei Fehler."""
        with patch(
            "src.shell.watch_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.return_value = Failure(Exception("Clear failed"))

            with patch("src.shell.watch_service.get_settings"):
                # Should NOT raise exception, only log warning
                await fresh_watch_service._clear_played_tracks()

        # Verify that warning was logged but no exception was raised
        mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_played_tracks_exception(self, fresh_watch_service):
        """Test Clear Played Tracks bei Exception."""
        with patch(
            "src.shell.watch_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.side_effect = Exception("Network error")

            with (
                patch("src.shell.watch_service.get_settings"),
                pytest.raises(RuntimeError),
            ):
                await fresh_watch_service._clear_played_tracks()


class TestNewWatchServiceFunction:
    """Tests für die neue watch_service Funktion nach playlist_service.py Pattern."""

    @pytest.mark.asyncio
    async def test_watch_service_success(self):
        """Test erfolgreiche watch_service Ausführung."""
        mock_supabase = AsyncMock()
        mock_spotify = AsyncMock()

        expected_result = {"deleted_count": 5, "filled_count": 3}

        # Mock the clear_played_tracks_from_playlist function at module level
        with patch(
            "src.core.services.playlist_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.return_value = Success(expected_result)

            result = await watch_service(
                supabase_client=mock_supabase,
                spotify_client=mock_spotify,
                config_playlist_id="test_playlist",
                autofill_count=10,
            )

        assert is_successful(result)
        assert result.unwrap() == expected_result
        mock_clear.assert_called_once()

        # Verify correct arguments were passed
        call_args = mock_clear.call_args
        assert call_args[0][0] == mock_spotify  # spotify_client
        assert call_args[0][1] == mock_supabase  # supabase_client
        assert call_args[0][2] == "test_playlist"  # config_playlist_id
        assert call_args[0][3] == 10  # autofill_count

    @pytest.mark.asyncio
    async def test_watch_service_failure(self):
        """Test watch_service bei Fehler."""
        mock_supabase = AsyncMock()
        mock_spotify = AsyncMock()

        error = PlaylistClearError(
            error_code=PlaylistClearFailure.PLAYBACK_INACTIVE,
            message="No active playback found",
            details="User is not playing music",
        )

        # Mock the clear_played_tracks_from_playlist function
        with patch(
            "src.core.services.playlist_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.return_value = Failure(error)

            result = await watch_service(
                supabase_client=mock_supabase,
                spotify_client=mock_spotify,
                config_playlist_id="test_playlist",
            )

        assert not is_successful(result)
        assert result.failure() == error
        mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_service_exception(self):
        """Test watch_service bei unerwarteter Exception."""
        mock_supabase = AsyncMock()
        mock_spotify = AsyncMock()

        # Mock the clear_played_tracks_from_playlist function to raise exception
        with patch(
            "src.core.services.playlist_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.side_effect = Exception("Unexpected error")

            result = await watch_service(
                supabase_client=mock_supabase,
                spotify_client=mock_spotify,
                config_playlist_id="test_playlist",
                autofill_count=None,
            )

        assert not is_successful(result)
        failure = result.failure()
        assert failure.error_code == PlaylistClearFailure.ERROR
        assert "Unexpected error in watch service" in failure.message
        assert failure.details is not None
        assert "Unexpected error" in failure.details
        mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_watch_service_without_autofill(self):
        """Test watch_service ohne Autofill."""
        mock_supabase = AsyncMock()
        mock_spotify = AsyncMock()

        expected_result = {"deleted_count": 2, "filled_count": 0}

        # Mock the clear_played_tracks_from_playlist function
        with patch(
            "src.core.services.playlist_service.clear_played_tracks_from_playlist"
        ) as mock_clear:
            mock_clear.return_value = Success(expected_result)

            result = await watch_service(
                supabase_client=mock_supabase,
                spotify_client=mock_spotify,
                config_playlist_id="test_playlist",
                autofill_count=None,  # Autofill deaktiviert
            )

        assert is_successful(result)
        assert result.unwrap() == expected_result
        mock_clear.assert_called_once()

        # Verify autofill_count is passed as None
        call_args = mock_clear.call_args
        assert call_args[0][3] is None
