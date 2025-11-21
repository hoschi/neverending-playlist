# Quickstart: Clear Played Tracks

This guide explains how to use the new `POST /clear-played` endpoint.

## Prerequisites

- The application must be running.
- You must have a valid authentication token (if authentication is required by the API).
- Music must be actively playing from the playlist specified in your `.env` configuration file.

## Usage

You can trigger the operation by sending a `POST` request to the `/clear-played` endpoint.

### Example Request with `curl`

```bash
# Replace YOUR_API_BASE_URL with the actual URL where the service is running
# e.g., http://localhost:8000

curl -X POST "YOUR_API_BASE_URL/clear-played"
```

### Success Response (200 OK) - Nothing to Delete

If no tracks need to be deleted, you will receive a `200 OK` status code:

```json
{
  "deleted_count": 0,
  "filled_count": 0
}
```

### Success Response (200 OK) - Successful Autofill

If tracks were successfully removed and the playlist was refilled, you will receive a `200 OK` status code:

```json
{
  "deleted_count": 5,
  "filled_count": 15
}
```

### Partial Success Response (207 Multi-Status)

If tracks were successfully removed but there were insufficient songs available in Supabase to refill the playlist, you will receive a `207 Multi-Status` status code.

```json
{
  "deleted_count": 3,
  "filled_count": 0,
  "message": "Partial success: Deleted 3 tracks. Not enough songs available in Supabase to complete autofill to minimum count."
}
```

**Status Code Logic:**
- **200 OK**: Returned when `deleted_count == 0` (nothing to delete) OR `filled_count > 0` (successful deletion + autofill)
- **207 Multi-Status**: Returned when `deleted_count > 0` AND `filled_count == 0` (partial success - tracks deleted but no songs available for autofill)

**Response Field Explanations:**
- `deleted_count`: Number of tracks successfully removed from the playlist (not including autofilled tracks)
- `filled_count`: Number of tracks automatically added to the playlist during autofill to maintain the minimum track count
- `message`: Additional context information (primarily for 207 responses)

### Error Response: Playback Inactive (409 Conflict)

If no music is currently playing, you will receive a `409 Conflict` status code.

```json
{
  "error": "playback_inactive",
  "message": "Cannot clear tracks when no music is playing."
}
```

### Error Response: Wrong Playlist (400 Bad Request)

If music is playing but from a different playlist than the one configured, you will receive a `400 Bad Request` status code.

```json
{
  "error": "wrong_playlist",
  "message": "The currently playing song is not from the configured playlist."
}
```
