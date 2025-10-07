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


class UserAuthorization(BaseModel):
    """Represents the user's authorization data from Spotify."""

    spotify_user_id: str = Field(..., description="The Spotify user ID.")
    access_token: str = Field(..., description="The access token for API requests.")
    refresh_token: str = Field(
        ..., description="The refresh token for a new access token."
    )
    expires_at: int = Field(
        ..., description="The timestamp when the access token expires."
    )
    scope: str = Field(..., description="The scopes of access granted.")
