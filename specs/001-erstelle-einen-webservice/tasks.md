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
- [ ] T008 [P] SongRequest-Modell in `src/core/models.py` implementieren
- [ ] T009 [P] SupabaseService-Protokoll in `src/core/protocols.py` definieren
- [ ] T010 [P] SpotifyService-Protokoll in `src/core/protocols.py` definieren
- [ ] T011 [P] Service-Implementierung für Supabase in `src/core/services.py`
- [ ] T012 [P] Service-Implementierung für Spotify in `src/core/services.py`
- [ ] T013 [P] Fehlerbehandlung mit returns.Result in allen Services
- [ ] T014 [P] Logging mit Loguru in `src/shell/logging_config.py`

## Phase 3.4: API & Integration
- [ ] T015 FastAPI-Endpoint POST /sync-playlist in `src/shell/api.py` implementieren
- [ ] T016 Query-Parameter-Validierung (max_count) mit Pydantic
- [ ] T017 Integration aller Services im Endpoint (Supabase → Spotify)
- [ ] T018 Fehler- und Erfolgsantworten gemäß OpenAPI-Schema

## Phase 3.5: Polish
- [ ] T019 [P] Unit-Tests für alle Services in `tests/unit/test_services.py`
- [ ] T020 [P] Performance-Test für Endpunkt (<200ms p95) in `tests/performance/test_sync_playlist.py`
- [ ] T021 [P] Dokumentation aktualisieren (`README.md`, `quickstart.md`)
- [ ] T022 [P] 100% Testabdeckung prüfen und ggf. fehlende Tests ergänzen

## Abhängigkeiten & Parallelisierung
- Setup (T001–T004) vor allen anderen Tasks
- Tests (T005–T007) müssen fehlschlagen, bevor Implementierung beginnt
- Modell/Protokolle (T008–T010) vor Service-Implementierungen (T011–T012)
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
