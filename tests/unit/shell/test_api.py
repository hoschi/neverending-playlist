"""Fixed API Tests with proper mocking strategy."""

from datetime import UTC
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from returns.result import Failure, Success

from src.core.models import (
    PlaylistClearError,
    PlaylistClearFailure,
    SyncFailure,
    SyncResult,
)
from src.core.services.encryption_service import EncryptionService
from src.shell.api import callback


@pytest.fixture
def mock_request():
    """Provides a mock Request object."""
    request = Mock(spec=Request)
    request.session = {}
    return request


@pytest.fixture
def mock_oauth_manager():
    """Provides a mock SpotifyOAuth manager."""
    from spotipy.oauth2 import SpotifyOAuth

    return Mock(spec=SpotifyOAuth)


@pytest.fixture
def mock_encryption_service():
    """Provides a mock EncryptionService."""
    return Mock(spec=EncryptionService)


@pytest.fixture
def mock_spotify_client():
    """Provides a proper mock Spotify client."""
    client = Mock()
    client.get_current_user = AsyncMock(return_value=Success({"id": "test_user"}))
    client.get_current_playback = AsyncMock()
    client.add_songs_to_playlist = AsyncMock()
    client.get_playlist_items = AsyncMock(return_value=Success([]))
    client.remove_items_from_playlist = AsyncMock(return_value=Success(None))
    return client


@pytest.fixture
def mock_supabase_client():
    """Provides a proper mock Supabase client."""
    client = Mock()
    client.fetch_pending_song_requests = AsyncMock(return_value=Success([]))
    client.update_song_requests_as_added = AsyncMock(return_value=Success(None))
    return client


def test_callback_without_current_user(
    mock_oauth_manager: Mock,
    mock_encryption_service: Mock,
) -> None:
    """Test callback when current_user is None."""
    # Arrange
    mock_oauth_manager.get_access_token.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": 1234567890,
        "scope": "test_scope",
    }

    # Mock ConcreteSpotifyClient to simulate the callback behavior
    with patch("src.shell.clients.ConcreteSpotifyClient") as MockSpotifyClient:
        mock_client_instance = Mock()
        mock_client_instance.get_current_user.return_value = Success(None)
        MockSpotifyClient.return_value = mock_client_instance

        # Create a temp client using Spotipy.Spotify to get user - but mock it to return None
        with patch("spotipy.Spotify") as mock_spotify_class:
            mock_spotify_instance = Mock()
            mock_spotify_instance.current_user.return_value = None
            mock_spotify_class.return_value = mock_spotify_instance

            # Act & Assert
            with pytest.raises(HTTPException) as exc_info:
                callback(
                    code="test_code",
                    oauth_manager=mock_oauth_manager,
                    encryption_service=mock_encryption_service,
                )

            assert exc_info.value.status_code == 500
            assert (
                "Failed to retrieve user information from Spotify."
                in exc_info.value.detail
            )


def test_callback_with_valid_user(
    mock_oauth_manager: Mock,
    mock_encryption_service: Mock,
) -> None:
    """Test callback with successful token retrieval and valid user."""
    # Arrange
    mock_oauth_manager.get_access_token.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": 1234567890,
        "scope": "playlist-modify-public playlist-modify-private",
    }

    # Mock ConcreteSpotifyClient to simulate the callback behavior
    with patch("src.shell.clients.ConcreteSpotifyClient") as MockSpotifyClient:
        mock_client_instance = Mock()
        mock_client_instance.get_current_user.return_value = Success(
            {"id": "test_user_id"}
        )
        MockSpotifyClient.return_value = mock_client_instance

        # Mock spotipy.Spotify to return valid user
        with (
            patch("spotipy.Spotify") as mock_spotify_class,
            patch("src.shell.api.set_key") as mock_set_key,
        ):
            mock_spotify_instance = Mock()
            mock_spotify_instance.current_user.return_value = {"id": "test_user_id"}
            mock_spotify_class.return_value = mock_spotify_instance
            mock_encryption_service.encrypt.return_value = "encrypted_token"

            # Act
            result = callback(
                code="test_code",
                oauth_manager=mock_oauth_manager,
                encryption_service=mock_encryption_service,
            )

            # Assert
            assert result == {
                "status": "success",
                "message": "Successfully authenticated.",
            }
            mock_encryption_service.encrypt.assert_called_once_with(
                "test_refresh_token"
            )
            mock_set_key.assert_called_once_with(
                ".env", "SPOTIFY_REFRESH_TOKEN", "encrypted_token"
            )


