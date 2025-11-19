from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from returns.result import Failure, Success

from src.core.models import Song, SongAdditionStatus, SongRequest
from src.shell.clients import ConcreteSpotifyClient, ConcreteSupabaseClient


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Provides a mock Supabase client."""
    return MagicMock()


@pytest.fixture
def concrete_supabase_client(mock_supabase_client: MagicMock) -> ConcreteSupabaseClient:
    """Provides a ConcreteSupabaseClient instance with mocked dependencies."""
    with (
        patch("src.shell.clients.create_client", return_value=mock_supabase_client),
        patch("src.shell.clients.get_settings") as mock_settings,
    ):
        mock_settings_instance = MagicMock()
        mock_settings_instance.supabase_table = "_spotify_to_supabase_test"
        mock_settings.return_value = mock_settings_instance
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
            "status": None,
        },
        {
            "id": 2,
            "artist": "Test Artist 2",
            "song": "Test Song 2",
            "status": None,
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
    assert first_request.status is None

    # Check second song request
    second_request = result.unwrap()[1]
    assert second_request.id == 2
    assert second_request.song.artist == "Test Artist 2"
    assert second_request.song.title == "Test Song 2"
    assert second_request.status is None

    # Verify the correct Supabase query chain was used
    mock_supabase_client.table.assert_called_once_with("_spotify_to_supabase_test")
    table_mock = mock_supabase_client.table.return_value

    # Check the query chain
    table_mock.select.assert_called_once_with("*")
    table_mock.select.return_value.is_.assert_called_once_with("status", "null")
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
    table_mock.select.return_value.is_.assert_called_once_with("status", "null")
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
    table_mock.select.return_value.is_.assert_called_once_with("status", "null")
    table_mock.select.return_value.is_.return_value.limit.assert_called_once_with(5)
    table_mock.select.return_value.is_.return_value.limit.return_value.execute.assert_called_once()


@pytest.mark.anyio
async def test_update_song_requests_as_added_empty_list(
    concrete_supabase_client: ConcreteSupabaseClient, mock_supabase_client: MagicMock
) -> None:
    """Test update of song requests when empty list is provided."""
    # Arrange
    empty_requests: list[SongRequest] = []

    # Act
    result = await concrete_supabase_client.update_song_requests_as_added(
        empty_requests
    )

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() is None

    # Verify the correct Supabase query chain was used with empty list
    mock_supabase_client.table.assert_not_called()


@pytest.mark.anyio
async def test_update_song_requests_as_added_database_failure(
    concrete_supabase_client: ConcreteSupabaseClient, mock_supabase_client: MagicMock
) -> None:
    """Test update of song requests when database fails."""
    # Arrange
    song_requests = [
        SongRequest(
            id=1,
            song=Song(artist="Test Artist", title="Test Song"),
            status=None,
        )
    ]

    database_error = Exception("Database update failed")
    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.side_effect = database_error

    # Act
    result = await concrete_supabase_client.update_song_requests_as_added(song_requests)

    # Assert
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), Exception)
    assert result.failure() == database_error

    # Verify the correct Supabase query chain was used
    mock_supabase_client.table.assert_called_once_with("_spotify_to_supabase_test")
    table_mock = mock_supabase_client.table.return_value

    table_mock.update.assert_called_once_with({"status": None})
    table_mock.update.return_value.eq.assert_called_once_with("id", 1)
    table_mock.update.return_value.eq.return_value.execute.assert_called_once()


@pytest.mark.anyio
async def test_update_song_requests_as_added_multiple_ids(
    concrete_supabase_client: ConcreteSupabaseClient, mock_supabase_client: MagicMock
) -> None:
    """Test update of song requests with multiple IDs."""
    # Arrange
    song_requests = [
        SongRequest(
            id=1,
            song=Song(artist="Test Artist 1", title="Test Song 1"),
            status=None,
        ),
        SongRequest(
            id=2,
            song=Song(artist="Test Artist 2", title="Test Song 2"),
            status=None,
        ),
        SongRequest(
            id=3,
            song=Song(artist="Test Artist 3", title="Test Song 3"),
            status=None,
        ),
    ]

    mock_supabase_client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    # Act
    result = await concrete_supabase_client.update_song_requests_as_added(song_requests)

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() is None

    # Verify the correct Supabase query chain was used
    assert mock_supabase_client.table.call_count == len(song_requests)

    for _i, song_request in enumerate(song_requests):
        mock_supabase_client.table.assert_any_call("_spotify_to_supabase_test")
        table_mock = mock_supabase_client.table.return_value

        # Check the query chain for each song request
        table_mock.update.assert_any_call(
            {"status": song_request.status.value if song_request.status else None}
        )
        table_mock.update.return_value.eq.assert_any_call("id", song_request.id)
        table_mock.update.return_value.eq.return_value.execute.assert_called()


@pytest.fixture
def mock_spotify_client() -> MagicMock:
    """Provides a mock Spotify client."""
    return MagicMock()


@pytest.fixture
def concrete_spotify_client(
    mock_spotify_client: MagicMock, mock_settings
) -> ConcreteSpotifyClient:
    """Provides a ConcreteSpotifyClient instance with mocked dependencies."""
    with (
        patch("src.shell.clients.get_settings", return_value=mock_settings),
        patch("src.shell.clients.EncryptionService") as mock_encryption,
        patch("src.shell.clients.SpotifyOAuth") as mock_auth,
        patch("src.shell.clients.spotipy.Spotify") as mock_spotify,
    ):
        # Mock encryption
        mock_encryption.return_value.decrypt.return_value = "decrypted_token"

        # Mock auth
        mock_auth_instance = MagicMock()
        mock_auth.return_value = mock_auth_instance
        mock_auth_instance.refresh_access_token.return_value = {"access_token": "test"}

        # Mock spotify client
        mock_spotify.return_value = mock_spotify_client

        return ConcreteSpotifyClient()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "song_requests,search_results,expected_calls",
    [
        # Success case: All songs found
        (
            [
                SongRequest(
                    id=1,
                    song=Song(artist="Test Artist 1", title="Test Song 1"),
                    status=None,
                ),
                SongRequest(
                    id=2,
                    song=Song(artist="Test Artist 2", title="Test Song 2"),
                    status=None,
                ),
            ],
            [
                {"tracks": {"items": [{"uri": "spotify:track:001"}]}},
                {"tracks": {"items": [{"uri": "spotify:track:002"}]}},
            ],
            2,
        ),
        # Partial success: Some songs found
        (
            [
                SongRequest(
                    id=1,
                    song=Song(artist="Test Artist 1", title="Test Song 1"),
                    status=None,
                ),
                SongRequest(
                    id=2,
                    song=Song(artist="Test Artist 2", title="Test Song 2"),
                    status=None,
                ),
                SongRequest(
                    id=3,
                    song=Song(artist="Test Artist 3", title="Test Song 3"),
                    status=None,
                ),
            ],
            [
                {"tracks": {"items": [{"uri": "spotify:track:001"}]}},
                {"tracks": {"items": []}},  # Not found
                {"tracks": {"items": [{"uri": "spotify:track:003"}]}},
            ],
            3,
        ),
        # No songs found
        (
            [
                SongRequest(
                    id=1,
                    song=Song(artist="Test Artist 1", title="Test Song 1"),
                    status=None,
                ),
                SongRequest(
                    id=2,
                    song=Song(artist="Test Artist 2", title="Test Song 2"),
                    status=None,
                ),
            ],
            [
                {"tracks": {"items": []}},
                {"tracks": {"items": []}},
            ],
            2,
        ),
        # Empty list
        ([], [], 0),
    ],
)
async def test_add_songs_to_playlist_success(
    concrete_spotify_client: ConcreteSpotifyClient,
    mock_spotify_client: MagicMock,
    mock_settings,
    song_requests: list[SongRequest],
    search_results: list[dict[str, Any]],
    expected_calls: int,
) -> None:
    """Test successful addition of songs to playlist with various scenarios."""
    # Arrange
    mock_spotify_client.search.side_effect = search_results

    # Act
    result = await concrete_spotify_client.add_songs_to_playlist(song_requests)

    # Assert
    assert isinstance(result, Success)
    assert isinstance(result.unwrap(), list)
    assert len(result.unwrap()) == len(song_requests)

    # Verify that each song request has the correct status
    for i, (song_request, status) in enumerate(result.unwrap()):
        assert song_request.id == song_requests[i].id
        assert song_request.status == status
        # Verify that the status is set correctly based on search results
        if search_results[i] and search_results[i].get("tracks", {}).get("items"):
            assert status == SongAdditionStatus.SUCCESS
        else:
            assert status == SongAdditionStatus.NOT_FOUND

    # Verify search calls
    assert mock_spotify_client.search.call_count == expected_calls
    for _i, song in enumerate(song_requests):
        expected_query = f"artist:{song.song.artist} track:{song.song.title}"
        mock_spotify_client.search.assert_any_call(
            q=expected_query, type="track", limit=1
        )

    # Verify playlist add calls
    found_uris = []
    for i, _song in enumerate(song_requests):
        if search_results[i] and search_results[i]["tracks"]["items"]:
            found_uris.append(search_results[i]["tracks"]["items"][0]["uri"])

    if found_uris:
        assert mock_spotify_client.playlist_add_items.call_count == len(found_uris)
        # Verify each call contains a single URI in a list
        for uri in found_uris:
            mock_spotify_client.playlist_add_items.assert_any_call(
                mock_settings.spotify_playlist_id, [uri]
            )
    else:
        mock_spotify_client.playlist_add_items.assert_not_called()


@pytest.mark.anyio
async def test_add_songs_to_playlist_api_failure(
    concrete_spotify_client: ConcreteSpotifyClient,
    mock_spotify_client: MagicMock,
    mock_settings,
) -> None:
    """Test addition of songs to playlist when Spotify API fails."""
    # Arrange
    song_requests = [
        SongRequest(
            id=1,
            song=Song(artist="Test Artist", title="Test Song"),
            status=None,
        )
    ]

    # Mock search to succeed but playlist_add_items to fail
    mock_spotify_client.search.return_value = {
        "tracks": {"items": [{"uri": "spotify:track:001"}]}
    }
    mock_spotify_client.playlist_add_items.side_effect = Exception("API Error")

    # Act
    result = await concrete_spotify_client.add_songs_to_playlist(song_requests)

    # Assert
    assert isinstance(result, Success)
    assert len(result.unwrap()) == 1
    assert result.unwrap()[0][1] == SongAdditionStatus.ERROR

    # Verify the calls were made
    mock_spotify_client.search.assert_called_once_with(
        q="artist:Test Artist track:Test Song", type="track", limit=1
    )
    mock_spotify_client.playlist_add_items.assert_called_once_with(
        mock_settings.spotify_playlist_id, ["spotify:track:001"]
    )


@pytest.mark.anyio
async def test_add_songs_to_playlist_search_failure(
    concrete_spotify_client: ConcreteSpotifyClient,
    mock_spotify_client: MagicMock,
) -> None:
    """Test addition of songs to playlist when search fails."""
    # Arrange
    song_requests = [
        SongRequest(
            id=1,
            song=Song(artist="Test Artist", title="Test Song"),
            status=None,
        )
    ]

    # Mock search to fail
    mock_spotify_client.search.side_effect = Exception("Search failed")

    # Act
    result = await concrete_spotify_client.add_songs_to_playlist(song_requests)

    # Assert
    assert isinstance(result, Success)
    assert len(result.unwrap()) == 1
    assert result.unwrap()[0][1] == SongAdditionStatus.ERROR

    # Verify the search was called
    mock_spotify_client.search.assert_called_once_with(
        q="artist:Test Artist track:Test Song", type="track", limit=1
    )


async def test_add_songs_to_playlist_malformed_search_results(
    concrete_spotify_client: ConcreteSpotifyClient,
    mock_spotify_client: MagicMock,
) -> None:
    """Test addition of songs when search returns malformed results."""
    # Arrange
    song_requests = [
        SongRequest(
            id=1,
            song=Song(artist="Test Artist", title="Test Song"),
            status=None,
        )
    ]

    # Mock search to return result without tracks key
    mock_spotify_client.search.return_value = {"some_other_key": "value"}

    # Act
    result = await concrete_spotify_client.add_songs_to_playlist(song_requests)

    # Assert
    assert isinstance(result, Success)
    assert len(result.unwrap()) == 1
    # Since "tracks" key is missing, it will raise KeyError which is caught as ERROR
    assert result.unwrap()[0][1] == SongAdditionStatus.ERROR

    # Verify search was called
    mock_spotify_client.search.assert_called_once_with(
        q="artist:Test Artist track:Test Song", type="track", limit=1
    )

    # Verify playlist_add_items was not called
    mock_spotify_client.playlist_add_items.assert_not_called()


@pytest.mark.anyio
def test_concrete_spotify_client_init_missing_refresh_token() -> None:
    """Test ConcreteSpotifyClient initialization when refresh token is missing."""
    # Arrange
    mock_settings_missing_token = MagicMock()
    mock_settings_missing_token.spotify_refresh_token = None
    mock_settings_missing_token.spotify_client_id = "test_client_id"
    mock_settings_missing_token.spotify_client_secret = "test_client_secret"
    mock_settings_missing_token.spotify_redirect_uri = "http://test-redirect"
    mock_settings_missing_token.encryption_key = "test_key"

    with (
        patch(
            "src.shell.clients.get_settings", return_value=mock_settings_missing_token
        ),
        pytest.raises(
            ValueError, match="Spotify refresh token not found in environment"
        ),
    ):
        ConcreteSpotifyClient()


@pytest.mark.anyio
def test_concrete_spotify_client_init_encryption_error() -> None:
    """Test ConcreteSpotifyClient initialization when decryption fails."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.spotify_refresh_token = "invalid_token"
    mock_settings.spotify_client_id = "test_client_id"
    mock_settings.spotify_client_secret = "test_client_secret"
    mock_settings.spotify_redirect_uri = "http://test-redirect"
    mock_settings.encryption_key = "test_key"

    with (
        patch("src.shell.clients.get_settings", return_value=mock_settings),
        patch("src.shell.clients.EncryptionService") as mock_encryption,
    ):
        # Mock encryption service to raise exception
        mock_encryption.return_value.decrypt.side_effect = Exception(
            "Decryption failed"
        )

        # Act & Assert
        with pytest.raises(Exception, match="Decryption failed"):
            ConcreteSpotifyClient()


