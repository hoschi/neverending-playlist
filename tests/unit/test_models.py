from src.core.models import Song, SongRequest


def test_song_request_model_creation() -> None:
    """Test that a SongRequest model can be created successfully."""
    # Arrange
    song = Song(artist="Test Artist", title="Test Title")
    song_request = SongRequest(
        id=1,
        song=song,
        requested_by="test_user",
        is_added=False,
    )

    # Assert
    assert song_request.id == 1
    assert song_request.song.artist == "Test Artist"
    assert song_request.song.title == "Test Title"
    assert song_request.requested_by == "test_user"
    assert not song_request.is_added
