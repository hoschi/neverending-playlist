# Quickstart: Refine Song Addition Status Logic

This document provides a quick overview of the changes introduced in this feature.

## API Changes

The `/sync-playlist` endpoint has been updated to provide a more detailed response about the status of each song.

### Request

The request body remains the same:

```json
{
  "playlist_id": "your-playlist-id",
  "songs": [
    {
      "song_title": "Bohemian Rhapsody",
      "artist_name": "Queen"
    },
    {
      "song_title": "Non Existent Song",
      "artist_name": "No One"
    }
  ]
}
```

### Response

The response will now be a JSON object with three arrays: `successful`, `not_found`, and `errors`.

**Success Response (HTTP 200)**

Returned when all songs are processed, even if some were not found.

```json
{
  "successful": [
    {
      "song_title": "Bohemian Rhapsody",
      "artist_name": "Queen"
    }
  ],
  "not_found": [
    {
      "song_title": "Non Existent Song",
      "artist_name": "No One"
    }
  ],
  "errors": []
}
```

**Error Response (HTTP 400)**

Returned if an error occurs while processing one or more songs.

```json
{
  "successful": [
    {
      "song_title": "Bohemian Rhapsody",
      "artist_name": "Queen"
    }
  ],
  "not_found": [],
  "errors": [
    {
      "song_title": "Another Song",
      "artist_name": "Some Artist"
    }
  ]
}
```

## Data Model Changes

The `SongRequest` entity in the database has been updated. The `added` boolean field has been replaced with a `status` field of type `SongAdditionStatus` which can have the following values: `PENDING`, `SUCCESS`, `NOT_FOUND`, `ERROR`.
