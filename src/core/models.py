from enum import Enum

from pydantic import BaseModel, Field


class SongAdditionStatus(str, Enum):
    """Enum representing the status of song addition attempts."""

    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"


class Song(BaseModel):
    """Represents a song with artist and title."""

    artist: str = Field(..., description="The artist of the song.")
    title: str = Field(..., description="The title of the song.")


class SongRequest(BaseModel):
    """Represents a user's song request."""

    id: int = Field(..., description="The unique identifier for the song request.")
    song: Song = Field(..., description="The song being requested.")
    status: SongAdditionStatus | None = Field(
        default=None, description="The status of the song addition attempt to Spotify."
    )


class SyncFailure(BaseModel):
    """Represents a failure in song synchronization."""

    song_id: str = Field(..., description="The ID of the song that failed.")
    reason: str = Field(..., description="The reason for the failure.")


class SyncResult(BaseModel):
    """Represents the result of a playlist synchronization operation."""

    failures: list[SyncFailure] = Field(
        default_factory=list, description="List of failures."
    )
    successful: list[str] = Field(
        default_factory=list, description="List of successfully added song IDs."
    )
    not_found: list[str] = Field(
        default_factory=list, description="List of song IDs that were not found."
    )


class SyncPlaylistResult(BaseModel):
    """Represents the result of a playlist synchronization operation."""

    successful: list[str] = Field(
        default_factory=list, description="List of successfully added song IDs."
    )
    not_found: list[str] = Field(
        default_factory=list, description="List of song IDs that were not found."
    )
    errors: list[str] = Field(
        default_factory=list, description="List of error messages for failed additions."
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


class PlaylistClearFailure(str, Enum):
    """Fehlertypen für Playlist-Clear-Operationen"""

    PLAYBACK_INACTIVE = "PLAYBACK_INACTIVE"
    WRONG_PLAYLIST = "WRONG_PLAYLIST"
    ERROR = "ERROR"


class PlaylistClearError(BaseModel):
    """Detaillierte Fehlerinformationen für Playlist-Clear-Operationen."""

    error_code: PlaylistClearFailure = Field(
        ...,
        description="Der Fehlertyp für die Playlist-Clear-Operation.",
    )
    message: str = Field(
        ...,
        description="Eine benutzerfreundliche Fehlermeldung.",
    )
    details: str | None = Field(
        default=None,
        description="Zusätzliche technische Details zum Fehler.",
    )


class ClearPlayedTracksResponse(BaseModel):
    """Response model for the clear played tracks endpoint."""

    deleted_count: int = Field(
        ...,
        description="The number of tracks successfully deleted from the playlist.",
    )
