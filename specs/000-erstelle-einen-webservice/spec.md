# Feature Specification: Supabase-Spotify Playlist Bridge

**Feature Branch**: `001-erstelle-einen-webservice`
**Created**: 2025-10-03
**Status**: Draft
**Input**: User description: "Erstelle einen Webservice, der als Brücke zwischen einer Supabase-Datenbank und einer Spotify-Playlist fungiert. Der Service stellt einen einzelnen HTTP-Endpunkt bereit, der ohne Authentifizierung zugänglich ist. Wenn dieser Endpunkt aufgerufen wird, liest er Song-Daten aus einer bestimmten Supabase-Tabelle. Die Kriterien für die Song-Auswahl sind wie folgt: Es werden nur Einträge berücksichtigt, bei denen das Feld state leer ist. Die ausgewählten Einträge werden nach dem Zeitstempel im Feld airtime sortiert. Optional kann über einen Query-Parameter max_count die maximale Anzahl der zu verarbeitenden Songs begrenzt werden. Wird dieser Wert nicht angegeben werden maximal 5000 Songs verarbeitet. Jeder ausgewählte Song (bestehend aus artist und song) wird zur Ziel-Spotify-Playlist hinzugefügt. Es ist dabei unerheblich, ob der Song bereits in der Playlist vorhanden ist; er soll in jedem Fall erneut hinzugefügt werden. Nach der Verarbeitung wird der Status jedes Eintrags in der Supabase-Tabelle aktualisiert: Bei erfolgreichem Hinzufügen zu Spotify wird der state auf "added" gesetzt. Konnte ein Song in Spotify nicht gefunden werden, wird der state auf "not_found" gesetzt. Trat ein anderer Fehler beim Hinzufügen auf, wird der state auf "error" gesetzt. Bei jeder Änderung eines Eintrags wird das Feld last_changed auf den aktuellen Zeitstempel aktualisiert. Das Endergebnis des Endpunkt-Aufrufs hängt vom Erfolg der Operationen ab: Wenn alle Songs fehlerfrei hinzugefügt wurden, gibt der Endpunkt den HTTP-Statuscode 200 zurück. Der Response Body enthält eine Liste der erfolgreich hinzugefügten Songs. Wenn während des Prozesses ein oder mehrere Fehler auftreten, werden alle Fehlermeldungen gesammelt. Der Endpunkt gibt dann den HTTP-Statuscode 500 zurück, und der Response Body enthält eine für Menschen lesbare Zusammenfassung aller aufgetretenen Fehler. Verhalten in Fehler- und Sonderfällen: Ungültiger max_count: Sollte der Parameter max_count den Wert 0 oder einen negativen Wert haben, wird die Anfrage mit dem HTTP-Statuscode 400 und einer entsprechenden Fehlermeldung abgelehnt. Keine Songs zu verarbeiten: Findet der Service keine zu verarbeitenden Songs in der Supabase-Tabelle, wird der Aufruf mit dem HTTP-Statuscode 404 und einer für Menschen lesbaren Fehlermeldung beendet. Playlist nicht gefunden: Kann die konfigurierte Spotify-Playlist nicht gefunden werden, wird die Anfrage ebenfalls mit dem HTTP-Statuscode 404 und einer klaren Fehlermeldung abgelehnt, da die Grundvoraussetzung für die Operation nicht erfüllt ist. Kommunikationsfehler: Treten während der Kommunikation mit Supabase oder Spotify unvorhergesehene Probleme auf (z. B. Netzwerkfehler), bricht der Prozess ab und der Endpunkt gibt den HTTP-Statuscode 500 mit einer allgemeinen, für Menschen lesbaren Fehlermeldung zurück."

---
## Clarifications
### Session 2025-10-03
- Q: Soll die Aktualisierung der `state`- und `last_changed`-Felder in der Supabase-Tabelle für alle Songs atomar erfolgen (d. h. entweder alle Updates werden übernommen oder keine), oder ist es akzeptabel, dass einzelne Einträge auch bei Fehlern teilweise aktualisiert werden? → A: Atomar: Alle Updates in einer Transaktion, bei Fehler Rollback
- Q: Wie wird die Eindeutigkeit eines Song-Eintrags in der Supabase-Tabelle bestimmt? Gibt es einen eindeutigen Primärschlüssel (z. B. `id`), oder ist die Kombination aus `artist`, `song` und `airtime` eindeutig? → A: `airtime` ist der Primärschlüssel
- Q: Gibt es ein Ziel für die maximale Verarbeitungszeit (Latenz) pro Request, z. B. für 1000 Songs? Falls ja, bitte Wert angeben. → A: gibt es nicht
- Q: Wie soll der Service reagieren, wenn das Hinzufügen eines Songs zu Spotify wegen eines temporären API-Limits (Rate Limiting) fehlschlägt? → A: Song auf „error“ setzen, Rest weiterverarbeiten
- Q: Werden im Service personenbezogene Daten verarbeitet, die besonderen Datenschutzanforderungen (z. B. DSGVO) unterliegen? → A: Nein, keine personenbezogenen Daten


## User Scenarios & Testing *(mandatory)*

### Primary User Story
As a system administrator, I want to trigger a webservice endpoint to synchronize new song entries from a Supabase database to a specific Spotify playlist, so that the playlist is kept up-to-date with the latest aired songs automatically.

### Acceptance Scenarios
1.  **Given** there are 10 new song entries in the Supabase table with an empty `state`.
    **When** the webservice endpoint is called without a `max_count` parameter.
    **Then** the service finds the 10 songs, adds them to the Spotify playlist, updates their `state` to "added" and `last_changed` in Supabase, and returns an HTTP 200 status with a list of the 10 added songs.

