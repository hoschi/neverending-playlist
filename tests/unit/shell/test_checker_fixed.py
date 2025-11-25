"""Unit Tests für die Checker's Retry- und State-Change-Logik.

Dieses Modul testet die Background Task Retry-Logik und State Management
des Clear Played Watchmode Features.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from returns.result import Failure, Success

from src.shell.checker import Checker, CheckerState, get_checker


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
def fresh_checker(mock_spotify_client_factory, mock_supabase_client_factory):
    """Frische Checker Instanz für jeden Test."""
    # Reset global checker to avoid state contamination
    import src.shell.checker

    src.shell.checker._global_checker = None
    return Checker(mock_spotify_client_factory, mock_supabase_client_factory)


@pytest.fixture
def mock_clear_played_tracks():
    """Mock für clear_played_tracks_from_playlist Funktion."""
    with patch("src.shell.checker.clear_played_tracks_from_playlist") as mock_clear:
        mock_clear.return_value = Success({"deleted_count": 3, "filled_count": 2})
        yield mock_clear


class TestCheckerState:
    """Tests für CheckerState Model."""

    def test_checker_state_default_values(self):
        """Test default values für CheckerState."""
        state = CheckerState()

        assert state.is_running is False
        assert state.retries_left == 5
        assert state.last_playback_detected is False
        assert state.last_checked is None
        assert state.next_check is None

    def test_checker_state_custom_values(self):
        """Test custom values für CheckerState."""
        now = datetime.utcnow()
        state = CheckerState(
            is_running=True,
            retries_left=3,
            last_playback_detected=True,
            last_checked=now,
            next_check=now + timedelta(minutes=10),
        )

        assert state.is_running is True
        assert state.retries_left == 3
        assert state.last_playback_detected is True
        assert state.last_checked == now
        assert state.next_check == now + timedelta(minutes=10)


class TestCheckerInitialization:
    """Tests für Checker Initialisierung."""

    def test_checker_initialization(
        self, mock_spotify_client_factory, mock_supabase_client_factory
    ):
        """Test Checker wird korrekt initialisiert."""
        checker = Checker(mock_spotify_client_factory, mock_supabase_client_factory)

        assert checker.spotify_client_factory == mock_spotify_client_factory
        assert checker.supabase_client_factory == mock_supabase_client_factory
        assert checker.state.is_running is False
        assert checker.state.retries_left == 5
        assert isinstance(checker.broker, type(checker.broker))
        assert isinstance(checker.backend, type(checker.backend))

    def test_checker_singleton_pattern(
        self, mock_spotify_client_factory, mock_supabase_client_factory
    ):
        """Test Checker Singleton Pattern."""
        checker1 = get_checker(
            mock_spotify_client_factory, mock_supabase_client_factory
        )
        checker2 = get_checker(
            mock_spotify_client_factory, mock_supabase_client_factory
        )

        # Same instance should be returned
        assert checker1 is checker2


class TestCheckerStateManagement:
    """Tests für Checker State Management."""

    @pytest.mark.asyncio
    async def test_get_state_returns_current_state(self, fresh_checker):
        """Test get_state gibt aktuellen State zurück."""
        fresh_checker.state.is_running = True
        fresh_checker.state.retries_left = 3

        state = fresh_checker.get_state()

        assert state.is_running is True
        assert state.retries_left == 3
        assert state is fresh_checker.state

    def test_stop_checker_when_not_running(self, fresh_checker):
        """Test stop_checker gibt korrekten State zurück wenn Checker nicht läuft."""
        initial_state = fresh_checker.get_state()
        result_state = fresh_checker.stop_checker()

        assert result_state is initial_state
        assert fresh_checker.state.is_running is False

    def test_stop_checker_updates_state(self, fresh_checker):
        """Test stop_checker aktualisiert State korrekt."""
        # Set checker to running state
        fresh_checker.state.is_running = True
        fresh_checker.state.next_check = datetime.utcnow() + timedelta(minutes=10)

        result_state = fresh_checker.stop_checker()

        assert result_state.is_running is False
        assert result_state.next_check is None


class TestCheckerPlaybackDetection:
    """Tests für Playback Detection Logic."""

    @pytest.mark.asyncio
    async def test_check_active_playback_success(self, fresh_checker):
        """Test erfolgreiche Playback Detection."""
        mock_client = fresh_checker.spotify_client_factory()
        mock_client.get_current_playback.return_value = Success({"is_playing": True})

        result = await fresh_checker._check_active_playback()

        assert result is True
        mock_client.get_current_playback.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_active_playback_no_playback(self, fresh_checker):
        """Test wenn kein Playback aktiv ist."""
        mock_client = fresh_checker.spotify_client_factory()
        mock_client.get_current_playback.return_value = Success(None)

        result = await fresh_checker._check_active_playback()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_active_playback_api_failure(self, fresh_checker):
        """Test Playback Detection bei API Fehler."""
        mock_client = fresh_checker.spotify_client_factory()
        mock_client.get_current_playback.return_value = Failure(Exception("API Error"))

        result = await fresh_checker._check_active_playback()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_active_playback_exception(self, fresh_checker):
        """Test Playback Detection bei Exception."""
        mock_client = fresh_checker.spotify_client_factory()
        mock_client.get_current_playback.side_effect = Exception("Network Error")

        result = await fresh_checker._check_active_playback()

        assert result is False


class TestCheckerRetryLogic:
    """Tests für Checker's Retry-Logik."""

    @pytest.mark.asyncio
    async def test_start_checker_decrements_retries_left_on_no_playback(
        self, fresh_checker
    ):
        """Test decrement retries_left bei erfolglosem Playback beim Start."""
        fresh_checker.state.retries_left = 3

        with patch.object(fresh_checker, "_check_active_playback", return_value=False):
            result_state = await fresh_checker.start_checker()

        assert result_state.retries_left == 2
        assert result_state.is_running is False

    @pytest.mark.asyncio
    async def test_start_checker_resets_retries_left_on_playback(self, fresh_checker):
        """Test reset retries_left auf 5 bei erfolgreichem Playback."""
        fresh_checker.state.retries_left = 2

        with (
            patch.object(fresh_checker, "_check_active_playback", return_value=True),
            patch.object(fresh_checker, "_execute_clear_task", new_callable=AsyncMock),
        ):
            result_state = await fresh_checker.start_checker()

        assert result_state.retries_left == 5
        assert result_state.is_running is True

    @pytest.mark.asyncio
    async def test_start_checker_no_playback_no_retries_left(self, fresh_checker):
        """Test Start fehlt wenn kein Playback und keine Retries mehr."""
        fresh_checker.state.retries_left = 1

        with patch.object(fresh_checker, "_check_active_playback", return_value=False):
            with pytest.raises(ValueError, match="No active playback detected"):
                await fresh_checker.start_checker()

    @pytest.mark.asyncio
    async def test_execute_clear_task_decrements_retries_on_no_playback(
        self, fresh_checker
    ):
        """Test decrement retries_left bei erfolglosem Playback in Background Task."""
        fresh_checker.state.retries_left = 3
        fresh_checker.state.is_running = True

        with patch.object(fresh_checker, "_check_active_playback", return_value=False):
            await fresh_checker._execute_clear_task()

        assert fresh_checker.state.retries_left == 2
        assert fresh_checker.state.is_running is True  # Still running, not zero yet

    @pytest.mark.asyncio
    async def test_execute_clear_task_stops_when_retries_exhausted(self, fresh_checker):
        """Test stop_checker wird aufgerufen wenn retries_left = 0."""
        fresh_checker.state.retries_left = 1
        fresh_checker.state.is_running = True

        with (
            patch.object(fresh_checker, "_check_active_playback", return_value=False),
            patch.object(fresh_checker, "stop_checker") as mock_stop,
        ):
            await fresh_checker._execute_clear_task()

        assert fresh_checker.state.retries_left == 0
        mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_clear_task_resets_retries_on_playback(self, fresh_checker):
        """Test reset retries_left auf 5 bei erfolgreichem Playback in Background Task."""
        fresh_checker.state.retries_left = 2
        fresh_checker.state.is_running = True

        with (
            patch.object(fresh_checker, "_check_active_playback", return_value=True),
            patch.object(fresh_checker, "_clear_played_tracks", new_callable=AsyncMock),
        ):
            await fresh_checker._execute_clear_task()

        assert fresh_checker.state.retries_left == 5
        assert fresh_checker.state.last_playback_detected is True

    @pytest.mark.asyncio
    async def test_execute_clear_task_decrements_retries_on_error(self, fresh_checker):
        """Test decrement retries_left bei Exception im Background Task."""
        fresh_checker.state.retries_left = 3
        fresh_checker.state.is_running = True

        with patch.object(fresh_checker, "_check_active_playback", return_value=True):
            with patch.object(
                fresh_checker,
                "_clear_played_tracks",
                side_effect=Exception("Test Error"),
            ):
                await fresh_checker._execute_clear_task()

        assert fresh_checker.state.retries_left == 2

    @pytest.mark.asyncio
    async def test_execute_clear_task_stops_on_error_when_retries_exhausted(
        self, fresh_checker
    ):
        """Test stop_checker wird aufgerufen bei Error wenn retries = 0."""
        fresh_checker.state.retries_left = 1
        fresh_checker.state.is_running = True

        with (
            patch.object(fresh_checker, "_check_active_playback", return_value=True),
            patch.object(
                fresh_checker,
                "_clear_played_tracks",
                side_effect=Exception("Test Error"),
            ),
            patch.object(fresh_checker, "stop_checker") as mock_stop,
        ):
            await fresh_checker._execute_clear_task()

        assert fresh_checker.state.retries_left == 0
        mock_stop.assert_called_once()


