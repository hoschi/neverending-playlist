# Supabase to Spotify

This project provides a web service to synchronize song requests from a Supabase database to a Spotify playlist.

## Features

- **Playlist Synchronization**: A FastAPI endpoint (`POST /sync-playlist`) fetches pending song requests from a Supabase table, finds the corresponding tracks on Spotify, and adds them to a specified playlist. The `/sync-playlist` endpoint returns a comprehensive response with details about successful additions, not found tracks, and any errors encountered.
- **Clear Played Tracks**: A new FastAPI endpoint (`POST /clear-played`) removes tracks from the beginning of a Spotify playlist that have already been played. This endpoint only works when music is actively playing from the configured playlist.
- **Configurable**: All external service credentials and settings are managed via a `.env` file.
- **Robust & Testable**: Built with a "Functional Core, Imperative Shell" architecture, ensuring the business logic is isolated and easily testable. It uses the `returns` library for explicit, railway-oriented error handling.

## API Endpoints

### POST /sync-playlist

Synchronizes the playlist by fetching pending song requests from Supabase and adding them to Spotify.

**Query Parameters:**
- `max_count` (optional, default: 10, max: 50): Maximum number of pending song requests to process.

**Response:**
```json
{
  "successful": ["123", "456"],
  "not_found": ["789"],
  "errors": []
}
```

**Response Fields:**
- `successful`: List of song IDs that were successfully added to the playlist.
- `not_found`: List of song IDs that could not be found on Spotify.
- `errors`: List of error messages for songs that failed to be added due to errors.

**Example Response:**
```json
{
  "successful": ["1", "2", "3"],
  "not_found": ["4"],
  "errors": ["Failed to add song ID 5: API rate limit exceeded"]
}
```

### POST /clear-played

Removes tracks from the beginning of the configured playlist that have already been played. This operation is conditional and will only execute if music is actively playing from the correct playlist.

**Response (200 OK):**
```json
{
  "deleted_count": 5
}
```

**Response Fields:**
- `deleted_count`: Number of tracks successfully removed from the playlist.

**Error Responses:**
- **400 Bad Request**: Current track is not from the configured playlist
  ```json
  {
    "detail": {
      "error": "wrong_playlist",
      "message": "The currently playing song is not from the configured playlist."
    }
  }
  ```

- **409 Conflict**: No active playback found
  ```json
  {
    "detail": {
      "error": "playback_inactive",
      "message": "Cannot clear tracks when no music is playing."
    }
  }
  ```

- **500 Internal Server Error**: Unexpected API errors
  ```json
  {
    "detail": {
      "error": "internal_server_error",
      "message": "An unexpected error occurred."
    }
  }
  ```

**Example Usage:**
```bash
curl -X POST "http://localhost:6361/clear-played"
```

**Requirements:**
- Music must be actively playing from Spotify
- The currently playing track must be from the configured playlist
- OAuth authorization must be completed

## Project Setup

