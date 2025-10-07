# Tasks: Authorization Code Flow

**Input**: Design documents from `/specs/002-feature-request-authorization/`
**Prerequisites**: plan.md (required), research.md, data-model.md, quickstart.md

## Execution Flow (main)
```
1. Load plan.md from feature directory
   → If not found: ERROR "No implementation plan found"
   → Extract: tech stack, libraries, structure
2. Load optional design documents:
   → data-model.md: Extract entities → model tasks
   → contracts/: Each file → contract test task
   → research.md: Extract decisions → setup tasks
3. Generate tasks by category:
   → Setup: project init, dependencies, linting
   → Tests: contract tests, integration tests
   → Core: models, services, CLI commands
   → Integration: DB, middleware, logging
   → Polish: unit tests, performance, docs
4. Apply task rules:
   → Different files = mark [P] for parallel
   → Same file = sequential (no [P])
   → Tests before implementation (TDD)
5. Number tasks sequentially (T001, T002...)
6. Generate dependency graph
7. Create parallel execution examples
8. Validate task completeness:
   → All contracts have tests?
   → All entities have models?
   → All endpoints implemented?
9. Return: SUCCESS (tasks ready for execution)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/`, `tests/` at repository root
- **Web app**: `backend/src/`, `frontend/src/`
- **Mobile**: `api/src/`, `ios/src/` or `android/src/`
- Paths shown below assume single project - adjust based on plan.md structure

## Phase 3.1: Setup
- [ ] T001 Update `core/config.py` to include `SPOTIPY_CLIENT_ID`, `SPOTIPY_CLIENT_SECRET`, `SPOTIPY_REDIRECT_URI`, and `ENCRYPTION_KEY`.
- [ ] T002 Add the new environment variables to `.env.example`.

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3
**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**
- [ ] T003 [P] Create integration test for `GET /login` in `tests/integration/test_auth.py` to verify it redirects to the Spotify authorization URL.
- [ ] T004 [P] Create integration test for `GET /callback` in `tests/integration/test_auth.py` to verify it handles the callback, exchanges the code for tokens, and stores the encrypted refresh token.
- [ ] T005 [P] Create unit test for the `EncryptionService` in `tests/unit/test_encryption_service.py`.

## Phase 3.3: Core Implementation (ONLY after tests are failing)
- [ ] T006 [P] Create `UserAuthorization` Pydantic model in `src/core/models.py`.
- [ ] T007 [P] Implement `EncryptionService` in `src/core/services/encryption_service.py` for encrypting and decrypting the refresh token.
- [ ] T008 Implement `GET /login` endpoint in `src/shell/api.py` to initiate the Spotify OAuth flow.
- [ ] T009 Implement `GET /callback` endpoint in `src/shell/api.py` to handle the redirect from Spotify, store the refresh token, and return a success message.
- [ ] T010 Refactor `SpotifyClient` in `src/shell/clients.py` to use `spotipy.SpotifyOAuth` and handle token caching and refreshing.

## Phase 3.4: Integration
- [ ] T011 Integrate `EncryptionService` into the `GET /callback` endpoint to encrypt the refresh token before storing it.
- [ ] T012 Update services that use `SpotifyClient` to ensure they work with the new authentication mechanism.

## Phase 3.5: Polish
- [ ] T013 [P] Add comprehensive docstrings and type hints to all new functions and classes.
- [ ] T014 [P] Update `README.md` with instructions on how to configure and use the new authorization flow.
- [ ] T015 Run all tests and ensure they pass.

## Dependencies
- T001, T002 must be done before all other tasks.
- Tests (T003-T005) before implementation (T006-T010).
- T006 blocks T009.
- T007 blocks T011.
- T010 blocks T012.
- Implementation (T006-T010) before integration (T011-T012).
- Integration (T011-T012) before polish (T013-T015).

## Parallel Example
```
# Launch T003-T005 together:
Task: "Create integration test for GET /login in tests/integration/test_auth.py"
Task: "Create integration test for GET /callback in tests/integration/test_auth.py"
Task: "Create unit test for the EncryptionService in tests/unit/test_encryption_service.py"
```

## Notes
- [P] tasks = different files, no dependencies
- Verify tests fail before implementing
- Commit after each task
- Avoid: vague tasks, same file conflicts

## Task Generation Rules
*Applied during main() execution*

1. **From Contracts**:
   - Each contract file → contract test task [P]
   - Each endpoint → implementation task
   
2. **From Data Model**:
   - Each entity → model creation task [P]
   - Relationships → service layer tasks
   
3. **From User Stories**:
   - Each story → integration test [P]
   - Quickstart scenarios → validation tasks

4. **Ordering**:
   - Setup → Tests → Models → Services → Endpoints → Polish
   - Dependencies block parallel execution

## Validation Checklist
*GATE: Checked by main() before returning*

- [ ] All contracts have corresponding tests
- [ ] All entities have model tasks
- [ ] All tests come before implementation
- [ ] Parallel tasks truly independent
- [ ] Each task specifies exact file path
- [ ] No task modifies same file as another [P] task