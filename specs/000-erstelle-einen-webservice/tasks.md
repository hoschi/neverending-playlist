# Tasks: Supabase-Spotify Playlist Bridge

**Input**: Design-Dokumente aus `/specs/001-erstelle-einen-webservice/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/

## Phase 3.1: Setup
- [ ] T001 Projektstruktur gemäß plan.md anlegen (`src/`, `tests/`, etc.)
- [ ] T002 Python-Projekt initialisieren und poetry-Abhängigkeiten laut research.md installieren
- [ ] T003 [P] Linting und Formatierung (z.B. ruff, black) konfigurieren
- [ ] T004 [P] .env.example bereitstellen und Umgebungsvariablen dokumentieren

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
- [ ] T005 [P] Contract-Test für POST /sync-playlist in `tests/contract/test_sync_playlist_post.py`
- [ ] T006 [P] Integrationstest für Quickstart-Workflow in `tests/integration/test_quickstart.py`
- [ ] T007 [P] Property-based Test für SongRequest-Validierung in `tests/unit/test_songrequest_validation.py`


## Phase 3.3: Core Implementation (nur nach fehlschlagenden Tests)
- [ ] T008 [P] SongRequest-Modell in `src/core/models.py` als reine Datenstruktur (keine Methoden, außer ggf. `__post_init__`) implementieren
- [ ] T009 [P] Define pure function signatures (with type hints) for Supabase and Spotify interactions in `src/core/services.py` (no Protocols, only functions and type annotations, as only one implementation is required)
- [ ] T010 [P] Implement explicit test doubles (mock functions) for Supabase and Spotify interactions in the respective test files (`tests/unit/test_services.py`), without using Protocols
- [ ] T011 [P] Freie Funktion `fetch_pending_song_requests` in `src/core/services.py` implementieren
- [ ] T012 [P] Freie Funktion `add_song_to_spotify` in `src/core/services.py` implementieren
- [ ] T013 [P] Fehlerbehandlung mit `returns.Result` in allen freien Service-Funktionen sicherstellen
- [ ] T014 [P] Logging mit Loguru in `src/shell/logging_config.py` (nur in Shell, nicht im Core)


## Phase 3.4: API & Integration
- [ ] T015 FastAPI-Endpoint POST /sync-playlist in `src/shell/api.py` implementieren
- [ ] T016 Query-Parameter-Validierung (max_count) mit Pydantic
- [ ] T017 Integration aller Services im Endpoint (Supabase → Spotify)
- [ ] T018 Fehler- und Erfolgsantworten gemäß OpenAPI-Schema
- [ ] T019 Atomare Transaktionslogik für Updates in Supabase implementieren (alle Updates in einer Transaktion, Rollback bei Fehlern, FR-018)
- [ ] T020 Test für atomare Transaktion: Simuliere Fehler und prüfe, dass keine teilweisen Updates persistiert werden (Unit- oder Integrationstest)


## Phase 3.5: Polish
- [ ] T021 [P] Unit-Tests für alle Services in `tests/unit/test_services.py`
- [ ] T022 [P] (Optional) Performance-Test für Endpunkt in `tests/performance/test_sync_playlist.py` (nur falls Performance-Ziel nachträglich spezifiziert wird)
- [ ] T023 [P] Dokumentation aktualisieren (`README.md`, `quickstart.md`)
- [ ] T024 [P] 100% Testabdeckung prüfen und ggf. fehlende Tests ergänzen

## Abhängigkeiten & Parallelisierung
- Setup (T001–T004) vor allen anderen Tasks
- Tests (T005–T007) müssen fehlschlagen, bevor Implementierung beginnt
- Modell (T008–T010) vor Service-Implementierungen (T011–T012)
- Services vor API-Integration (T015–T018)
- Polish-Tasks (T019–T022) können parallel nach Implementierung erfolgen
- [P] = Kann parallel ausgeführt werden (unabhängige Dateien)

## Parallel Execution Example
```
# Starte alle [P]-Tasks in Phase 3.2 parallel:
Task: "Contract-Test für POST /sync-playlist in tests/contract/test_sync_playlist_post.py"
Task: "Integrationstest für Quickstart-Workflow in tests/integration/test_quickstart.py"
Task: "Property-based Test für SongRequest-Validierung in tests/unit/test_songrequest_validation.py"
```

## Hinweise
- Jeder Task enthält einen klaren Dateipfad
- Keine [P]-Tasks dürfen dieselbe Datei gleichzeitig bearbeiten
- Nach jedem Task committen
- Tests müssen vor Implementierung fehlschlagen (TDD)
- Polish-Phase für finale Qualitätssicherung
