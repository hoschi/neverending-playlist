from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient, Response
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from starlette import status

from src.shell.api import app, get_encryption_service, get_spotify_oauth

pytestmark = pytest.mark.anyio


class MockSpotifyOAuth(SpotifyOAuth):
    """A mock SpotifyOAuth manager for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.auth_url = "https://accounts.spotify.com/authorize?mock_params"
        self.token_info: dict[str, str | int] = {
            "access_token": "mock_access_token",
            "refresh_token": "mock_refresh_token",
            "expires_at": 9999999999,
            "scope": "playlist-modify-public playlist-modify-private",
        }

    def get_authorize_url(self, *_args, **_kwargs) -> str:
        return self.auth_url

    def get_access_token(
        self,
        code: str | None = None,  # noqa: ARG002 - unused in mock
        as_dict: bool = True,  # noqa: ARG002 - unused in mock
        check_cache: bool = True,  # noqa: ARG002 - unused in mock
    ) -> dict[str, str | int]:
        """Override base method to return mock token info."""
        # For mocking purposes, we ignore the parameters and always return token_info
        return self.token_info


class MockEncryptionService:
    """A mock EncryptionService for testing."""

    def encrypt(self, value: str) -> str:
        return f"encrypted_{value}"


@pytest.fixture
def mock_oauth_manager() -> MockSpotifyOAuth:
    """Provides a mock SpotifyOAuth manager."""
    return MockSpotifyOAuth(
        client_id="test_id",
        client_secret="test_secret",
        redirect_uri="http://localhost/callback",
    )


@pytest.fixture
def mock_encryption_service() -> MockEncryptionService:
    """Provides a mock EncryptionService."""
    return MockEncryptionService()


async def test_login_redirects_to_spotify(
    mock_oauth_manager: MockSpotifyOAuth,
) -> None:
    """Test that GET /login redirects to the Spotify authorization URL."""
    # Arrange
    app.dependency_overrides[get_spotify_oauth] = lambda: mock_oauth_manager

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.get("/login")

    # Assert
    assert response.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert response.headers["location"] == mock_oauth_manager.auth_url

    # Clean up
    app.dependency_overrides = {}


async def test_callback_fails_if_no_refresh_token(
    mock_oauth_manager: MockSpotifyOAuth,
    mock_encryption_service: MockEncryptionService,
) -> None:
    """Test that GET /callback returns an error if no refresh token is received."""
    # Arrange
    mock_oauth_manager.token_info = {"access_token": "mock_access_token"}
    app.dependency_overrides[get_spotify_oauth] = lambda: mock_oauth_manager
    app.dependency_overrides[get_encryption_service] = lambda: mock_encryption_service
    auth_code = "test_auth_code"

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.get(f"/callback?code={auth_code}")

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Could not retrieve refresh token" in response.text

    # Clean up
    app.dependency_overrides = {}


async def test_callback_handles_general_exception(
    mock_oauth_manager: MockSpotifyOAuth,
    mock_encryption_service: MockEncryptionService,
) -> None:
    """Test that GET /callback returns a 500 error on unexpected failure."""
    # Arrange
    app.dependency_overrides[get_spotify_oauth] = lambda: mock_oauth_manager
    app.dependency_overrides[get_encryption_service] = lambda: mock_encryption_service
    auth_code = "test_auth_code"

    # Act
    with patch.object(
        mock_oauth_manager,
        "get_access_token",
        side_effect=Exception("A wild error appears!"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response: Response = await client.get(f"/callback?code={auth_code}")

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "An internal error occurred" in response.text

    # Clean up
    app.dependency_overrides = {}


async def test_callback_handles_code_and_stores_token(
    mock_oauth_manager: MockSpotifyOAuth,
    mock_encryption_service: MockEncryptionService,
) -> None:
    """Test that GET /callback exchanges the auth code and stores the token."""
    # Arrange
    app.dependency_overrides[get_spotify_oauth] = lambda: mock_oauth_manager
    app.dependency_overrides[get_encryption_service] = lambda: mock_encryption_service
    auth_code = "test_auth_code"

    mock_spotify_user = {"id": "test_user_id"}
    mock_spotify_client = MagicMock(spec=Spotify)
    mock_spotify_client.current_user.return_value = mock_spotify_user

    # Act
    with (
        patch("src.shell.api.set_key") as mock_set_key,
        patch(
            "spotipy.Spotify", return_value=mock_spotify_client
        ) as mock_spotify_constructor,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response: Response = await client.get(f"/callback?code={auth_code}")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "Successfully authenticated."

    mock_spotify_constructor.assert_called_once_with(
        auth=mock_oauth_manager.token_info["access_token"]
    )
    mock_set_key.assert_called_once_with(
        ".env",
        "SPOTIFY_REFRESH_TOKEN",
        "encrypted_mock_refresh_token",
    )

    # Clean up
    app.dependency_overrides = {}
