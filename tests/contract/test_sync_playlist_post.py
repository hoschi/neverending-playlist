import pytest
from httpx import ASGITransport, AsyncClient

from src.shell.api import app
from tests.mocks import MockSpotifyClient, MockSupabaseClient


@pytest.mark.asyncio
async def test_sync_playlist_success() -> None:
    """Contract test for a successful playlist synchronization."""
    # Arrange
    supabase_mock = MockSupabaseClient()
    spotify_mock = MockSpotifyClient()

    from src.shell.api import get_spotify_client, get_supabase_client

    app.dependency_overrides[get_supabase_client] = lambda: supabase_mock
    app.dependency_overrides[get_spotify_client] = lambda: spotify_mock

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/sync-playlist")

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert "songs_added" in response_data
    assert isinstance(response_data["songs_added"], int)

    # Teardown
    app.dependency_overrides = {}
