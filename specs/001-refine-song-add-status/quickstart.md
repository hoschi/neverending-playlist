# Quickstart: Refine Song Addition Status Logic

This document provides a quick overview of the changes introduced in this feature.

## API Changes

The `/sync-playlist` endpoint has been updated to provide a more detailed response about the status of each song. It does not take a request body.

### Response

The response will now be a JSON object with three arrays: `successful`, `not_found`, and `errors`, containing strings in the format `ARTIST - SONG`.

**Success Response (HTTP 200)**

Returned when all songs are processed, even if some were not found.

```json
{
  "successful": [
    "Queen - Bohemian Rhapsody"
  ],
  "not_found": [
    "No One - Non Existent Song"
  ],
  "errors": []
}
```

**Error Response (HTTP 400)**

Returned if an error occurs while processing one or more songs.

```json
{
  "successful": [
    "Queen - Bohemian Rhapsody"
  ],
  "not_found": [],
  "errors": [
    "Some Artist - Another Song"
  ]
}
```

## Data Model Changes

The `SongRequest` entity in the database has been updated. The `added` boolean field has been replaced with a `status` field of type `SongAdditionStatus` which can have the following values: `PENDING`, `SUCCESS`, `NOT_FOUND`, `ERROR`.
