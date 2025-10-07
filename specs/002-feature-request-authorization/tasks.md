# Task Breakdown: Authorization Code Flow

This plan is based on the design artifacts and follows a Test-Driven Development (TDD) approach.

## Phase 1: Setup and Configuration

- [ ] **Task 1**: Update `core/config.py` to include new required settings: `SPOTIFY_REDIRECT_URI` and an encryption key for the refresh token.
- [ ] **Task 2**: Enhance `.env.example` with `SPOTIFY_REDIRECT_URI` and `ENCRYPTION_KEY`.
- [ ] **Task 3**: Create a new service in `core/services/encryption_service.py` with `encrypt` and `decrypt` functions.
- [ ] **Task 4**: Write unit tests for the `encryption_service` to ensure round-trip consistency.

## Phase 2: Authorization Flow Endpoints

- [ ] **Task 5**: Create a new API route `/login` in `shell/api.py`. This endpoint will generate the Spotify authorization URL and redirect the user.
- [ ] **Task 6**: Create a new API route `/callback` in `shell/api.py`. This endpoint will handle the response from Spotify, exchange the code for tokens, and save the encrypted refresh token.
- [ ] **Task 7**: Write integration tests for the `/login` endpoint to verify it redirects to the correct Spotify URL.
- [ ] **Task 8**: Write integration tests for the `/callback` endpoint, mocking the Spotify token exchange, to verify it handles success and error responses correctly.

## Phase 3: Spotify Client Refactoring

- [ ] **Task 9**: Refactor the existing Spotify client in `shell/clients.py` to use the Authorization Code Flow with `spotipy.SpotifyOAuth`.
- [ ] **Task 10**: The client should now load the encrypted refresh token from the environment, decrypt it, and use it to initialize the `spotipy` client.
- [ ] **Task 11**: Implement logic to re-encrypt and save the refresh token if `spotipy` provides a new one after a refresh.
- [ ] **Task 12**: Write unit tests for the refactored Spotify client, mocking `spotipy` and the file system to test token loading, decryption, and re-saving.

## Phase 4: Integration and Finalization

- [ ] **Task 13**: Update the `sync_playlist` service to use the new authentication mechanism.
- [ ] **Task 14**: Manually run through the `quickstart.md` guide to perform a full end-to-end test of the authorization flow.
- [ ] **Task 15**: Update the project's `README.md` with instructions on how to set up and use the new authorization flow.