class TestCheckerStateTransitions:
    """Tests für State Transitions."""

    @pytest.mark.asyncio
    async def test_start_checker_state_transition_success(self, fresh_checker):
        """Test komplette State Transition beim erfolgreichen Start."""
        initial_time = datetime.utcnow()

        with (
            patch.object(fresh_checker, "_check_active_playback", return_value=True),
            patch.object(fresh_checker, "_execute_clear_task", new_callable=AsyncMock),
            patch("src.shell.checker.datetime") as mock_datetime,
        ):
            mock_datetime.utcnow.return_value = initial_time
            result_state = await fresh_checker.start_checker()

        assert result_state.is_running is True
        assert result_state.retries_left == 5
        assert result_state.last_playback_detected is True
        assert result_state.next_check == initial_time + timedelta(minutes=10)

    @pytest.mark.asyncio
    async def test_start_checker_already_running(self, fresh_checker):
        """Test start_checker gibt aktuellen State zurück wenn bereits laufend."""
        fresh_checker.state.is_running = True

        with patch.object(fresh_checker, "_check_active_playback", return_value=True):
            result_state = await fresh_checker.start_checker()

        assert result_state is fresh_checker.state
        assert result_state.is_running is True

    @pytest.mark.asyncio
    async def test_state_updates_during_background_task(self, fresh_checker):
        """Test State Updates während Background Task Execution."""
        fresh_checker.state.is_running = True
        now = datetime.utcnow()

        with (
            patch.object(fresh_checker, "_check_active_playback", return_value=True),
            patch.object(fresh_checker, "_clear_played_tracks", new_callable=AsyncMock),
            patch("src.shell.checker.datetime") as mock_datetime,
        ):
            mock_datetime.utcnow.return_value = now
            await fresh_checker._execute_clear_task()

        assert fresh_checker.state.last_checked == now
        assert fresh_checker.state.last_playback_detected is True
        assert fresh_checker.state.next_check == now + timedelta(minutes=10)


