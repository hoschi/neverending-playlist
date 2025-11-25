from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, patch

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
    mock_supabase_client: MagicMock,
    mock_spotify_client: MagicMock,
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
async def test_clear_played_success_with_autofill_200(
    mock_spotify_client: MagicMock,
    mock_supabase_client: MagicMock,
) -> None:
    """Test /clear-played returns 200 when deleted_count > 0 AND filled_count > 0."""
    # Arrange
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

    # Mock playlist items sequence for autofill
    call_count = 0

    def get_playlist_items_side_effect(*_args, **_kwargs):
        nonlocal call_count
        if call_count == 0:
            # Initial call for clearing
            call_count += 1
            return Success(
                [
                    {"track": {"uri": "spotify:track:track1"}},
                    {"track": {"uri": "spotify:track:track2"}},
                    {"track": {"uri": "spotify:track:track3"}},
                    {"track": {"uri": "spotify:track:track4"}},  # Currently playing
                ]
            )
        else:
            # After songs are added, the playlist should grow
            call_count += 1
            # Start with the current track
            tracks = [{"track": {"uri": "spotify:track:track4"}}]
            # Add songs that would have been added during autofill
            # Gradually increase tracks to reach the minimum of 85
            base_tracks = call_count * 20  # Add 20 tracks per autofill attempt
            for i in range(1, base_tracks + 1):
                tracks.append({"track": {"uri": f"spotify:track:new{i}"}})
            return Success(tracks)

    mock_spotify_client.get_playlist_items.side_effect = get_playlist_items_side_effect
    mock_spotify_client.remove_items_from_playlist.return_value = Success(None)

    # Mock autofill requests - enough to fill 85 tracks
    mock_supabase_client.fetch_pending_song_requests.return_value = Success(
        [
            SongRequest(id=i, song=Song(artist=f"Artist {i}", title=f"Title {i}"))
            for i in range(1, 86)  # 85 requests
        ]
    )
    mock_supabase_client.update_song_requests_as_added.return_value = Success(None)
    mock_spotify_client.add_songs_to_playlist.return_value = Success(
        [
            (
                SongRequest(id=i, song=Song(artist=f"Artist {i}", title=f"Title {i}")),
                SongAdditionStatus.SUCCESS,
            )
            for i in range(1, 86)
        ]
    )

    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.post("/clear-played")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["deleted_count"] == 3
    assert response_data["filled_count"] > 0  # Songs were filled during autofill

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_no_deletion_needed_200(
    mock_spotify_client: MagicMock,
) -> None:
    """Test /clear-played returns 200 when deleted_count == 0 (nothing to delete)."""
    # Arrange
    config_playlist_id = "7AVVVQ6TJMTA17a2e6ncFr"

    mock_spotify_client.get_current_playback.return_value = Success(
        {
            "item": {"uri": "spotify:track:track1"},
            "context": {
                "type": "playlist",
                "uri": f"spotify:playlist:{config_playlist_id}",
            },
        }
    )

    # Mock playlist with only current track (no played tracks to remove)
    mock_spotify_client.get_playlist_items.return_value = Success(
        [
            {"track": {"uri": "spotify:track:track1"}},  # Only current track
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
    response_data = response.json()
    assert response_data["deleted_count"] == 0
    assert response_data["filled_count"] == 0

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_partially_successful_207(
    mock_spotify_client: MagicMock,
    mock_supabase_client: MagicMock,
) -> None:
    """Test /clear-played returns 207 when deleted_count > 0 AND filled_count == 0."""
    # Arrange
    config_playlist_id = "7AVVVQ6TJMTA17a2e6ncFr"

    # Mock current playback with played tracks
    current_track_uri = "spotify:track:track4"
    mock_spotify_client.get_current_playback.return_value = Success(
        {
            "item": {"uri": current_track_uri},
            "context": {
                "type": "playlist",
                "uri": f"spotify:playlist:{config_playlist_id}",
            },
        }
    )

    # Mock sequence for autofill attempts - no songs available
    mock_playlist_sequence = [
        # Initial call: playlist with 4 tracks (3 to be removed + current)
        [
            {"track": {"uri": "spotify:track:track1"}},  # Will be removed
            {"track": {"uri": "spotify:track:track2"}},  # Will be removed
            {"track": {"uri": "spotify:track:track3"}},  # Will be removed
            {"track": {"uri": current_track_uri}},  # Currently playing
        ],
        # After removal: 1 track remaining (current one)
        [
            {"track": {"uri": current_track_uri}},  # Currently playing
        ],
        # After autofill attempt 1: 1 + 0 = 1 tracks (no songs available)
        [
            {"track": {"uri": current_track_uri}},
        ],
    ]

    call_count = 0

    def get_playlist_items_side_effect(*_args, **_kwargs):
        nonlocal call_count
        if call_count < len(mock_playlist_sequence):
            result = Success(mock_playlist_sequence[call_count])
            call_count += 1
            return result
        # After sequence, return current track only (no more songs available)
        return Success([{"track": {"uri": current_track_uri}}])

    mock_spotify_client.get_playlist_items.side_effect = get_playlist_items_side_effect
    mock_spotify_client.remove_items_from_playlist.return_value = Success(None)

    # Mock no pending requests available
    mock_supabase_client.fetch_pending_song_requests.return_value = Success([])
    mock_supabase_client.update_song_requests_as_added.return_value = Success(None)

    # Override dependencies
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client

    # Act
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response: Response = await client.post("/clear-played")

    # Assert - should return 207 because tracks were deleted but no songs were added
    assert response.status_code == status.HTTP_207_MULTI_STATUS
    response_data = response.json()
    assert response_data["deleted_count"] == 3
    assert response_data["filled_count"] == 0  # No songs were added during autofill
    assert "Partial success" in response_data["message"]

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
            "message": "No active playback found",
            "details": "User is not currently playing any music",
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
            "message": "Current playlist does not match configured playlist",
            "details": "Current: playlist456, Configured: 7AVVVQ6TJMTA17a2e6ncFr",
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
            "message": "Playback is inactive or unavailable",
            "details": "Failed to get current playback state from Spotify API",
        }
    }

    # Clean up
    app.dependency_overrides = {}