### 1. Prerequisites
- [Conda](https://docs.conda.io/en/latest/miniconda.html) for environment management.
- [Poetry](https://python-poetry.org/docs/#installation) for package management.
- [Poe the Poet](https://poethepoet.natn.io/installation.html) for task management.

### 2. Installation

```bash
# Create and activate the conda environment
conda env create --file conda.yml
conda activate supabase-to-spotify

# Install dependencies using Poetry
poetry install

# add git filter for Jupyter notebooks
nbstripout --install
```

### 3. Configuration
1. Copy `.env.example` to `.env`.
2. Enter your Supabase and Spotify API credentials in the `.env` file.

### 4. Linking your Spotify Account

To link your Spotify account to the service, follow these steps:

1. **Create a Spotify Developer Application**
    - Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create a new application.
    - Copy the **Client ID** and **Client Secret** into the `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` fields in your `.env` file.
     - Add the URI from `SPOTIFY_REDIRECT_URI` (`http://localhost:6361/callback`) to the "Redirect URIs" section in the dashboard. The URI must match exactly.

2. **Enter your Playlist ID**
    - Create a new playlist in your Spotify account.
    - Copy the playlist ID from the URL and enter it in `SPOTIFY_PLAYLIST_ID`.

3. **Generate an Encryption Key**
    - Generate a 32-byte, URL-safe, base64-encoded key:
      ```python
      from cryptography.fernet import Fernet
      key = Fernet.generate_key().decode()
      print(key)
      ```
    - Add this key as `ENCRYPTION_KEY` in your `.env` file.

4. **Perform OAuth Authorization**
    - Start the web service:
      ```bash
      poetry run python src/shell/api.py
      ```
    - Open `https://localhost:6361/login` in your browser.
    - You will be redirected to Spotify to authorize the application.
    - After successful login and approval, you will be redirected back to the application (`/callback`).
    - The service will automatically save the encrypted `SPOTIFY_REFRESH_TOKEN` in your `.env` file.

**Note:** The values for `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_REDIRECT_URI` must match exactly with the settings in the Spotify Developer Dashboard. The redirect URI must be registered there.

For more details on Spotify OAuth, see the [Spotipy documentation](https://spotipy.readthedocs.io/en/latest/#authorization-code-flow) and the [Spotify Developer Guide](https://developer.spotify.com/documentation/web-api/tutorials/code-flow).

### 5. Authorization
This application uses the OAuth 2.0 Authorization Code Flow to access your Spotify account. You must authorize it once before you can use the `/sync-playlist` endpoint.

1.  **Configure Environment**: Ensure your `.env` file has the correct `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, and `SPOTIFY_REDIRECT_URI`. The `SPOTIFY_REDIRECT_URI` must match what you have configured in your Spotify Developer Dashboard.
2.  **Generate Encryption Key**: You need a 32-byte, URL-safe, base64-encoded encryption key. You can generate one with the following Python code:
    ```python
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    print(key)
    ```
    Add this key to your `.env` file as `ENCRYPTION_KEY`.
3.  **Authorize the Application**:
    - Start the web service: `poetry run python src/shell/api.py`
    - Open your browser and navigate to `http://localhost:6361/login`.
    - You will be redirected to Spotify to log in and grant permission.
    - After you approve, you will be redirected back to the application's `/callback` endpoint.

Upon successful authorization, the application will automatically encrypt and save a `SPOTIFY_REFRESH_TOKEN` to your `.env` file. The service will use this token to stay logged in.

### 6. Supabase

#### Locally Hosted Supabase Instance

**Finding Access Credentials**:
- Go to your local Supabase UI
- Click on the profile icon in the top right corner and select "Command Menu"
- Run "Copy API URL" and paste it into `SUPABASE_URL` in the `.env` file
- Run "Get API keys", select "Copy service API key" and paste it into `SUPABASE_KEY` in the `.env` file

#### Supabase Cloud (https://supabase.com/)

1. **Create Project**:
   - Log in to Supabase and create a new project
   - Select a region close to your location for better performance
2. **Finding Access Credentials**:
   - After project creation, go to Project Settings > API
   - Copy the `URL` and `public anon key` into your `.env` file:
     ```env
     SUPABASE_URL="https://your-project-id.supabase.co"
     SUPABASE_KEY="your-public-anon-key"
     ```
3. **Table Permissions**:
   - Ensure the service account (public anon key) has read/write permissions for your table
   - Go to Authentication > Policies and create appropriate access rules

For more details, see the [Supabase Documentation](https://supabase.com/docs).

#### Database Schema

Here is the SQL statement to create the table (replace `your_table_name` with your actual table name):

```sql
CREATE TABLE public.your_table_name (
    id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    artist TEXT NOT NULL,
    song TEXT NOT NULL,
    status TEXT,
    requested_by TEXT
);
```

To copy data from an existing table with `artist` and `song` columns into the newly created table, you can use the following SQL command. Replace `your_existing_table` with the name of your source table.

```sql
INSERT INTO public.your_table_name (artist, song)
SELECT artist, song
FROM your_existing_table;
```

If you want to import only a limited number of records, for example 30, you can add `LIMIT 30` to the query:

```sql
INSERT INTO public.your_table_name (artist, song)
SELECT artist, song
FROM your_existing_table
LIMIT 30;
```

### 7. Setup SSL Certificates

For development with HTTPS, you need to create SSL certificates and keys. This guide shows you how to create self-signed certificates for local development.

#### 1. Create SSL folder

First, create a folder for your SSL certificates:

```bash
mkdir -p ssl
```

#### 2. Generate private key

Generate a private key with 2048 bits:

```bash
openssl genrsa -out ssl/key.pem 2048
```

#### 3. Create self-signed certificate

Create a self-signed certificate that is valid for one year:

```bash
openssl req -new -x509 -key ssl/key.pem -out ssl/cert.pem -days 365 -subj "/CN=localhost"
```

#### 4. Configure environment variables

Add the following lines to your `.env` file to specify the paths to your SSL files:

```
SSL_CERT_PATH=ssl/cert.pem
SSL_KEY_PATH=ssl/key.pem
```

#### Note

These self-signed certificates are only suitable for local development. For production environments, you should use certificates signed by a trusted Certificate Authority (CA).

## Daily Work

### Running the Service
To start the web service, run the following command:
```bash
poetry run python src/shell/api.py
```

### Running Quality Checks

This project is equipped with a comprehensive set of quality gates. To run them all locally, use the following commands:

```bash
# Run linter and formatter check
ruff check .
ruff format --check .

# Run static type checking
mypy

# Run tests and generate coverage reports
pytest

# Run all checks
poe check-all
```

To view the interactive coverage report after running the tests, open `htmlcov/index.html` in your browser.

### Interactive Documentation

The `docs/` directory contains interactive Jupyter Notebooks. They are the best way to learn the core concepts and patterns used in this project.

1.  **Open the project in VS Code.**
2.  **Make sure you have the recommended extensions installed (VS Code will prompt you).**
3.  **Select the project's Python interpreter: YOUR CONDA ENV.**
4.  **Open `docs/01_core_concepts.ipynb` or `docs/02_advanced_patterns.ipynb`.**
5.  **Run the code cells one by one to see the concepts in action.**

Each code cell ends with `assert` statements, making the documentation self-verifying.

## 🤖 Working with AI Assistants (Cursor, Gemini, etc.)

This project is specifically optimized to work with modern AI coding assistants. To ensure high code quality, we have created a "manifest" for AIs.

### Setup

Cursor and Gemini are already set up for you.

**For other tools:**
Explicitly include the main directive in your prompt. Example:
```bash
claude "Refactor the 'process_data' function in 'src/core/services.py'. Strictly follow the instructions from 'ai-assistants/01-main-directives.md'."
```

### The Rules

The `ai-assistants/` directory contains the complete set of rules. The AI is automatically referred to the relevant documents to ensure it always operates within the project's context.