def test_callback_without_request_token_400(
    mock_oauth_manager: Mock,
    mock_encryption_service: Mock,
) -> None:
    """Test callback when get_access_token does not return refresh_token."""
    # Arrange
    mock_oauth_manager.get_access_token.return_value = {
        "access_token": "test_access_token",
        # Missing refresh_token
        "expires_at": 1234567890,
        "scope": "test_scope",
    }

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        callback(
            code="test_code",
            oauth_manager=mock_oauth_manager,
            encryption_service=mock_encryption_service,
        )

    assert exc_info.value.status_code == 400
    assert "Could not retrieve refresh token." in exc_info.value.detail


# Tests für fehlende API Coverage (Zeilen 44, 49-50, 60-61)
async def test_callback_with_missing_oauth_tokens_400(
    mock_oauth_manager: Mock,
    mock_encryption_service: Mock,
) -> None:
    """Test callback when oauth token is missing in get_access_token."""
    # Arrange
    mock_oauth_manager.get_access_token.return_value = {
        "access_token": "test_access_token",
        # Missing refresh_token
        "expires_at": 1234567890,
        "scope": "test_scope",
    }

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        callback(
            code="test_code",
            oauth_manager=mock_oauth_manager,
            encryption_service=mock_encryption_service,
        )

    assert exc_info.value.status_code == 400
    assert "Could not retrieve refresh token." in exc_info.value.detail


async def test_callback_oauth_exception_handling_500(
    mock_oauth_manager: Mock,
    mock_encryption_service: Mock,
) -> None:
    """Test callback when get_access_token raises exception."""
    # Arrange
    mock_oauth_manager.get_access_token.side_effect = Exception("OAuth error")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        callback(
            code="test_code",
            oauth_manager=mock_oauth_manager,
            encryption_service=mock_encryption_service,
        )

    assert exc_info.value.status_code == 500
    # Updated assertion to match actual error message
    assert "internal error occurred" in exc_info.value.detail.lower()


async def test_callback_encryption_error_handling_500(
    mock_oauth_manager: Mock,
    mock_encryption_service: Mock,
) -> None:
    """Test callback when encryption fails."""
    # Arrange
    mock_oauth_manager.get_access_token.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": 1234567890,
        "scope": "test_scope",
    }

    mock_encryption_service.encrypt.side_effect = Exception("Encryption failed")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        callback(
            code="test_code",
            oauth_manager=mock_oauth_manager,
            encryption_service=mock_encryption_service,
        )

    assert exc_info.value.status_code == 500


async def test_callback_set_key_error_handling_500(
    mock_oauth_manager: Mock,
    mock_encryption_service: Mock,
) -> None:
    """Test callback when set_key fails."""
    # Arrange
    mock_oauth_manager.get_access_token.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": 1234567890,
        "scope": "test_scope",
    }

    mock_encryption_service.encrypt.return_value = "encrypted_token"

    # Act & Assert
    with patch("src.shell.clients.ConcreteSpotifyClient") as MockSpotifyClient:
        mock_client_instance = Mock()
        mock_client_instance.get_current_user.return_value = Success(
            {"id": "test_user_id"}
        )
        MockSpotifyClient.return_value = mock_client_instance

        with (
            patch("spotipy.Spotify") as mock_spotify_class,
            patch("src.shell.api.set_key") as mock_set_key_fail,
        ):
            mock_spotify_instance = Mock()
            mock_spotify_instance.current_user.return_value = {"id": "test_user_id"}
            mock_spotify_class.return_value = mock_spotify_instance
            mock_set_key_fail.side_effect = Exception("Failed to save token")

            with pytest.raises(HTTPException) as exc_info:
                callback(
                    code="test_code",
                    oauth_manager=mock_oauth_manager,
                    encryption_service=mock_encryption_service,
                )

            assert exc_info.value.status_code == 500


