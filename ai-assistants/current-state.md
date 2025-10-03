# Current State: Supabase to Spotify Repository

## Repository Overview

Dies ist ein **funktionales Python-Projekt**. Aktuell sind **keine Features implementiert**, aber komplette **Infrastruktur, Tooling und Code-Style-Grundlagen** sind konfiguriert mit Beispielcode für AI Coding Assistants.

## Architektur: Functional Core, Imperative Shell (FCIS)

- **`src/core/`** - Funktionaler Kern: reine Business-Logik, keine Seiteneffekte
- **`src/shell/`** - Imperative Schale: I/O, APIs, CLI, Logging, orchestriert Core-Funktionen

## Aktuelle Dateien im `src/` Verzeichnis

### Core-Module (Funktionaler Kern)

- **`src/__init__.py`** - Leere Package-Initialisierung
- **`src/py.typed`** - Signalisiert Type-Checker Unterstützung für Inline Type-Hints (PEP 561)

#### src/core/

- **`__init__.py`** - Leere Core-Package Initialisierung
- **`config.py`** - Pydantic Settings für `log_level`, `log_to_file`. Lädt aus `.env`. Globale type-safe `settings` Instanz
- **`models.py`** - Pydantic Datenmodelle: `User` (id, name, age mit Validierung), `ApiResponse` (status, data). Immutable Strukturen
- **`protocols.py`** - `Fetcher[KeyType, ReturnType]` Protocol. Generisches Interface für Daten-Fetching mit `future_safe` async Operations
- **`services.py`** - Business-Logik: `example_transform_service()` (Text-Transform mit Result), `get_user_details()` (User-Fetching mit Dependency Inversion)

### Shell-Module (Imperative Schale)

#### src/shell/

- **`__init__.py`** - Leere Shell-Package Initialisierung
- **`api.py`** - FastAPI Web-Interface: `InMemoryUserFetcher` (Protocol-Implementierung), Endpoints `/users/{id}`, `/transform/`. Demonstriert Core-Service Integration
- **`cli.py`** - Typer CLI: Commands `transform`, `get-user`. Rich-formatierte Ausgabe. Async Integration mit Core-Services via `anyio.run()`
- **`logging_config.py`** - Loguru-Setup basierend auf Settings. Console-Logger mit Farben, optionaler File-Logger (10MB Rotation, 7 Tage Retention)

## Development Setup

**Tools:** Ruff (Lint+Format), MyPy+BasedPyright (Strict Typing), Pytest (95% Coverage), Poetry, Poe Tasks
**Environment:** Python 3.12, Conda
