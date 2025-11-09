from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient, Response
from returns.result import Failure, Success
from starlette import status

from src.core.models import Song, SongAdditionStatus, SongRequest
from src.core.protocols import SpotifyClient, SupabaseClient
from src.shell.api import app, get_spotify_client, get_supabase_client

pytestmark = pytest.mark.anyio


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Provides a mock SupabaseClient."""
    return MagicMock(spec=SupabaseClient)


@pytest.fixture
def mock_spotify_client() -> MagicMock:
    """Provides a mock SpotifyClient."""
    return MagicMock(spec=SpotifyClient)


async def test_sync_playlist_success(
    mock_supabase_client: MagicMock, mock_spotify_client: MagicMock
) -> None:
    """Test the success path of the /sync-playlist endpoint."""
    # Arrange
    mock_supabase_client.fetch_pending_song_requests.return_value = Success(
        [
            SongRequest(
                id=1,
                song=Song(artist="A", title="B"),
                requested_by="hoschi",
                status=None,
            )
        ]
    )
    mock_supabase_client.update_song_requests_as_added.return_value = Success(None)
    mock_spotify_client.add_songs_to_playlist.return_value = Success(
        [
            (
                SongRequest(
                    id=1,
                    song=Song(artist="A", title="B"),
                    requested_by="hoschi",
                    status=None,
                ),
                SongAdditionStatus.SUCCESS,
            )
        ]
    )

    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.post("/sync-playlist?max_count=5")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    # This is a bit of a simplification, in a real scenario the service would return
    # the number of songs added. The current implementation returns the result of
    # the final `update_song_requests_as_added` call, which is None.
    # We will adapt the test to the actual current implementation.
    assert response.json() == {"status": "success", "songs_added": 1}

    # Clean up
    app.dependency_overrides = {}


async def test_sync_playlist_failure(
    mock_supabase_client: MagicMock, mock_spotify_client: MagicMock
) -> None:
    """Test the failure path of the /sync-playlist endpoint."""
    # Arrange
    mock_supabase_client.fetch_pending_song_requests.return_value = Failure(
        Exception("Supabase ded")
    )

    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.post("/sync-playlist?max_count=5")

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Supabase ded" in response.text

    # Clean up
    app.dependency_overrides = {}
