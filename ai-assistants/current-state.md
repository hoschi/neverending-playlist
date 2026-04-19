# Current State

**Zuletzt aktualisiert:** 19. April 2026, 15:10 UTC

## Repository Overview

Dies ist ein **funktionales Python-Projekt**, das einen Webservice zur Synchronisierung von Song-Anfragen aus einer Supabase-Datenbank in eine Spotify-Playlist bereitstellt. Das Projekt implementiert den **OAuth 2.0 Authorization Code Flow** für die Spotify-Authentifizierung. Zusätzlich zu der Playlist-Synchronisation wurde das **"Clear Played Tracks"** Feature hinzugefügt, mit **"Autofill-Funktionalität"**.

## Architektur: Functional Core, Imperative Shell (FCIS)

- **`src/core/`** - Funktionaler Kern: Definiert die Business-Logik, Datenmodelle und Protokolle. Enthält keine Seiteneffekte und ist vollständig testbar.
- **`src/shell/`** - Imperative Schale: Stellt die FastAPI-Web-API, Client-Implementierungen und Logging-Konfiguration bereit. Orchestriert die Core-Funktionen und interagiert mit externen Diensten.

## Aktuelle Dateien im `src/` Verzeichnis

### Core-Module (Funktionaler Kern)

- **`src/__init__.py`** - Leere Package-Initialisierung.
- **`src/py.typed`** - Signalisiert Type-Checker Unterstützung für Inline Type-Hints (PEP 561).

#### src/core/

- **`__init__.py`** - Leere Core-Package Initialisierung.
- **`config.py`** - Pydantic Settings für Supabase/Spotify sowie NeverendingSongs-Basiskonfiguration: umschaltbare Song-Quelle (`SUPABASE|SQLITE`), SQLite-Pfad im Repo-Root und Maximalgröße, sowie verpflichtende Liste von REST-URLs für mehrere Quellen (`song_source_rest_urls`). Der `source` wird aus der URL-Domain abgeleitet. Optionaler macOS-Notification-Flag bleibt enthalten.
- **`models.py`** - Pydantic Datenmodelle und Enums für Playlist-Sync sowie NeverendingSongs-Basisdomäne: zusätzliche Backends/Import-Status-Enums, Source-Konfiguration, gemappte Import-Datensätze und Import-Run-Summary. Enthält weiterhin `Song`, `SongRequest`, `SyncResult`/`SyncFailure` und Playlist-Clear Modelle.
- **`sqlite_schema.py`** - Definiert das feste SQLite-Schema als gemeinsame Schnittstelle für Import und Playlist-Sync: `song_requests` (inkl. `airtime`/`source`) und `neverending_songs_runs` für Laufhistorie, jeweils als zentrale SQL-Statements.
- **`protocols.py`** - Definiert die `SupabaseClient` und `SpotifyClient` Protokolle mit `@runtime_checkable`, um die Entkopplung zwischen Shell und Core zu gewährleisten. `SpotifyClient` um `get_current_playback`, `get_playlist_items`, `remove_items_from_playlist`.

#### src/core/services/

- **`__init__.py`** - Macht das `services`-Verzeichnis zu einem Python-Package.
- **`encryption_service.py`** - Ein Pydantic-basiertes Service-Modell, das symmetrische Verschlüsselung mit `cryptography.Fernet` für das sichere Speichern von Tokens implementiert.
- **`playlist_service.py`** - Enthält die Business-Logik `sync_playlist` (gibt SyncResult zurück), `add_songs_to_spotify`, um Songs von Supabase zu holen und zu Spotify hinzuzufügen. `clear_played_tracks_from_playlist` für das Entfernen von abgespielten Tracks. Autofill-Logik mit `_autofill_playlist()` für automatische Playlist-Auffüllung bis zur Mindestanzahl erreicht ist. Mehrfache Nachfüllversuche bei nicht gefundenen Liedern, **Error_count > 0 führt zu Fehlschlag**.

### Shell-Module (Imperative Schale)

#### src/shell/

- **`__init__.py`** - Leere Shell-Package Initialisierung.
- **`api.py`** - FastAPI Web-Interface. Stellt die Endpunkte `/login` und `/callback` für den OAuth-Flow sowie **`/sync-playlist`** (gibt 207 bei partial failure, sonst strukturierte Erfolge) für die Playlist-Synchronisation, **`/clear-played`** für das Entfernen von abgespielten Tracks und **`GET /clear-played-watchmode`** für die Aktivierung/Status-Abfrage des Watchmode-Features bereit. **`Korrektur`** des `/clear-played-watchmode` Endpunkts: Entfernte manuelle `next_check` Berechnung und verwendet jetzt direkt die Werte aus `CheckerState` für konsistente State-Verwaltung. `/clear-played` nutzt auch SupabaseClient für Autofill-Funktionalität.
- **`clients.py`** - Enthält die konkreten Implementierungen `ConcreteSupabaseClient` und `ConcreteSpotifyClient`, die die in `core/protocols.py` definierten Protokolle erfüllen. `ConcreteSpotifyClient` um die neuen Methoden für Playback-Check und Track-Entfernung.
- **`logging_config.py`** - Konfiguriert `Loguru` für strukturiertes Logging basierend auf den Einstellungen in `config.py`.
- **`state.py`** - Singleton-basiertes In-Memory State Management für den Watchmode WatchService. Thread-Safe Implementation mit `asyncio.Lock` für globalen Zustand.
- **`watch_service.py`** - Service-Klasse für das Watchmode-Feature. Implementiert die automatische Überwachung und Bereinigung von abgespielten Tracks mit konfigurierbaren Intervallen basierend auf `WATCH_SERVICE_TIMEOUT_MINUTES`. Verwendet `state.py` für State-Management. Startet Background-Tasks mit asyncio, prüft aktives Playback und führt automatisches Löschen durch. Retry-Counter wird nun korrekt zurückgesetzt, wenn Playback nach einem Stop wieder erkannt wird.
- **`cli.py`** - Ein einfacher Typer-CLI-Einstiegspunkt, der die `main`-Funktion für die API startet.

## Testabdeckung

- **Unit-Tests:** Testen Core Logik in `core/services/` und `core/models.py`, sowie Shell-Komponenten in `src/shell/` (inklusive WatchService)
- **Integrationstests:** Testen den vollständigen Sync-Flow und API-Endpunkte, inklusive Watchmode-Funktionalität
- **Contract-Tests:** Testen die API-Spezifikation mit `/sync-playlist` Endpunkt

## Development Setup

**Tools:** Ruff (Lint+Format), MyPy (Strict Typing), Pytest, Poetry, Poe Tasks
**Environment:** Python 3.12, Conda
