from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient, Response
from returns.result import Failure, Success
from starlette import status

from src.core.models import (
    Song,
    SongAdditionStatus,
    SongRequest,
)
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
    assert response.json() == {"successful": ["1"], "not_found": [], "errors": []}

    # Clean up
    app.dependency_overrides = {}


# Clear Played Tracks Integration Tests
async def test_clear_played_success(
    mock_spotify_client: MagicMock,
) -> None:
    """Test the success path of the /clear-played endpoint."""
    # Arrange
    # Use the actual configured playlist ID
    config_playlist_id = "7AVVVQ6TJMTA17a2e6ncFr"

    # Mock successful clearing of 3 tracks
    mock_spotify_client.get_current_playback.return_value = Success(
        {
            "item": {"uri": "spotify:track:track4"},
            "context": {
                "type": "playlist",
                "uri": f"spotify:playlist:{config_playlist_id}",
            },
        }
    )
    mock_spotify_client.get_playlist_items.return_value = Success(
        [
            {"track": {"uri": "spotify:track:track1"}},
            {"track": {"uri": "spotify:track:track2"}},
            {"track": {"uri": "spotify:track:track3"}},
            {"track": {"uri": "spotify:track:track4"}},  # Currently playing
        ]
    )
    mock_spotify_client.remove_items_from_playlist.return_value = Success(None)

    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.post("/clear-played")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"deleted_count": 3}

    # Verify the correct methods were called
    mock_spotify_client.get_current_playback.assert_called_once()
    mock_spotify_client.get_playlist_items.assert_called_once_with(config_playlist_id)
    mock_spotify_client.remove_items_from_playlist.assert_called_once()

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_playback_inactive(
    mock_spotify_client: MagicMock,
) -> None:
    """Test the /clear-played endpoint when playback is inactive."""
    # Arrange
    mock_spotify_client.get_current_playback.return_value = Success(None)

    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.post("/clear-played")

    # Assert
    assert response.status_code == status.HTTP_409_CONFLICT
    # FastAPI wraps HTTPException details in "detail" key
    assert response.json() == {
        "detail": {
            "error": "playback_inactive",
            "message": "Cannot clear tracks when no music is playing.",
        }
    }

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_wrong_playlist(
    mock_spotify_client: MagicMock,
) -> None:
    """Test the /clear-played endpoint when playing from wrong playlist."""
    # Arrange
    other_playlist_id = "playlist456"

    mock_spotify_client.get_current_playback.return_value = Success(
        {
            "item": {"uri": "spotify:track:track1"},
            "context": {
                "type": "playlist",
                "uri": f"spotify:playlist:{other_playlist_id}",
            },
        }
    )

    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.post("/clear-played")

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # FastAPI wraps HTTPException details in "detail" key
    assert response.json() == {
        "detail": {
            "error": "wrong_playlist",
            "message": "The currently playing song is not from the configured playlist.",
        }
    }

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_api_error(
    mock_spotify_client: MagicMock,
) -> None:
    """Test the /clear-played endpoint when API call fails and is treated as playback inactive."""
    # Arrange
    mock_spotify_client.get_current_playback.return_value = Failure(
        Exception("Spotify API error")
    )

    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.post("/clear-played")

    # Assert - API errors are treated as PLAYBACK_INACTIVE in core logic
    assert response.status_code == status.HTTP_409_CONFLICT
    # FastAPI wraps HTTPException details in "detail" key
    assert response.json() == {
        "detail": {
            "error": "playback_inactive",
            "message": "Cannot clear tracks when no music is playing.",
        }
    }

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
