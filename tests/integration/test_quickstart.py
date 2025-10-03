import pytest
from httpx import ASGITransport, AsyncClient

from src.core.models import Song, SongRequest
from src.shell.api import app
from tests.mocks import MockSpotifyClient, MockSupabaseClient


@pytest.mark.asyncio
async def test_quickstart_workflow() -> None:
    """Integration test for the main playlist synchronization workflow."""
    # Arrange
    requests = [
        SongRequest(
            id=1, song=Song(artist="Artist 1", title="Title 1"), requested_by="User 1"
        ),
        SongRequest(
            id=2, song=Song(artist="Artist 2", title="Title 2"), requested_by="User 2"
        ),
    ]
    supabase_mock = MockSupabaseClient(pending_requests=requests)
    spotify_mock = MockSpotifyClient()

    from src.shell.api import get_spotify_client, get_supabase_client

    app.dependency_overrides[get_supabase_client] = lambda: supabase_mock
    app.dependency_overrides[get_spotify_client] = lambda: spotify_mock

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/sync-playlist?max_count=10")

    # Assert
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "success"
    assert response_data["songs_added"] == 2
    assert len(supabase_mock.updated_requests) == 2
    assert len(spotify_mock.added_songs) == 2

    # Teardown
    app.dependency_overrides = {}