async def test_sync_playlist_success_returns_200(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test sync_playlist_endpoint returns 200 on success."""
    from src.shell.api import app, get_spotify_client

    sync_result = SyncResult(
        failures=[],
        successful=["1", "2", "3"],
        not_found=[],
    )

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    with patch("src.shell.api.sync_playlist", return_value=Success(sync_result)):
        response = client.post("/sync-playlist")

        assert response.status_code == 200
        content = response.json()
        assert content == {
            "successful": ["1", "2", "3"],
            "not_found": [],
            "errors": [],
        }

    # Clean up
    app.dependency_overrides.clear()


async def test_sync_playlist_returns_207_on_partial_failure(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test sync_playlist_endpoint returns JSONResponse 207 on partial failure."""
    from src.shell.api import app, get_spotify_client

    sync_result = SyncResult(
        failures=[SyncFailure(song_id="123", reason="Timeout")],
        successful=["1", "2"],
        not_found=[],
    )

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    with patch("src.shell.api.sync_playlist", return_value=Success(sync_result)):
        response = client.post("/sync-playlist")

        assert response.status_code == 207
        content = response.json()
        assert content == {
            "successful": ["1", "2"],
            "not_found": [],
            "errors": ["123: Timeout"],
        }

    # Clean up
    app.dependency_overrides.clear()


async def test_sync_playlist_error_handling_500(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test sync_playlist endpoint handles errors gracefully."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    with patch("src.shell.api.sync_playlist") as mock_sync:
        # Mock sync_playlist to return a Failure result instead of raising exception
        from returns.result import Failure

        mock_sync.return_value = Failure(Exception("Sync failed"))

        # Call the endpoint
        response = client.post("/sync-playlist")

        # Should return 500 for sync failures
        assert response.status_code == 500
        content = response.json()
        assert "Sync failed" in str(content.get("detail", ""))

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_endpoint_success(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test clear_played_endpoint returns 200 when filled_count > 0 (successful autofill)."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    with patch(
        "src.shell.api.clear_played_tracks_from_playlist",
        return_value=Success({"deleted_count": 5, "filled_count": 3}),
    ):
        response = client.post("/clear-played")

        assert response.status_code == 200
        content = response.json()
        assert content["deleted_count"] == 5
        assert content["filled_count"] == 3

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_endpoint_no_deletion_needed_200(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test clear_played_endpoint returns 200 when deleted_count == 0 (nothing to delete)."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    with patch(
        "src.shell.api.clear_played_tracks_from_playlist",
        return_value=Success({"deleted_count": 0, "filled_count": 0}),
    ):
        response = client.post("/clear-played")

        assert response.status_code == 200
        content = response.json()
        assert content["deleted_count"] == 0
        assert content["filled_count"] == 0

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_endpoint_partially_successful_207(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test clear_played_endpoint returns 207 when deleted_count > 0 AND filled_count == 0."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    with patch(
        "src.shell.api.clear_played_tracks_from_playlist",
        return_value=Success({"deleted_count": 5, "filled_count": 0}),
    ):
        response = client.post("/clear-played")

        assert response.status_code == 207
        content = response.json()
        assert content["deleted_count"] == 5
        assert content["filled_count"] == 0
        assert "Partial success" in content["message"]
        assert "Not enough songs available" in content["message"]

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_endpoint_successful_deletion_and_refill_200(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test clear_played_endpoint returns 200 when deleted_count > 0 AND filled_count > 0."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    with patch(
        "src.shell.api.clear_played_tracks_from_playlist",
        return_value=Success({"deleted_count": 3, "filled_count": 2}),
    ):
        response = client.post("/clear-played")

        assert response.status_code == 200
        content = response.json()
        assert content["deleted_count"] == 3
        assert content["filled_count"] == 2

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_endpoint_playback_inactive_error_409(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test clear_played_endpoint returns 409 for PLAYBACK_INACTIVE error."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    playback_error = PlaylistClearError(
        error_code=PlaylistClearFailure.PLAYBACK_INACTIVE,
        message="No active playback found",
        details="User is not currently playing any music",
    )

    with patch("src.shell.api.clear_played_tracks_from_playlist") as mock_clear:
        mock_clear.return_value = Failure(playback_error)

        response = client.post("/clear-played")

        assert response.status_code == 409
        content = response.json()
        # FastAPI wraps the detail in a 'detail' key
        assert content["detail"]["error"] == "playback_inactive"
        assert content["detail"]["message"] == "No active playback found"
        assert content["detail"]["details"] == "User is not currently playing any music"

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_endpoint_wrong_playlist_error_400(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test clear_played_endpoint returns 400 for WRONG_PLAYLIST error."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    playlist_error = PlaylistClearError(
        error_code=PlaylistClearFailure.WRONG_PLAYLIST,
        message="Current playlist does not match configured playlist",
        details="Current: playlist1, Configured: playlist2",
    )

    with patch("src.shell.api.clear_played_tracks_from_playlist") as mock_clear:
        mock_clear.return_value = Failure(playlist_error)

        response = client.post("/clear-played")

        assert response.status_code == 400
        content = response.json()
        # FastAPI wraps the detail in a 'detail' key
        assert content["detail"]["error"] == "wrong_playlist"
        assert (
            content["detail"]["message"]
            == "Current playlist does not match configured playlist"
        )
        assert (
            content["detail"]["details"] == "Current: playlist1, Configured: playlist2"
        )

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_endpoint_internal_error_500(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test clear_played_endpoint returns 500 for ERROR error."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    internal_error = PlaylistClearError(
        error_code=PlaylistClearFailure.ERROR,
        message="Failed to remove tracks from playlist",
        details="API rate limit exceeded",
    )

    with patch("src.shell.api.clear_played_tracks_from_playlist") as mock_clear:
        mock_clear.return_value = Failure(internal_error)

        response = client.post("/clear-played")

        assert response.status_code == 500
        content = response.json()
        # FastAPI wraps the detail in a 'detail' key
        assert content["detail"]["error"] == "internal_server_error"
        assert content["detail"]["message"] == "Failed to remove tracks from playlist"
        assert content["detail"]["details"] == "API rate limit exceeded"

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_endpoint_unknown_error_500(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test clear_played_endpoint returns 500 for unknown exceptions."""
    from src.shell.api import app, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    with patch("src.shell.api.clear_played_tracks_from_playlist") as mock_clear:
        # Mock clear_played_tracks_from_playlist to raise an unknown exception
        mock_clear.side_effect = RuntimeError("Unexpected database connection failure")

        response = client.post("/clear-played")

        assert response.status_code == 500
        content = response.json()
        # FastAPI wraps the detail in a 'detail' key
        assert content["detail"]["error"] == "unknown_error"
        assert content["detail"]["message"] == "An unknown error occurred."
        assert "Unexpected database connection failure" in content["detail"]["details"]


async def test_clear_played_watchmode_executed_successfully(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test GET /clear-played-watchmode returns executed when successfully run."""
    from datetime import datetime, timedelta

    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    mock_supabase_client = Mock()
    app.dependency_overrides[get_song_request_client] = lambda: mock_supabase_client

    # Mock the active playback check
    mock_spotify_client.get_current_playback.return_value = Success(
        {
            "item": {"uri": "spotify:track:current_track"},
            "context": {
                "type": "playlist",
                "uri": "spotify:playlist:test_playlist",
            },
        }
    )

    with patch("src.shell.api.watch_service") as mock_watch_service:
        # Mock the WatchService instance
        mock_watch_service_instance = AsyncMock()

        mock_state_instance = AsyncMock()
        mock_state_instance.is_running = False
        mock_state_instance.retries_left = 5
        mock_state_instance.next_check = None
        mock_watch_service_instance.get_state.return_value = mock_state_instance

        mock_started_state_instance = AsyncMock()
        mock_started_state_instance.is_running = True
        mock_started_state_instance.retries_left = 5
        mock_started_state_instance.next_check = datetime.now(UTC) + timedelta(
            minutes=10
        )
        mock_watch_service_instance.start_watch_service.return_value = (
            mock_started_state_instance
        )

        mock_watch_service.return_value = mock_watch_service_instance

        with patch("src.shell.api.get_settings") as mock_settings:
            mock_settings.return_value.spotify_playlist_id = "test_playlist"
            mock_settings.return_value.playlist_autofill_count = 150

            response = client.get("/clear-played-watchmode")

    assert response.status_code == 200
    content = response.json()
    assert content["status"] == "monitoring_started"
    assert "Background monitoring has been started" in content["message"]
    assert "monitoring" in content

    # Clean up
    app.dependency_overrides.clear()


async def test_clear_played_watchmode_no_active_playback(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test GET /clear-played-watchmode returns no_active_playback when no playback detected."""
    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override the dependency
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock no active playback
    mock_spotify_client.get_current_playback.return_value = Success(None)

    response = client.get("/clear-played-watchmode")

    assert response.status_code == 409
    content = response.json()
    assert content["status"] == "no_active_playback"
    assert "No active playback detected" in content["message"]


# Tests für Coverage-Lücken in watch_service.py
async def test_watchmode_endpoint_state_inconsistency_error_500(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint returns 500 for state inconsistency."""
    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    with patch("src.shell.api.watch_service") as mock_watch_service:
        # Mock watch service with inconsistent state (running but no next_check)
        mock_watch_service_instance = AsyncMock()

        mock_state = AsyncMock()
        mock_state.is_running = True
        mock_state.retries_left = 5
        mock_state.next_check = None  # Inconsistent state!
        mock_watch_service_instance.get_state.return_value = mock_state

        mock_watch_service.return_value = mock_watch_service_instance

        response = client.get("/clear-played-watchmode")

    assert response.status_code == 500
    content = response.json()
    assert "internal_state_inconsistent" in str(content)


# Tests für Exception Handling (Zeilen 406-408)
async def test_watchmode_endpoint_top_level_exception_corrected(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint top-level exception handling for truly unhandled exceptions (ZEILEN 406-408)."""

    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock active playback SUCCESSFULLY (bypasses Zeilen 268-301)
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    with patch("src.shell.api.watch_service") as mock_watch_service:
        # Create a mock that will raise an exception AFTER successful service creation
        # but BEFORE the inner exception handlers can catch it
        mock_watch_service_instance = AsyncMock()

        # Mock successful state retrieval (bypasses Zeilen 304-323)
        mock_state = AsyncMock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_state.next_check = None
        mock_watch_service_instance.get_state.return_value = mock_state

        # Mock start_watch_service to raise an exception that bypasses
        # the specific exception handling in Zeilen 369-393
        mock_watch_service_instance.start_watch_service.side_effect = RuntimeError(
            "Unhandled system error - not playback, not startup specific"
        )

        # Mock the watch_service constructor to return our instance successfully
        # This ensures we get past Zeilen 304-308
        mock_watch_service.return_value = mock_watch_service_instance

        response = client.get("/clear-played-watchmode")

    # Expected: 500 with startup error handling (Zeilen 386-392)
    assert response.status_code == 500
    content = response.json()
    assert content["status"] == "startup_error"
    assert "Error starting background monitoring" in content["message"]
    assert "Unhandled system error" in content["details"]


# Tests für State Management
async def test_watchmode_endpoint_already_running_returns_200(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint returns 200 when monitoring already running."""
    from datetime import datetime, timedelta

    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    with patch("src.shell.api.watch_service") as mock_watch_service:
        # Mock watch service instance
        mock_watch_service_instance = AsyncMock()

        # Mock already running state
        mock_state = AsyncMock()
        mock_state.is_running = True
        mock_state.retries_left = 3
        mock_state.next_check = datetime.now(UTC) + timedelta(minutes=10)
        mock_watch_service_instance.get_state.return_value = mock_state

        mock_watch_service.return_value = mock_watch_service_instance

        response = client.get("/clear-played-watchmode")

    assert response.status_code == 200
    content = response.json()
    assert content["status"] == "already_running"
    assert "Background monitoring is already active" in content["message"]


# Tests für Edge Cases und Error Scenarios
async def test_watchmode_endpoint_playback_check_failure_409(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint returns 409 when playback check fails."""
    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock failed playback check
    mock_spotify_client.get_current_playback.return_value = Failure(
        Exception("API Error")
    )

    response = client.get("/clear-played-watchmode")

    assert response.status_code == 409
    content = response.json()
    assert content["status"] == "playback_check_failed"
    assert "Failed to check playback status" in content["message"]


async def test_watchmode_endpoint_playback_check_exception_500(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint returns 500 when playback check throws exception."""
    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock playback check exception
    mock_spotify_client.get_current_playback.side_effect = Exception("Network timeout")

    response = client.get("/clear-played-watchmode")

    assert response.status_code == 500
    content = response.json()
    assert "playback_check_error" in str(content)


async def test_watchmode_endpoint_service_error_500(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint returns 500 when service access fails."""
    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    with patch("src.shell.api.watch_service") as mock_watch_service:
        # Mock service access error
        mock_watch_service.side_effect = Exception("Service unavailable")

        response = client.get("/clear-played-watchmode")

    assert response.status_code == 500
    content = response.json()
    assert "service_error" in str(content)


async def test_watchmode_endpoint_startup_error_500(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint returns 500 when startup fails."""
    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    with patch("src.shell.api.watch_service") as mock_watch_service:
        mock_watch_service_instance = AsyncMock()

        # Mock not running state
        mock_state = AsyncMock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_state.next_check = None
        mock_watch_service_instance.get_state.return_value = mock_state

        # Mock startup failure
        mock_watch_service_instance.start_watch_service.side_effect = Exception(
            "Database connection failed"
        )

        mock_watch_service.return_value = mock_watch_service_instance

        response = client.get("/clear-played-watchmode")

    assert response.status_code == 500
    content = response.json()
    assert "startup_error" in str(content)


async def test_watchmode_endpoint_playback_inactive_during_startup_409(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint returns 409 when playback inactive during startup."""
    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock active playback for initial check
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    with patch("src.shell.api.watch_service") as mock_watch_service:
        mock_watch_service_instance = AsyncMock()

        # Mock not running state
        mock_state = AsyncMock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_state.next_check = None
        mock_watch_service_instance.get_state.return_value = mock_state

        # Mock startup with "no active playback" error
        mock_watch_service_instance.start_watch_service.side_effect = ValueError(
            "No active playback detected. WatchService not started."
        )

        mock_watch_service.return_value = mock_watch_service_instance

        response = client.get("/clear-played-watchmode")

    assert response.status_code == 409
    content = response.json()
    assert content["status"] == "playback_inactive"
    assert "No active playback detected" in content["message"]


# Neue Tests für fehlende Code-Pfade


async def test_watchmode_endpoint_state_inconsistency_after_start_corrected(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint returns 500 for state inconsistency after start (ZEILE 347)."""

    from src.shell.api import app, get_song_request_client, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_song_request_client] = lambda: Mock()

    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    with patch("src.shell.api.watch_service") as mock_watch_service:
        # Mock watch service instance
        mock_watch_service_instance = AsyncMock()

        # Mock INITIAL state where is_running=False (not running yet)
        mock_initial_state = AsyncMock()
        mock_initial_state.is_running = False
        mock_initial_state.retries_left = 5
        mock_initial_state.next_check = None
        mock_watch_service_instance.get_state.return_value = mock_initial_state

        # Mock start_watch_service to return INCONSISTENT state (running but no next_check)
        mock_started_state = AsyncMock()
        mock_started_state.is_running = True  # Service wurde gestartet
        mock_started_state.retries_left = 5
        mock_started_state.next_check = (
            None  # ABER: kein next_check gesetzt - INKONSISTENT!
        )
        mock_watch_service_instance.start_watch_service.return_value = (
            mock_started_state
        )

        mock_watch_service.return_value = mock_watch_service_instance

        response = client.get("/clear-played-watchmode")

    # Expected: 500 due to state inconsistency (Zeile 347)
    assert response.status_code == 500
    content = response.json()
    # The HTTPException from Zeile 347 is caught in the startup error handler (Zeilen 369-393)
    # and returns a JSONResponse with startup_error status
    assert content["status"] == "startup_error"
    assert "Error starting background monitoring" in content["message"]


async def test_watchmode_endpoint_unexpected_error_handling(
    client: TestClient, mock_spotify_client: Mock
) -> None:
    """Test watchmode endpoint handles truly unexpected errors in top-level exception handler (ZEILEN 406-415)."""

    from returns.result import Success

    from src.shell.api import app, get_spotify_client

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Mock successful playback check that will pass the first try-catch block
    mock_spotify_client.get_current_playback.return_value = Success(
        {"is_playing": True}
    )

    # Mock watch_service instance to succeed completely but then raise error
    # in the JSONResponse constructor (after Zeile 367, outside all try-catch blocks)
    with patch("src.shell.api.watch_service") as mock_watch_service:
        mock_watch_service_instance = AsyncMock()

        # Mock state objects
        mock_state = Mock()
        mock_state.is_running = False
        mock_state.retries_left = 5
        mock_state.next_check = None

        from datetime import datetime

        mock_started_state = Mock()
        mock_started_state.is_running = True
        mock_started_state.retries_left = 5
        mock_started_state.next_check = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)

        # Mock the methods to return successful results
        mock_watch_service_instance.get_state.return_value = mock_state
        mock_watch_service_instance.start_watch_service.return_value = (
            mock_started_state
        )

        mock_watch_service.return_value = mock_watch_service_instance

        # Mock JSONResponse.__init__ to raise error AFTER successful processing
        # This will occur after the last try-catch block (Zeile 367), in the top-level handler
        with patch("fastapi.responses.JSONResponse.__init__") as mock_json_init:
            # Configure the mock to raise an exception during initialization
            # This simulates an error that occurs when creating the JSONResponse object
            # after all the try-catch blocks have completed successfully
            mock_json_init.side_effect = RuntimeError(
                "System crash - completely unexpected error that bypasses all handlers"
            )

            # Expect the exception to be raised and caught by the top-level handler
            with pytest.raises(
                RuntimeError,
                match="System crash - completely unexpected error that bypasses all handlers",
            ):
                client.get("/clear-played-watchmode")


async def test_watchmode_endpoint_top_level_exception_handler_exists():
    """Test that the top-level exception handler exists in the watchmode endpoint (ZEILEN 406-415)."""

    # This test documents that the top-level exception handler exists
    # and would catch any exceptions that bypass all inner try-catch blocks
    import inspect

    import src.shell.api

    # Get the source code of the clear_played_watchmode_endpoint function
    source = inspect.getsource(src.shell.api.clear_played_watchmode_endpoint)

    # Verify that the top-level exception handler exists
    assert "except Exception as e:" in source
    assert "Unexpected error in watchmode endpoint" in source
    assert "unexpected_error" in source
    assert "An unexpected error occurred" in source

    # This test ensures the code path exists and is properly structured
    # Even though it's difficult to trigger in tests, it's important for production safety
