import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from returns.result import Failure, Success

from src.core.models import Song, SongRequest
from src.shell.clients import ConcreteSupabaseClient


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Provides a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def concrete_supabase_client(mock_supabase_client: MagicMock) -> ConcreteSupabaseClient:
    """Provides a ConcreteSupabaseClient instance with mocked dependencies."""
    with patch("src.shell.clients.create_client", return_value=mock_supabase_client):
        with patch("src.shell.clients.get_settings"):
            return ConcreteSupabaseClient()


@pytest.mark.anyio
async def test_fetch_pending_song_requests_success(
    concrete_supabase_client: ConcreteSupabaseClient, mock_supabase_client: MagicMock
) -> None:
    """Test successful fetch of pending song requests."""
    # Arrange
    test_data = [
        {
            "id": 1,
            "artist": "Test Artist 1",
            "song": "Test Song 1",
            "added_to_spotify": None,
        },
        {
            "id": 2,
            "artist": "Test Artist 2",
            "song": "Test Song 2",
            "added_to_spotify": None,
        },
    ]

    mock_execute_result = MagicMock()
    mock_execute_result.data = test_data
    mock_supabase_client.table.return_value.select.return_value.is_.return_value.limit.return_value.execute.return_value = mock_execute_result

    # Act
    result = await concrete_supabase_client.fetch_pending_song_requests(max_count=5)

    # Assert
    assert isinstance(result, Success)
    assert len(result.unwrap()) == 2

    # Check first song request
    first_request = result.unwrap()[0]
    assert first_request.id == 1
    assert first_request.song.artist == "Test Artist 1"
    assert first_request.song.title == "Test Song 1"
    assert first_request.requested_by == "hoschi"
    assert not first_request.added_to_spotify

    # Check second song request
    second_request = result.unwrap()[1]
    assert second_request.id == 2
    assert second_request.song.artist == "Test Artist 2"
    assert second_request.song.title == "Test Song 2"
    assert second_request.requested_by == "hoschi"
    assert not second_request.added_to_spotify

    # Verify the correct Supabase query chain was used
    mock_supabase_client.table.assert_called_once_with("_spotify_to_supabase_test")
    table_mock = mock_supabase_client.table.return_value

    # Check the query chain
    table_mock.select.assert_called_once_with("*")
    table_mock.select.return_value.is_.assert_called_once_with(
        "added_to_spotify", "null"
    )
    table_mock.select.return_value.is_.return_value.limit.assert_called_once_with(5)
    table_mock.select.return_value.is_.return_value.limit.return_value.execute.assert_called_once()


@pytest.mark.anyio
async def test_fetch_pending_song_requests_empty_result(
    concrete_supabase_client: ConcreteSupabaseClient, mock_supabase_client: MagicMock
) -> None:
    """Test fetch of pending song requests when no results are returned."""
    # Arrange
    mock_execute_result = MagicMock()
    mock_execute_result.data = []
    mock_supabase_client.table.return_value.select.return_value.is_.return_value.limit.return_value.execute.return_value = mock_execute_result

    # Act
    result = await concrete_supabase_client.fetch_pending_song_requests(max_count=10)

    # Assert
    assert isinstance(result, Success)
    assert len(result.unwrap()) == 0

    # Verify the correct Supabase query chain was used
    mock_supabase_client.table.assert_called_once_with("_spotify_to_supabase_test")
    table_mock = mock_supabase_client.table.return_value

    table_mock.select.assert_called_once_with("*")
    table_mock.select.return_value.is_.assert_called_once_with(
        "added_to_spotify", "null"
    )
    table_mock.select.return_value.is_.return_value.limit.assert_called_once_with(10)
    table_mock.select.return_value.is_.return_value.limit.return_value.execute.assert_called_once()


@pytest.mark.anyio
async def test_fetch_pending_song_requests_database_failure(
    concrete_supabase_client: ConcreteSupabaseClient, mock_supabase_client: MagicMock
) -> None:
    """Test fetch of pending song requests when database fails."""
    # Arrange
    database_error = Exception("Database connection failed")
    mock_supabase_client.table.return_value.select.return_value.is_.return_value.limit.return_value.execute.side_effect = database_error

    # Act
    result = await concrete_supabase_client.fetch_pending_song_requests(max_count=5)

    # Assert
    assert isinstance(result, Failure)
    assert result.failure() == database_error

    # Verify the correct Supabase query chain was used
    mock_supabase_client.table.assert_called_once_with("_spotify_to_supabase_test")
    table_mock = mock_supabase_client.table.return_value

    table_mock.select.assert_called_once_with("*")
    table_mock.select.return_value.is_.assert_called_once_with(
        "added_to_spotify", "null"
    )
    table_mock.select.return_value.is_.return_value.limit.assert_called_once_with(5)
    table_mock.select.return_value.is_.return_value.limit.return_value.execute.assert_called_once()


@pytest.mark.anyio
async def test_fetch_pending_song_requests_with_max_count(
    concrete_supabase_client: ConcreteSupabaseClient, mock_supabase_client: MagicMock
) -> None:
    """Test that the max_count parameter is correctly passed to the query."""
    # Arrange
    test_data = [
        {
            "id": 1,
            "artist": "Test Artist",
            "song": "Test Song",
            "added_to_spotify": None,
        }
    ]

    mock_execute_result = MagicMock()
    mock_execute_result.data = test_data
    mock_supabase_client.table.return_value.select.return_value.is_.return_value.limit.return_value.execute.return_value = mock_execute_result

    # Act
    result = await concrete_supabase_client.fetch_pending_song_requests(max_count=3)

    # Assert
    assert isinstance(result, Success)
    assert len(result.unwrap()) == 1

    # Verify the correct max_count was used in the query
    mock_supabase_client.table.assert_called_once_with("_spotify_to_supabase_test")
    table_mock = mock_supabase_client.table.return_value

    table_mock.select.assert_called_once_with("*")
    table_mock.select.return_value.is_.assert_called_once_with(
        "added_to_spotify", "null"
    )
    table_mock.select.return_value.is_.return_value.limit.assert_called_once_with(3)
    table_mock.select.return_value.is_.return_value.limit.return_value.execute.assert_called_once()


@pytest.mark.anyio
async def test_fetch_pending_song_requests_song_with_added_to_spotify_false(
    concrete_supabase_client: ConcreteSupabaseClient, mock_supabase_client: MagicMock
) -> None:
    """Test that songs with added_to_spotify=False are correctly handled."""
    # Arrange
    test_data = [
        {
            "id": 1,
            "artist": "Test Artist",
            "song": "Test Song",
            "added_to_spotify": False,  # This should still be included
        }
    ]

    mock_execute_result = MagicMock()
    mock_execute_result.data = test_data
    mock_supabase_client.table.return_value.select.return_value.is_.return_value.limit.return_value.execute.return_value = mock_execute_result

    # Act
    result = await concrete_supabase_client.fetch_pending_song_requests(max_count=5)

    # Assert
    assert isinstance(result, Success)
    assert len(result.unwrap()) == 1

    song_request = result.unwrap()[0]
    assert song_request.id == 1
    assert song_request.song.artist == "Test Artist"
    assert song_request.song.title == "Test Song"
    assert song_request.requested_by == "hoschi"
    assert not song_request.added_to_spotify  # Should be False, not None