@pytest.mark.anyio
def test_concrete_spotify_client_init_auth_error() -> None:
    """Test ConcreteSpotifyClient initialization when auth refresh fails."""
    # Arrange
    mock_settings = MagicMock()
    mock_settings.spotify_refresh_token = "encrypted_token"
    mock_settings.spotify_client_id = "test_client_id"
    mock_settings.spotify_client_secret = "test_client_secret"
    mock_settings.spotify_redirect_uri = "http://test-redirect"
    mock_settings.encryption_key = "test_key"

    with (
        patch("src.shell.clients.get_settings", return_value=mock_settings),
        patch("src.shell.clients.EncryptionService") as mock_encryption,
        patch("src.shell.clients.SpotifyOAuth") as mock_auth,
    ):
        # Mock encryption
        mock_encryption.return_value.decrypt.return_value = "decrypted_token"

        # Mock auth to raise exception
        mock_auth_instance = MagicMock()
        mock_auth_instance.refresh_access_token.side_effect = Exception(
            "Auth refresh failed"
        )
        mock_auth.return_value = mock_auth_instance

        # Act & Assert
        with pytest.raises(Exception, match="Auth refresh failed"):
            ConcreteSpotifyClient()


@pytest.mark.anyio
async def test_get_current_user_success(
    concrete_spotify_client: ConcreteSpotifyClient,
    mock_spotify_client: MagicMock,
) -> None:
    """Test successful retrieval of current user information."""
    # Arrange
    mock_user_info = {"id": "test_user", "display_name": "Test User"}
    mock_spotify_client.current_user.return_value = mock_user_info

    # Act
    result = await concrete_spotify_client.get_current_user()

    # Assert
    assert isinstance(result, Success)
    assert result.unwrap() == mock_user_info
    mock_spotify_client.current_user.assert_called_once()


