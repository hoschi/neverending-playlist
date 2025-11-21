# Research: Clear Played Tracks

This document outlines the investigation into the existing codebase to determine the best approach for implementing the "Clear Played Tracks" feature.

## How to Interact with the Spotify API

### Decision
Utilize the existing `SpotifyClient` class located in `src/shell/clients.py`. This client is already configured with the necessary authentication and credentials via the application's configuration.

### Rationale
Reusing the existing client adheres to the DRY principle and avoids duplicating setup and authentication logic. The client is already integrated into the application's dependency injection system, making it readily available to the API layer.

### Investigation Details
- The `SpotifyClient` class wraps the `spotipy.Spotify` client.
- It is instantiated and configured in `src/shell/api.py` within the `create_app` function.
- Key methods to use will be:
    - `currently_playing()`: To get the user's current playback state, including the playing track and context (which contains the playlist URI).
    - `playlist_items()`: To get all tracks in the target playlist.
    - `playlist_remove_items()`: To remove the identified tracks.

## How to Handle Configuration

### Decision
Access the target `PLAYLIST_ID` from the `Config` object provided in `src/core/config.py`.

### Rationale
The project already has a centralized Pydantic-based configuration management system. The `PLAYLIST_ID` is expected to be defined in the `.env` file and loaded into the `Config` model. This is the established pattern for managing environment-specific settings.

## How to Structure the Core Logic

### Decision
A new pure function, `clear_played_tracks_from_playlist`, will be created in `src/core/services/playlist_service.py`.

### Rationale
This aligns with the FCIS architecture. The function will be stateless and receive all necessary data (e.g., current playback state, playlist items) as arguments. It will return a `Result` object containing either a success value (number of tracks to be deleted) or a failure object indicating the reason for inaction (e.g., no active playback, wrong playlist). This keeps the core business logic pure and easily testable, completely decoupled from the Spotify API.
