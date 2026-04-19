from enum import Enum

from pydantic import BaseModel, Field


class SongAdditionStatus(str, Enum):
    """Enum representing the status of song addition attempts."""

    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"


class SongSourceBackend(str, Enum):
    """Supported backends for reading song requests."""

    SUPABASE = "SUPABASE"
    SQLITE = "SQLITE"


class NeverendingSongsImportStatus(str, Enum):
    """Result status of a NeverendingSongs import run."""

    SUCCESS = "SUCCESS"
    SKIPPED_MAX_DB_SIZE = "SKIPPED_MAX_DB_SIZE"
    FAILED = "FAILED"


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


class NeverendingSongsSourceConfig(BaseModel):
    """Configuration for one REST source used by NeverendingSongs."""

    rest_url: str = Field(..., description="REST endpoint URL for source data.")


class NeverendingSongsMappedRecord(BaseModel):
    """Mapped record from source payload ready for database persistence."""

    artist: str = Field(..., description="Artist name.")
    song: str = Field(..., description="Song title.")
    airtime: str = Field(..., description="Original source airtime timestamp.")
    source: str = Field(..., description="Source system identifier.")
    status: SongAdditionStatus | None = Field(
        default=None,
        description="Playlist sync processing status.",
    )
    requested_by: str | None = Field(
        default=None,
        description="Optional requestor metadata.",
    )


class NeverendingSongsImportRun(BaseModel):
    """Summary of one NeverendingSongs import execution."""

    status: NeverendingSongsImportStatus = Field(..., description="Run status.")
    imported_count: int = Field(
        default=0, description="Count of rows written to database."
    )
    source_count: int = Field(default=0, description="Count of queried sources.")
    details: str | None = Field(default=None, description="Optional technical details.")


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
    """Error types for Playlist-Clear operations"""

    PLAYBACK_INACTIVE = "PLAYBACK_INACTIVE"
    WRONG_PLAYLIST = "WRONG_PLAYLIST"
    ERROR = "ERROR"


class PlaylistClearError(BaseModel):
    """Detailed error information for Playlist-Clear operations."""

    error_code: PlaylistClearFailure = Field(
        ...,
        description="Der Fehlertyp für die Playlist-Clear-Operation.",
    )
    message: str = Field(
        ...,
        description="A user-friendly error message.",
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
    filled_count: int = Field(
        0,
        description="The number of tracks automatically added to the playlist during autofill to maintain the minimum track count.",
    )