@pytest.mark.anyio
async def test_get_current_user_api_error(
    concrete_spotify_client: ConcreteSpotifyClient,
    mock_spotify_client: MagicMock,
) -> None:
    """Test get_current_user when Spotify API fails."""
    # Arrange
    mock_spotify_client.current_user.side_effect = Exception("API Error")

    # Act
    result = await concrete_spotify_client.get_current_user()

    # Assert
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), Exception)
    assert str(result.failure()) == "API Error"
    mock_spotify_client.current_user.assert_called_once()


async def test_add_songs_to_playlist_empty_search_results(
    concrete_spotify_client: ConcreteSpotifyClient,
    mock_spotify_client: MagicMock,
) -> None:
    """Test addition of songs when search returns completely empty results."""
    # Arrange
    song_requests = [
        SongRequest(
            id=1,
            song=Song(artist="Test Artist", title="Test Song"),
            status=None,
        )
    ]

    # Mock search to return empty dict
    mock_spotify_client.search.return_value = {}

    # Act
    result = await concrete_spotify_client.add_songs_to_playlist(song_requests)

    # Assert
    assert isinstance(result, Success)
    assert len(result.unwrap()) == 1
    assert result.unwrap()[0][1] == SongAdditionStatus.NOT_FOUND

    # Verify search was called
    mock_spotify_client.search.assert_called_once_with(
        q="artist:Test Artist track:Test Song", type="track", limit=1
    )

    # Verify playlist_add_items was not called
    mock_spotify_client.playlist_add_items.assert_not_called()
