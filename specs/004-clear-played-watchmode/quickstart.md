# Quickstart: Clear Played Watchmode

This guide explains how to use the `GET /clear-played-watchmode` endpoint to automatically clear played tracks from your playlist.

## Activating the Checker

To start the automated checker, send a GET request to the `/clear-played-watchmode` endpoint.

**Prerequisite**: You must have an active music playback session on Spotify for the checker to start.

```bash
curl -X GET "http://localhost:6361/clear-played-watchmode"
```

### Success Response (Checker Installed)

If playback is detected and no checker is currently running, the endpoint will respond with:

```json
{
  "status": "checker_installed"
}
```

This confirms that the background task has been started. It will now run every 10 minutes to call the `/clear-played` logic.

## Checking the Status

If you call the endpoint while a checker is already running, it will return the current status of the checker.

```bash
curl -X GET "http://localhost:6361/clear-played-watchmode"
```

### Success Response (Checker Running)

```json
{
  "status": "checker_running",
  "state": {
    "is_running": true,
    "retries_left": 5,
    "last_playback_detected": true,
    "last_checked": "2025-11-21T10:00:00Z",
    "next_check": "2025-11-21T10:10:00Z"
  }
}
```

This response provides details about the checker's current state, including when the next check is scheduled.

## Error Response

If you try to activate the checker when no music is playing, you will receive a `400 Bad Request` error.

```json
{
  "detail": "No active playback detected. Checker not started."
}
```
