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
2. Fill in your Supabase and Spotify API credentials in the `.env` file.

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
    - Start the web service: `poetry run uvicorn src.shell.api:app --reload`
    - Open your browser and navigate to `http://localhost:6361/login`.
    - You will be redirected to Spotify to log in and grant permission.
    - After you approve, you will be redirected back to the application's `/callback` endpoint.

Upon successful authorization, the application will automatically encrypt and save a `SPOTIFY_REFRESH_TOKEN` to your `.env` file. The service will use this token to stay logged in.

## Daily Work

### Running the Service
To start the web service, run the following command:
```bash
poetry run uvicorn src.shell.api:app --reload
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