2.  **Given** there are 5 new song entries, and one of them cannot be found on Spotify.
    **When** the endpoint is called.
    **Then** the service processes all 5 songs, updates 4 to "added", 1 to "not_found", updates `last_changed` for all 5, and returns an HTTP 500 status with a summary of the "not_found" error.

3.  **Given** the Supabase table contains no entries with an empty `state`.
    **When** the endpoint is called.
    **Then** the service returns an HTTP 404 status with a message "No songs to process."

### Edge Cases
-   **Spotify Rate Limiting**: Schlägt das Hinzufügen eines Songs zu Spotify wegen eines temporären API-Limits fehl, wird der betroffene Song auf "error" gesetzt und die Verarbeitung der restlichen Songs fortgesetzt.
-   **Invalid `max_count`**: What happens when `max_count` is set to `0` or a negative number? The system should reject the request with an HTTP 400 error.
-   **Playlist Not Found**: How does the system handle eine ungültige oder nicht existierende Spotify-Playlist-ID? Es wird ein HTTP 404 Fehler zurückgegeben.
-   **Communication Failure**: Was passiert bei Verbindungsabbruch zu Supabase oder Spotify? Der Prozess wird abgebrochen, ein generischer HTTP 500 Fehler zurückgegeben. **Alle Supabase-Updates müssen atomar erfolgen:** Entweder werden alle betroffenen Einträge gemeinsam aktualisiert (Commit), oder bei Fehlern erfolgt ein vollständiger Rollback. Teilweise Updates sind nicht zulässig.

## Requirements *(mandatory)*
### Non-Functional Requirements
-   Es gibt kein explizites Performance-Limit für die maximale Verarbeitungszeit pro Request.
-   Es werden keine personenbezogenen Daten verarbeitet; besondere Datenschutzanforderungen (z. B. DSGVO) sind nicht relevant.

### Functional Requirements
-   **FR-001**: The system MUST expose a single, unauthenticated HTTP endpoint to trigger the synchronization process.
-   **FR-002**: The system MUST fetch song entries from a Supabase table where the `state` field is empty.
-   **FR-003**: The fetched entries MUST be sorted by the `airtime` field in ascending order.
-   **FR-004**: The system MUST support an optional `max_count` query parameter to limit the number of processed songs.
-   **FR-005**: If `max_count` is not provided, it MUST default to a maximum of 5000 songs.
-   **FR-006**: For each selected entry, the system MUST search for the track on Spotify using its `artist` and `song` fields.
-   **FR-007**: The system MUST add the found Spotify track to a configured target playlist, even if the track is already present.
-   **FR-008**: The system MUST update the `state` of the Supabase entry to "added" upon successful addition.
-   **FR-009**: The system MUST update the `state` to "not_found" if the track cannot be located on Spotify.
-   **FR-010**: The system MUST update the `state` to "error" for any other processing failure related to a specific song.
-   **FR-011**: The system MUST update the `last_changed` timestamp for any entry whose `state` is modified.
-   **FR-012**: The system MUST return an HTTP 200 status with a JSON body listing all successfully added songs if no errors occur.
-   **FR-013**: The system MUST return an HTTP 500 status with a JSON body summarizing all errors if one or more songs fail to process.
-   **FR-014**: The system MUST return an HTTP 400 status for an invalid `max_count` value (<= 0).
-   **FR-015**: The system MUST return an HTTP 404 status if no songs with an empty `state` are found.
-   **FR-016**: The system MUST return an HTTP 404 status if the configured Spotify playlist is not found.
-   **FR-017**: The system MUST return an HTTP 500 status for any unhandled communication errors with external services.
-   **FR-018**: Die Aktualisierung der `state`- und `last_changed`-Felder in der Supabase-Tabelle MUSS atomar für alle verarbeiteten Songs erfolgen (Transaktion). Bei Fehlern dürfen keine teilweisen Updates persistiert werden.

### Key Entities *(include if feature involves data)*
-   **Song Request**: Represents a single song entry from the Supabase database.
    -   **Attributes**: `artist` (text), `song` (text), `airtime` (timestamp, Primärschlüssel), `state` (text, e.g., "added", "not_found", "error"), `last_changed` (timestamp).
## Clarifications
### Session 2025-10-03
- Q: Soll die Aktualisierung der `state`- und `last_changed`-Felder in der Supabase-Tabelle für alle Songs atomar erfolgen (d. h. entweder alle Updates werden übernommen oder keine), oder ist es akzeptabel, dass einzelne Einträge auch bei Fehlern teilweise aktualisiert werden? → A: Atomar: Alle Updates in einer Transaktion, bei Fehler Rollback
- Q: Wie wird die Eindeutigkeit eines Song-Eintrags in der Supabase-Tabelle bestimmt? Gibt es einen eindeutigen Primärschlüssel (z. B. `id`), oder ist die Kombination aus `artist`, `song` und `airtime` eindeutig? → A: `airtime` ist der Primärschlüssel
### Session 2025-10-03
- Q: Soll die Aktualisierung der `state`- und `last_changed`-Felder in der Supabase-Tabelle für alle Songs atomar erfolgen (d. h. entweder alle Updates werden übernommen oder keine), oder ist es akzeptabel, dass einzelne Einträge auch bei Fehlern teilweise aktualisiert werden? → A: Atomar: Alle Updates in einer Transaktion, bei Fehler Rollback

## Review & Acceptance Checklist
*GATE: Automated checks run during main() execution*

### Content Quality
- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

### Requirement Completeness
- [ ] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

---

## Execution Status
*Updated by main() during processing*

- [X] User description parsed
- [X] Key concepts extracted
- [ ] Ambiguities marked
- [X] User scenarios defined
- [X] Requirements generated
- [X] Entities identified
- [ ] Review checklist passed

---