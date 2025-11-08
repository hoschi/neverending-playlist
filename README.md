# Supabase to Spotify

This project provides a web service to synchronize song requests from a Supabase database to a Spotify playlist.

## Features

- **Playlist Synchronization**: A FastAPI endpoint (`POST /sync-playlist`) fetches pending song requests from a Supabase table, finds the corresponding tracks on Spotify, and adds them to a specified playlist.
- **Configurable**: All external service credentials and settings are managed via a `.env` file.
- **Robust & Testable**: Built with a "Functional Core, Imperative Shell" architecture, ensuring the business logic is isolated and easily testable. It uses the `returns` library for explicit, railway-oriented error handling.

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

### Linking your Spotify Account

To link your Spotify account to the service, follow these steps:

1. **Create a Spotify Developer Application**
    - Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and create a new application.
    - Copy the **Client ID** and **Client Secret** into the `SPOTIPY_CLIENT_ID` and `SPOTIPY_CLIENT_SECRET` fields in your `.env` file.
    - Add the URI from `SPOTIPY_REDIRECT_URI` (`http://localhost:6361/callback`) to the "Redirect URIs" section in the dashboard. The URI must match exactly.

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

**Note:** The values for `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, and `SPOTIPY_REDIRECT_URI` must match exactly with the settings in the Spotify Developer Dashboard. The redirect URI must be registered there.

For more details on Spotify OAuth, see the [Spotipy documentation](https://spotipy.readthedocs.io/en/latest/#authorization-code-flow) and the [Spotify Developer Guide](https://developer.spotify.com/documentation/web-api/tutorials/code-flow).

### 4. Authorization
This application uses the OAuth 2.0 Authorization Code Flow to access your Spotify account. You must authorize it once before you can use the `/sync-playlist` endpoint.

1.  **Configure Environment**: Ensure your `.env` file has the correct `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, and `SPOTIPY_REDIRECT_URI`. The `SPOTIPY_REDIRECT_URI` must match what you have configured in your Spotify Developer Dashboard.
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