async def test_sync_playlist_failure(
    mock_supabase_client: MagicMock,
    mock_spotify_client: MagicMock,
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


# Clear Played Watchmode Integration Tests
async def test_clear_played_watchmode_already_active(
    mock_spotify_client: MagicMock,
    mock_supabase_client: MagicMock,
) -> None:
    """Test GET /clear-played-watchmode returns already_active when checker is running."""
    # Arrange
    from datetime import datetime

    from src.shell.state import CheckerState

    # Mock checker state to be already running
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client

    # Mock the global state to simulate already running checker
    # Since the endpoint uses global state, we need to ensure is_running is True
    from unittest.mock import patch

    mock_state = CheckerState(
        is_running=True,
        retries_left=3,
        last_playback_detected=True,
        last_checked=datetime.now(UTC),
        next_check=datetime.now(UTC),  # No specific future time needed for this test
    )

    with patch("src.shell.api.get_checker_state", return_value=mock_state):
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response: Response = await client.get("/clear-played-watchmode")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["status"] == "already_active"
    assert "checker_state" in response_data
    assert response_data["checker_state"]["is_running"] is True
    assert response_data["checker_state"]["retries_left"] == 3
    assert response_data["checker_state"]["last_playback_detected"] is True
    assert "last_checked" in response_data["checker_state"]

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_watchmode_no_active_playback(
    mock_spotify_client: MagicMock,
) -> None:
    """Test GET /clear-played-watchmode returns no_active_playback when no playback detected."""
    # Arrange
    from src.shell.state import CheckerState

    # Mock checker state to not be running
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Mock no active playback
    mock_spotify_client.get_current_playback.return_value = Success(None)

    mock_state = CheckerState(
        is_running=False,
        retries_left=5,
        last_playback_detected=False,
        last_checked=None,
        next_check=None,
    )

    with patch("src.shell.api.get_checker_state", return_value=mock_state):
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response: Response = await client.get("/clear-played-watchmode")

    # Assert
    assert response.status_code == status.HTTP_409_CONFLICT
    response_data = response.json()
    assert response_data["status"] == "no_active_playback"
    assert "No active playback detected" in response_data["message"]
    assert "checker_state" in response_data
    assert response_data["checker_state"]["is_running"] is False

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_watchmode_started_successfully(
    mock_spotify_client: MagicMock,
    mock_supabase_client: MagicMock,
) -> None:
    """Test GET /clear-played-watchmode returns started when successfully activated."""
    # Arrange
    from datetime import datetime

    from src.shell.state import CheckerState

    # Mock checker state to not be running initially
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase_client

    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {
            "item": {"uri": "spotify:track:current_track"},
            "context": {"type": "playlist", "uri": "spotify:playlist:test_playlist"},
        }
    )

    # Mock initial state (checker not running)
    initial_state = CheckerState(
        is_running=False,
        retries_left=5,
        last_playback_detected=False,
        last_checked=None,
        next_check=None,
    )

    # Mock updated state (checker running)
    updated_state = CheckerState(
        is_running=True,
        retries_left=5,
        last_playback_detected=True,
        last_checked=datetime.now(UTC),
        next_check=datetime.now(UTC),  # Next check in 10 minutes
    )

    # Mock checker instance and its start_checker method
    mock_checker = MagicMock()

    # Create async mock for start_checker
    async def mock_start_checker():
        return updated_state

    mock_checker.start_checker = mock_start_checker

    with (
        patch("src.shell.api.get_checker_state", return_value=initial_state),
        patch("src.shell.api.get_checker", return_value=mock_checker),
    ):
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response: Response = await client.get("/clear-played-watchmode")

    # Assert
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert response_data["status"] == "started"
    assert "Watchmode activated successfully" in response_data["message"]
    assert "checker_state" in response_data
    assert response_data["checker_state"]["is_running"] is True
    assert response_data["checker_state"]["retries_left"] == 5
    assert response_data["checker_state"]["last_playback_detected"] is True
    assert "last_checked" in response_data["checker_state"]
    assert "next_check" in response_data["checker_state"]

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_watchmode_start_failed(
    mock_spotify_client: MagicMock,
) -> None:
    """Test GET /clear-played-watchmode returns start_failed when checker fails to start."""
    # Arrange
    from src.shell.state import CheckerState

    # Mock checker state to not be running
    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Mock active playback
    mock_spotify_client.get_current_playback.return_value = Success(
        {
            "item": {"uri": "spotify:track:current_track"},
            "context": {"type": "playlist", "uri": "spotify:playlist:test_playlist"},
        }
    )

    mock_state = CheckerState(
        is_running=False,
        retries_left=5,
        last_playback_detected=False,
        last_checked=None,
        next_check=None,
    )

    # Mock checker instance that fails to start
    mock_checker = MagicMock()
    mock_checker.start_checker = AsyncMock(
        side_effect=Exception("Failed to start checker")
    )

    with (
        patch("src.shell.api.get_checker_state", return_value=mock_state),
        patch("src.shell.api.get_checker", return_value=mock_checker),
    ):
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response: Response = await client.get("/clear-played-watchmode")

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    response_data = response.json()
    assert response_data["status"] == "start_failed"
    assert "Failed to start watchmode" in response_data["message"]
    assert "Failed to start checker" in response_data["details"]

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_watchmode_playback_check_failed(
    mock_spotify_client: MagicMock,
) -> None:
    """Test GET /clear-played-watchmode returns playback_check_failed when API call fails."""
    # Arrange
    from src.shell.state import CheckerState

    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Mock failed playback check
    mock_spotify_client.get_current_playback.return_value = Failure(
        Exception("Spotify API error")
    )

    mock_state = CheckerState(
        is_running=False,
        retries_left=5,
        last_playback_detected=False,
        last_checked=None,
        next_check=None,
    )

    with patch("src.shell.api.get_checker_state", return_value=mock_state):
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response: Response = await client.get("/clear-played-watchmode")

    # Assert
    assert response.status_code == status.HTTP_409_CONFLICT
    response_data = response.json()
    assert response_data["status"] == "playback_check_failed"
    assert "Failed to check playback status" in response_data["message"]
    assert "checker_state" in response_data
    assert response_data["checker_state"]["is_running"] is False

    # Clean up
    app.dependency_overrides = {}


async def test_clear_played_watchmode_unexpected_error(
    mock_spotify_client: MagicMock,
) -> None:
    """Test GET /clear-played-watchmode handles unexpected errors gracefully."""
    # Arrange

    app.dependency_overrides[get_spotify_client] = lambda: mock_spotify_client

    # Mock unexpected error in get_checker_state
    with patch(
        "src.shell.api.get_checker_state", side_effect=Exception("Unexpected error")
    ):
        # Act
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response: Response = await client.get("/clear-played-watchmode")

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    response_data = response.json()
    assert response_data["status"] == "unexpected_error"
    assert "An unexpected error occurred" in response_data["message"]

    # Clean up
    app.dependency_overrides = {}
