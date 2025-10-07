# Quickstart: Authorization Code Flow

This guide walks through testing the end-to-end authorization flow.

## Prerequisites
- The application is running.
- You have a Spotify developer application configured with a `client_id`, `client_secret`, and a `redirect_uri` set to the application's callback URL (e.g., `http://localhost:8000/callback`).
- The `.env` file is configured with the `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_REDIRECT_URI`.

## Steps

### 1. Initiate Authorization
- **Action**: Send a GET request to the `/login` endpoint of the application.
- **Expected Result**: The application should redirect you to the Spotify login and authorization page in your browser.

### 2. Grant Permissions
- **Action**: On the Spotify page, log in with a valid Spotify account and click "Agree" to grant the requested permissions.
- **Expected Result**: Spotify will redirect you back to the application's `/callback` endpoint.

### 3. Verify Successful Authorization
- **Action**: The application will handle the callback, exchange the authorization code for tokens, and store the refresh token.
- **Expected Result**: The application should display a success message or redirect to a success page. Check the application logs to confirm that the tokens were received. The `.env` file should now contain an encrypted `SPOTIFY_REFRESH_TOKEN`.

### 4. Test Authenticated API Call
- **Action**: Send a request to an application endpoint that requires Spotify authorization (e.g., an endpoint to add a track to a playlist).
- **Expected Result**: The application should use the stored tokens to successfully make a request to the Spotify API on your behalf. The track should be added to the specified playlist.
