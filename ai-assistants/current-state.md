# Current State: Supabase to Spotify Repository

## Repository Overview

Dies ist ein **funktionales Python-Projekt**, das einen Webservice zur Synchronisierung von Song-Anfragen aus einer Supabase-Datenbank in eine Spotify-Playlist bereitstellt. Das Projekt implementiert den **OAuth 2.0 Authorization Code Flow** für die Spotify-Authentifizierung. Zusätzlich zu der Playlist-Synchronisation wurde das **"Clear Played Tracks"** Feature hinzugefügt.

## Architektur: Functional Core, Imperative Shell (FCIS)

- **`src/core/`** - Funktionaler Kern: Definiert die Business-Logik, Datenmodelle und Protokolle. Enthält keine Seiteneffekte und ist vollständig testbar.
- **`src/shell/`** - Imperative Schale: Stellt die FastAPI-Web-API, Client-Implementierungen und Logging-Konfiguration bereit. Orchestriert die Core-Funktionen und interagiert mit externen Diensten.

## Aktuelle Dateien im `src/` Verzeichnis

### Core-Module (Funktionaler Kern)

- **`src/__init__.py`** - Leere Package-Initialisierung.
- **`src/py.typed`** - Signalisiert Type-Checker Unterstützung für Inline Type-Hints (PEP 561).

#### src/core/

- **`__init__.py`** - Leere Core-Package Initialisierung.
- **`config.py`** - Pydantic Settings für alle Konfigurationsvariablen, inklusive Supabase, Spotify OAuth und dem Encryption Key. Lädt aus `.env`.
- **`models.py`** - Pydantic Datenmodelle: `Song`, `SongRequest`, `UserAuthorization` für die Spotify-OAuth-Daten, `SongAdditionStatus`-Enum, `SyncPlaylistResult`, `SyncFailure`, `SyncResult`, `ClearPlayedTracksResponse` und `PlaylistClearFailure`.
- **`protocols.py`** - Definiert die `SupabaseClient` und `SpotifyClient` Protokolle mit `@runtime_checkable`, um die Entkopplung zwischen Shell und Core zu gewährleisten. `SpotifyClient` um `get_current_playback`, `get_playlist_items`, `remove_items_from_playlist`.

#### src/core/services/

- **`__init__.py`** - Macht das `services`-Verzeichnis zu einem Python-Package.
- **`encryption_service.py`** - Ein Pydantic-basiertes Service-Modell, das symmetrische Verschlüsselung mit `cryptography.Fernet` für das sichere Speichern von Tokens implementiert.
- **`playlist_service.py`** - Enthält die Business-Logik `sync_playlist` (gibt SyncResult zurück), `add_songs_to_spotify`, um Songs von Supabase zu holen und zu Spotify hinzuzufügen. `clear_played_tracks_from_playlist` für das Entfernen von abgespielten Tracks.

### Shell-Module (Imperative Schale)

#### src/shell/

- **`__init__.py`** - Leere Shell-Package Initialisierung.
- **`api.py`** - FastAPI Web-Interface. Stellt die Endpunkte `/login` und `/callback` für den OAuth-Flow sowie **`/sync-playlist`** (gibt 207 bei partial failure, sonst strukturierte Erfolge) für die Playlist-Synchronisation und **`/clear-played`** für das Entfernen von abgespielten Tracks bereit.
- **`clients.py`** - Enthält die konkreten Implementierungen `ConcreteSupabaseClient` und `ConcreteSpotifyClient`, die die in `core/protocols.py` definierten Protokolle erfüllen. `ConcreteSpotifyClient` um die neuen Methoden für Playback-Check und Track-Entfernung.
- **`cli.py`** - Ein einfacher Typer-CLI-Einstiegspunkt, der die `main`-Funktion für die API startet.
- **`logging_config.py`** - Konfiguriert `Loguru` für strukturiertes Logging basierend auf den Einstellungen in `config.py`.

## Testabdeckung

- **Unit-Tests:** Testen Core Logik in `core/services/` und `core/models.py`
- **Integrationstests:** Testen den vollständigen Sync-Flow und API-Endpunkte
- **Contract-Tests:** Testen die API-Spezifikation mit `/sync-playlist` Endpunkt

## Development Setup

**Tools:** Ruff (Lint+Format), MyPy (Strict Typing), Pytest (95% Coverage), Poetry, Poe Tasks
**Environment:** Python 3.12, Conda