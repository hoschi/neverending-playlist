# NeverendingSongs Integration Plan

Dieser Plan integriert die NeverendingSongs-Importlogik direkt in Neverending Playlist, ergänzt SQLite als zusätzliche Datenquelle für die Playlist-Synchronisation und liefert einen robusten, täglich ausfallsicheren Import-Job mit klaren, testbaren Commit-Schritten.

## Leitplanken

- Architektur strikt nach FCIS: Geschäftslogik in `src/core`, I/O/DB/API/Scheduling in `src/shell`.
- Strikte Typisierung (`mypy --strict`) und `returns.Result` für erwartbare Fehlerpfade.
- Datenvalidierung an Grenzen mit Pydantic-Modellen.
- `ai-assistants/current-state.md` nach jeder `src/`-Änderung mitpflegen.
- Für schnelle Eigenprüfungen nutze ich kleine Hilfsskripte in `current/`, bevor ich dich um manuelle Tests oder Sichtprüfung bitte.
- Tests **nicht** während der frühen Implementierungsphasen; Testphase als vorletzter Schritt.
- Commits pro testbarem Teilpaket (mittelgranular, weder mikro noch zu grob).

## Umsetzungsphasen mit Commit-Gates

1. **Ist-Zustand + Domänenmodell + Basis-Konfiguration**
   - `current/songs_last_20min_sample.json` mit realen Treffern (20-Minuten-Fenster) stabilisieren.
   - Mapping der alten n8n-Logik als dokumentierte Feldpfade erfassen (Input -> Zielschema).
   - Neue Core-Modelle für Import-Records, Source-Config, Mapping-Config (jq-Syntax), Job-Status.
   - Settings erweitern: Datenquellenwahl (`SUPABASE|SQLITE`), SQLite-Pfad im Repo-Root, SQLite-Maxgröße (z. B. 10GB), Notification-Flag.
   - Für Importquellen nur eine konfigurierbare URL-Liste (mehrere Quellen möglich), ohne Defaults im Code.
   - `source` wird nicht konfiguriert, sondern aus der Domain der jeweiligen URL abgeleitet.
   - Festes SQLite-Schema definieren (Supabase-kompatibel + Importmetadaten wie `airtime`, `source`).
   - `implementation.md` anlegen (Zielbild, Constraints, erstes Mermaid-Diagramm).
   - **Testbar:** Referenz-JSON + Mapping-Design vorhanden, App startet mit neuen Env-Defaults, Konfiguration lädt korrekt.
   - **Commit 1**

2. **NeverendingSongs-Ingest (REST -> Mapping -> SQLite)**
   - Shell-Adapter für REST-Quellen (zunächst Radio Bob), Zeitfenster bis zum Schluss auf 20 Minuten.
   - jq-basiertes Mapping (CLI oder Library) implementieren, gegen Referenzdatei validieren.
   - SQLite-Writer + Upsert/Insert-Strategie implementieren.
   - Datei-Größen-Guard: Job-Abbruch bei Überschreitung des Limits (Result-Fehler statt Crash).
   - **Testbar:** Manueller Importlauf schreibt gemappte Daten in SQLite; Guard verhält sich korrekt.
   - **Commit 2**

3. **Playlist-Datenquelle konfigurierbar machen (Supabase + SQLite)**
   - Core-Protokoll/Abstraktion für SongRequest-Quelle sauber erweitern (nur wo mehrere Implementierungen wirklich nötig sind).
   - Supabase-Pfad beibehalten, SQLite-Implementierung als alternative Quelle ergänzen.
   - `sync_playlist` auf konfigurierbare Quelle umstellen, bestehendes Verhalten kompatibel halten.
   - **Testbar:** `POST /sync-playlist` funktioniert mit beiden Quellen (umschaltbar per Env).
   - **Commit 3**

4. **Scheduler: täglich 02:00 + stündlicher Catch-up**
   - Integrierten Background-Scheduler in der FastAPI-App ergänzen (kein externer Cron nötig).
   - Jede Stunde prüfen, ob der Tageslauf bereits erfolgt ist; bei verpasstem 02:00-Lauf nachholen.
   - Persistenz des letzten erfolgreichen Laufs in SQLite (oder dedizierter State-Tabelle) für reboot-sicheren Catch-up.
   - Logging vollständig über bestehendes Loguru-Interface.
   - **Testbar:** Scheduler-Logik über kontrollierte Zeitpunkte nachvollziehbar; Nachhol-Run wird ausgelöst.
   - **Commit 4**

5. **macOS-Fehlerbenachrichtigung (optional per Env)**
   - Bei Server-/Job-Fehlern optional `osascript`-Benachrichtigung senden (`Neverending Playlist` als Titel).
   - Nachricht enthält klaren Fehlerzeitpunkt.
   - Feature vollständig deaktivierbar über Env (portable für andere OS).
   - **Testbar:** Erzwungener Fehler erzeugt Notification bei aktiviertem Flag, sonst nicht.
   - **Commit 5**

6. **Dokumentation vervollständigen (Implementation + README + env example)**
   - `implementation.md` finalisieren (Ablaufbeschreibung + Mermaid-Diagramme für Ingest, Scheduler, Datenquellenwahl).
   - `README.md` auf neue Architektur und Betriebsweise aktualisieren.
   - `.env.example` um NeverendingSongs-/SQLite-/Scheduler-/Notification-Konfiguration erweitern (inkl. REST-Source + jq-Mapping-Beispiel).
   - `ai-assistants/current-state.md` vollständig aktualisieren.
   - **Testbar:** Doku bildet tatsächliches Verhalten ab, Setup ist reproduzierbar.
   - **Commit 6**

7. **Tests (vorletzter Implementierungsschritt) + finaler Qualitätslauf**
   - Erst jetzt Tests ergänzen/aktualisieren (Unit + Integration für neue Core-/Shell-Teile).
   - Danach vollständiger Qualitätslauf (`poe check-all`) und gezielte Fehlerkorrekturen.
   - **Testbar:** Alle neuen Tests grün, bestehende Tests grün, Type/Lint grün.
   - **Commit 7 (vorletzter Schritt gemäß Wunsch)**

8. **Finaler Abschluss-Commit**
   - Letzte kleine Doku-/Konsistenzanpassungen nach Testergebnis.
   - Abschließender, sauberer Integrations-Commit.

## Geplante Implementierungsartefakte

- Neue/erweiterte Core-Modelle und Service-Funktionen für NeverendingSongs-Ingest.
- SQLite-Anbindung und festes Schema für gemeinsame Nutzung zwischen Ingest und Playlist-Sync.
- Umschaltbare Datenquelle für Playlist-Sync (`SUPABASE|SQLITE`).
- In-App Scheduler mit 02:00-Run + stündlichem Catch-up.
- Optionale macOS-Notifications bei Fehlern.
- Aktualisierte Doku: `implementation.md`, `README.md`, `.env.example`, `ai-assistants/current-state.md`.
