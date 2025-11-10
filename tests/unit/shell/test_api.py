from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from returns.result import Success
from spotipy.oauth2 import SpotifyOAuth  # type: ignore

from src.core.models import SyncFailure, SyncResult
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

    # Mock spotipy.Spotify to return None for current_user
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
            "Failed to retrieve user information from Spotify." in exc_info.value.detail
        )


@pytest.mark.asyncio
async def test_sync_playlist_returns_207_on_partial_failure(client: TestClient) -> None:
    """Test sync_playlist_endpoint returns JSONResponse 207 on partial failure."""
    sync_result = SyncResult(
        success_count=2,
        failure_count=1,
        failures=[SyncFailure(song_id="123", reason="Timeout")],
        successful=["1", "2"],
        not_found=[],
        errors=["3"],
    )

    with patch("src.shell.api.sync_playlist", return_value=Success(sync_result)):
        response = client.post("/sync-playlist")

        assert response.status_code == 207
        content = response.json()
        assert content == {
            "successful": ["1", "2"],
            "not_found": [],
            "errors": ["123: Timeout"],
        }
