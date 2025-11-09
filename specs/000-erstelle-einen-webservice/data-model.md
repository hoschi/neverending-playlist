# Data Model: Supabase-Spotify Playlist Bridge

## Entities

### SongRequest
- **artist**: str
- **song**: str
- **airtime**: timestamptz (Primärschlüssel)
- **state**: str ("added", "not_found", "error", oder leer)
- **last_changed**: timestamptz

## Validation Rules
- `artist` und `song` dürfen nicht leer sein
- `airtime` muss eindeutig sein (Primärschlüssel)
- `state` darf nur die Werte "added", "not_found", "error" oder leer enthalten
- `last_changed` wird bei jeder Statusänderung aktualisiert

## State Transitions
- Initial: `state` ist leer
- Nach erfolgreichem Hinzufügen zu Spotify: `state` → "added"
- Wenn Song nicht gefunden: `state` → "not_found"
- Bei API-/Netzwerkfehler: `state` → "error"

## Relationships
- Keine weiteren Entitäten oder Relationen erforderlich

---

**Phase 1: data-model.md abgeschlossen.**
