# Quickstart: Supabase-Spotify Playlist Bridge

This guide provides step-by-step instructions to set up and run the Supabase-Spotify playlist synchronization service.

## 1. Prerequisites
- **Project Setup**: Ensure you have completed the initial project setup as described in the main [README.md](../../../README.md), including installing Conda, Poetry, and all dependencies.
- **Supabase Account**: A Supabase project is required. You can use a free-tier cloud instance for testing.
- **Spotify Developer Account**: A Spotify developer account is needed to create an application and get API credentials.

## 2. Configuration
1.  **Environment File**: Copy the `.env.example` file to a new file named `.env`.
2.  **Supabase Credentials**:
    - In your Supabase project, navigate to **Project Settings** > **API**.
    - Copy the **Project URL** and **Service Role Key** (or the `anon` key if you have configured row-level security) into the `SUPABASE_URL` and `SUPABASE_KEY` fields in your `.env` file.
3.  **Spotify Credentials**:
    - Go to your [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create a new application.
    - Copy the **Client ID** and **Client Secret** into the `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` fields in your `.env` file.
    - Set the `SPOTIFY_REDIRECT_URI` to `http://localhost:8888/callback` (or any other valid URI).
    - Create a new playlist on your Spotify account and copy its ID into the `SPOTIFY_PLAYLIST_ID` field. You can find the ID in the playlist's URL.
4.  **Supabase Table**: In your Supabase project, create a table named `song_requests` with the following columns:
    - `id` (int, primary key)
    - `artist` (text)
    - `title` (text)
    - `requested_by` (text)
    - `is_added` (boolean, default: `false`)

## 3. Running the Service
To start the web service, run the following command from the project root:
```bash
poetry run uvicorn src.shell.api:app --reload
```
The service will be available at `http://localhost:8000`.

## 4. Testing the Endpoint
You can test the synchronization by sending a `POST` request to the `/sync-playlist` endpoint. This will fetch up to 10 pending songs from your Supabase table and add them to your Spotify playlist.

```bash
curl -X POST "http://localhost:8000/sync-playlist?max_count=10"
```

### Expected Response
A successful response will look like this:
```json
{
  "status": "success",
  "songs_added": 2
}
```

## 5. Verifying the Results
- **Check your Spotify playlist**: The new songs should appear in the playlist you specified.
- **Check your Supabase table**: The `is_added` column for the synchronized songs should now be set to `true`.