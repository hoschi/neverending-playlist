from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from returns.result import Success

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


@pytest.mark.asyncio
async def test_sync_playlist_success_returns_200(
    client: TestClient, mock_spotify_client
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


@pytest.mark.asyncio
async def test_sync_playlist_returns_207_on_partial_failure(
    client: TestClient, mock_spotify_client
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


@pytest.mark.asyncio
async def test_clear_played_endpoint_success(
    client: TestClient, mock_spotify_client
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


@pytest.mark.asyncio
async def test_clear_played_endpoint_no_deletion_needed_200(
    client: TestClient, mock_spotify_client
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


@pytest.mark.asyncio
async def test_clear_played_endpoint_partially_successful_207(
    client: TestClient, mock_spotify_client
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


@pytest.mark.asyncio
async def test_clear_played_endpoint_successful_deletion_and_refill_200(
    client: TestClient, mock_spotify_client
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


@pytest.mark.asyncio
async def test_clear_played_endpoint_playback_inactive_error_409(
    client: TestClient, mock_spotify_client
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
        from returns.result import Failure

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


@pytest.mark.asyncio
async def test_clear_played_endpoint_wrong_playlist_error_400(
    client: TestClient, mock_spotify_client
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
        from returns.result import Failure

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


@pytest.mark.asyncio
async def test_clear_played_endpoint_internal_error_500(
    client: TestClient, mock_spotify_client
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
        from returns.result import Failure

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


@pytest.mark.asyncio
async def test_clear_played_endpoint_unknown_error_500(
    client: TestClient, mock_spotify_client
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
