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

### Success Response (200 OK)

If tracks were successfully removed, you will receive a `200 OK` status code and a JSON body indicating the number of tracks deleted.

```json
{
  "deleted_count": 5
}
```

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
