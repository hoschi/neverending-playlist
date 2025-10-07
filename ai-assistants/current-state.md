# Current State: Supabase to Spotify Repository

## Repository Overview

Dies ist ein **funktionales Python-Projekt**, das einen Webservice zur Synchronisierung von Song-Anfragen aus einer Supabase-Datenbank in eine Spotify-Playlist bereitstellt. Das Projekt implementiert den **OAuth 2.0 Authorization Code Flow** für die Spotify-Authentifizierung.

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
- **`models.py`** - Pydantic Datenmodelle: `Song`, `SongRequest` und `UserAuthorization` für die Spotify-OAuth-Daten.
- **`protocols.py`** - Definiert die `SupabaseClient` und `SpotifyClient` Protokolle mit `@runtime_checkable`, um die Entkopplung zwischen Shell und Core zu gewährleisten.

#### src/core/services/

- **`__init__.py`** - Macht das `services`-Verzeichnis zu einem Python-Package.
- **`encryption_service.py`** - Ein Pydantic-basiertes Service-Modell, das symmetrische Verschlüsselung mit `cryptography.Fernet` für das sichere Speichern von Tokens implementiert.
- **`playlist_service.py`** - Enthält die Business-Logik `sync_playlist` und `add_songs_to_spotify`, um Songs von Supabase zu holen und zu Spotify hinzuzufügen.

### Shell-Module (Imperative Schale)

#### src/shell/

- **`__init__.py`** - Leere Shell-Package Initialisierung.
- **`api.py`** - FastAPI Web-Interface. Stellt die Endpunkte `/login` und `/callback` für den OAuth-Flow sowie `/sync-playlist` für die Playlist-Synchronisation bereit.
- **`clients.py`** - Enthält die konkreten Implementierungen `ConcreteSupabaseClient` und `ConcreteSpotifyClient`, die die in `core/protocols.py` definierten Protokolle erfüllen.
- **`cli.py`** - Ein einfacher Typer-CLI-Einstiegspunkt, der die `main`-Funktion für die API startet.
- **`logging_config.py`** - Konfiguriert `Loguru` für strukturiertes Logging basierend auf den Einstellungen in `config.py`.

## Development Setup

**Tools:** Ruff (Lint+Format), MyPy (Strict Typing), Pytest (95% Coverage), Poetry, Poe Tasks
**Environment:** Python 3.12, Conda