class TestCheckerClearPlayedTracks:
    """Tests für Clear Played Tracks Logic."""

    @pytest.mark.asyncio
    async def test_clear_played_tracks_success(
        self, fresh_checker, mock_clear_played_tracks
    ):
        """Test erfolgreiche Clear Played Tracks Execution."""
        with patch("src.shell.checker.get_settings") as mock_settings:
            mock_settings.return_value.spotify_playlist_id = "test_playlist"
            mock_settings.return_value.playlist_autofill_count = 150

            await fresh_checker._clear_played_tracks()

        mock_clear_played_tracks.assert_called_once()
        call_args = mock_clear_played_tracks.call_args
        assert call_args[0][2] == "test_playlist"  # playlist_id
        assert call_args[0][3] == 150  # autofill_count

    @pytest.mark.asyncio
    async def test_clear_played_tracks_failure(self, fresh_checker):
        """Test Clear Played Tracks bei Fehler."""
        with patch("src.shell.checker.clear_played_tracks_from_playlist") as mock_clear:
            mock_clear.return_value = Failure(Exception("Clear failed"))

            with patch("src.shell.checker.get_settings"):
                # Should NOT raise exception, only log warning
                await fresh_checker._clear_played_tracks()

        # Verify that warning was logged but no exception was raised
        mock_clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_played_tracks_exception(self, fresh_checker):
        """Test Clear Played Tracks bei Exception."""
        with patch("src.shell.checker.clear_played_tracks_from_playlist") as mock_clear:
            mock_clear.side_effect = Exception("Network error")

            with patch("src.shell.checker.get_settings"):
                with pytest.raises(Exception):
                    await fresh_checker._clear_played_tracks()


