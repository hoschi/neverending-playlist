# NeverendingSongs Implementation

Dieses Dokument beschreibt die integrierte NeverendingSongs-Logik innerhalb von Neverending Playlist, inklusive Datenfluss, Mapping und SQLite-Schema als gemeinsame Schnittstelle zwischen Import und Playlist-Synchronisierung.

## Zielbild

- Die bisherige n8n-Importlogik wird in den Server integriert.
- Importierte Songs landen in einer festen SQLite-Struktur.
- Die Playlist-Synchronisierung kann zwischen `SUPABASE` und `SQLITE` umschalten.
- Der Datenfluss bleibt nachvollziehbar und testbar.

## Feldmapping (n8n -> jq -> Zielstruktur)

Historische n8n-Feldpfade aus `current/n8n_workflow.json`:

- `artist = $json.song.entry[0].artist.entry[0].name`
- `song = $json.song.entry[0].title`
- `airtime = $json.airtime`

Aktuelle jq-Zielstruktur (Basis):

```jq
.result.entry[] | {
  artist: .song.entry[0].artist.entry[0].name,
  song: .song.entry[0].title,
  airtime: .airtime,
  source: "radio_bob"
}
```

## SQLite-Schema (fest)

Die gemeinsame, feste Struktur liegt in `src/core/sqlite_schema.py` und enthält:

- `song_requests`: kompatible Playlist-Felder (`artist`, `song`, `status`, `requested_by`) plus Importmetadaten (`airtime`, `source`, `external_id`, `created_at`)
- `neverending_songs_runs`: Laufhistorie für Importläufe (`run_at`, `status`, `imported_count`, `source_count`, `details`)

## Datenfluss (Phase 1 Zielbild)

```mermaid
flowchart LR
    A[Radio Bob REST API] --> B[JSON Payload]
    B --> C[jq Mapping]
    C --> D[(SQLite song_requests)]
    D --> E[Playlist Sync Source SUPABASE|SQLITE]
    E --> F[Spotify Playlist]
```
