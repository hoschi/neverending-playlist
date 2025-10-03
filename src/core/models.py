from pydantic import BaseModel, Field


class Song(BaseModel):
    """Represents a song with artist and title."""

    artist: str = Field(..., description="The artist of the song.")
    title: str = Field(..., description="The title of the song.")


class SongRequest(BaseModel):
    """Represents a user's song request."""

    id: int = Field(..., description="The unique identifier for the song request.")
    song: Song = Field(..., description="The song being requested.")
    requested_by: str = Field(..., description="The user who requested the song.")
    is_added: bool = Field(
        default=False, description="Whether the song has been added to the playlist."
    )