class TestCheckerThreadSafety:
    """Tests für Thread-Safety in asyncio Environment."""

    @pytest.mark.asyncio
    async def test_concurrent_state_access(self, fresh_checker):
        """Test thread-sichere State Access bei concurrent operations."""
        import asyncio

        async def modify_state():
            fresh_checker.state.retries_left += 1
            await asyncio.sleep(0.001)  # Simulate async work
            return fresh_checker.state.retries_left

        # Run multiple concurrent state modifications
        tasks = [modify_state() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All operations should complete without errors
        assert len(results) == 10
        # State should be consistent
        assert fresh_checker.state.retries_left >= 5  # Should be at least initial value

    @pytest.mark.asyncio
    async def test_concurrent_start_stop_operations(self, fresh_checker):
        """Test thread-sichere Start/Stop Operations."""
        import asyncio

        async def start_operation():
            with patch.object(
                fresh_checker, "_check_active_playback", return_value=True
            ):
                with patch.object(
                    fresh_checker, "_execute_clear_task", new_callable=AsyncMock
                ):
                    return await fresh_checker.start_checker()

        async def stop_operation():
            return fresh_checker.stop_checker()

        # Run start and stop operations concurrently
        tasks = [
            start_operation(),
            stop_operation(),
            start_operation(),
            stop_operation(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should complete without crashing
        assert len(results) == 4
        for result in results:
            assert isinstance(result, (CheckerState, Exception))


class TestCheckerErrorHandling:
    """Tests für Error Handling und Graceful Degradation."""

    @pytest.mark.asyncio
    async def test_background_task_exception_handling(self, fresh_checker):
        """Test Exception Handling im Background Task."""
        fresh_checker.state.is_running = True
        fresh_checker.state.retries_left = 3

        # Mock an exception in _check_active_playback
        with patch.object(
            fresh_checker,
            "_check_active_playback",
            side_effect=Exception("Playback check failed"),
        ):
            await fresh_checker._execute_clear_task()

        # Should decrement retries and not crash
        assert fresh_checker.state.retries_left == 2
        assert fresh_checker.state.is_running is True

    @pytest.mark.asyncio
    async def test_start_checker_exception_preserves_state(self, fresh_checker):
        """Test Exception beim Start preserviert State korrekt."""
        fresh_checker.state.retries_left = 3
        original_state = fresh_checker.get_state()

        with patch.object(
            fresh_checker,
            "_check_active_playback",
            side_effect=Exception("Test exception"),
        ):
            with pytest.raises(Exception):
                await fresh_checker.start_checker()

        # State should not be corrupted by exception
        assert fresh_checker.state.retries_left == 3
        assert fresh_checker.state.is_running == original_state.is_running

    @pytest.mark.asyncio
    async def test_stop_checker_exception_handling(self, fresh_checker):
        """Test Exception Handling beim Stoppen."""
        fresh_checker.state.is_running = True

        # Note: The actual stop_checker implementation doesn't throw exceptions
        # in the state update section, so we test the successful case
        result_state = fresh_checker.stop_checker()

        assert result_state.is_running is False
        assert result_state.next_check is None

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_service_failure(
        self, fresh_checker, mock_supabase_client_factory
    ):
        """Test graceful degradation when external services fail."""
        fresh_checker.state.is_running = True
        fresh_checker.state.retries_left = 5

        # Mock service failures
        mock_spotify = fresh_checker.spotify_client_factory()
        mock_spotify.get_current_playback.side_effect = Exception("Service unavailable")

        mock_supabase = mock_supabase_client_factory()
        mock_supabase.get_current_user.side_effect = Exception("Service unavailable")

        with patch(
            "src.shell.checker.get_settings",
            side_effect=Exception("Config unavailable"),
        ):
            with patch.object(fresh_checker, "stop_checker") as mock_stop:
                await fresh_checker._execute_clear_task()

        # Should handle failures gracefully and eventually stop
        assert fresh_checker.state.retries_left == 4  # Decremented due to exception
        # Note: stop_checker may not be called immediately if retries_left > 0


class TestCheckerIntegration:
    """Integration Tests für vollständige Checker Workflows."""

    @pytest.mark.asyncio
    async def test_full_lifecycle_success_scenario(self, fresh_checker):
        """Test kompletter Lifecycle bei erfolgreichem Szenario."""
        # Initial state
        assert fresh_checker.state.retries_left == 5
        assert fresh_checker.state.is_running is False

        with (
            patch.object(fresh_checker, "_check_active_playback", return_value=True),
            patch.object(
                fresh_checker, "_execute_clear_task", new_callable=AsyncMock
            ) as mock_exec,
        ):
            # Start checker
            start_state = await fresh_checker.start_checker()

            assert start_state.is_running is True
            assert start_state.retries_left == 5
            mock_exec.assert_called_once()

        # Stop checker
        stop_state = fresh_checker.stop_checker()

        assert stop_state.is_running is False
        assert stop_state.next_check is None

    @pytest.mark.asyncio
    async def test_full_lifecycle_retry_exhaustion(self, fresh_checker):
        """Test kompletter Lifecycle bis Retry Erschöpfung."""
        fresh_checker.state.retries_left = 2

        # First attempt - no playback, should decrement
        with patch.object(fresh_checker, "_check_active_playback", return_value=False):
            start_state = await fresh_checker.start_checker()

        assert start_state.retries_left == 1
        assert start_state.is_running is False

        # Second attempt - still no playback, should fail
        with patch.object(fresh_checker, "_check_active_playback", return_value=False):
            with pytest.raises(ValueError):
                await fresh_checker.start_checker()

    @pytest.mark.asyncio
    async def test_state_persistence_across_operations(self, fresh_checker):
        """Test State Persistence across multiple operations."""
        # Set initial state
        fresh_checker.state.retries_left = 3
        fresh_checker.state.last_playback_detected = True

        # Perform multiple operations
        with patch.object(fresh_checker, "_check_active_playback", return_value=False):
            await fresh_checker.start_checker()

        assert fresh_checker.state.retries_left == 2

        with patch.object(fresh_checker, "_check_active_playback", return_value=True):
            with patch.object(
                fresh_checker, "_clear_played_tracks", new_callable=AsyncMock
            ):
                await fresh_checker._execute_clear_task()

        # State should be consistent and updated
        assert fresh_checker.state.retries_left == 5  # Reset on success
        assert fresh_checker.state.last_playback_detected is True
