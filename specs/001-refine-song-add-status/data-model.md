# Data Model: Refine Song Addition Status Logic

## Entities

### SongRequest

Represents a user's request to add a song to a playlist.

**Fields**:

- `id`: `UUID` - Unique identifier for the request.
- `playlist_id`: `UUID` - The ID of the playlist to add the song to.
- `song_title`: `str` - The title of the song.
- `artist_name`: `str` - The name of the artist.
- `added`: `SongAdditionStatus` - The status of the song addition process.
- `created_at`: `datetime` - Timestamp of when the request was created.

**State Transitions**:

The `added` field will transition from a default state (e.g., `PENDING`) to one of the final states: `SUCCESS`, `NOT_FOUND`, or `ERROR`.

## Enumerations

### SongAdditionStatus

An enumeration representing the possible states of a song addition attempt.

**Values**:

- `SUCCESS`: The song was successfully found and added to the playlist.
- `NOT_FOUND`: The song could not be found on Spotify.
- `ERROR`: An unexpected error occurred while trying to add the song.
- `PENDING`: The song has not yet been processed.
