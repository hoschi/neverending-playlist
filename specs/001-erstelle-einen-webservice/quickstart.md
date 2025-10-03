# Quickstart: Supabase-Spotify Playlist Bridge

## Voraussetzungen
- Python 3.12
- poetry installiert
- Supabase lokal per Docker (siehe `.env.example`)
- Spotify-API-Zugangsdaten in `.env`

## Installation
```bash
poetry install
```

## Konfiguration
1. Kopiere `.env.example` nach `.env` und trage die Zugangsdaten ein.
2. Starte die lokale Supabase-Instanz (siehe Supabase-Doku).

## Starten des Webservice
```bash
poetry run uvicorn src.shell.api:app --reload
```

## Testen
```bash
poetry run poe check-all
```

## API-Aufruf
```bash
curl -X POST "http://localhost:8000/sync-playlist?max_count=10"
```

## Hinweise
- Logging-Level und weitere Einstellungen können über `.env` angepasst werden.
- Siehe `docs/01_core_concepts.ipynb` für Beispiele zu Datenvalidierung, Fehlerbehandlung und Logging.

---

**Phase 1: quickstart.md abgeschlossen.**
