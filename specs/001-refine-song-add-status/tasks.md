# Tasks for: Refine Song Addition Status Logic

This document outlines the tasks required to implement the feature.

## Phase 1: Setup

- [ ] T001 Review existing implementation of `sync_playlist` in `src/core/services/playlist_service.py` and `sync_playlist_endpoint` in `src/shell/api.py` to understand the current workflow.

## Phase 2: Foundational Tasks (Data Model)

- [ ] T002 [P] Define the `SongAdditionStatus` enum in `src/core/models.py` with `SUCCESS`, `NOT_FOUND`, and `ERROR` values.
- [ ] T003 [P] Update the `SongRequest` model in `src/core/models.py` to replace the `added: bool` field with `status: SongAdditionStatus`.
- [ ] T004 [P] Create a new Pydantic model `SyncPlaylistResult` in `src/core/models.py` to hold the categorized results: `successful: list[str]`, `not_found: list[str]`, `errors: list[str]`.

## Phase 3: User Story 1: Accurate Song Status Tracking

**Goal**: Accurately track and store the status of each song addition, and reflect this in the API response.
**Independent Test**: The `/sync-playlist` endpoint can be called, and the API response and database state can be verified to correctly reflect the outcome for a batch of songs with mixed validity (successful, not found, error).

- [ ] T005 [US1] Refactor the `add_songs_to_playlist` method in `src/shell/clients.py` to process songs individually and return a detailed result for each song, capturing `SUCCESS`, `NOT_FOUND`, or `ERROR` states.
- [ ] T006 [US1] Refactor the `update_song_requests_as_added` method in `src/shell/clients.py` to accept a list of `SongRequest` objects with their final status and update them in the database.
- [ ] T007 [US1] Refactor the `sync_playlist` service in `src/core/services/playlist_service.py` to orchestrate the calls to the modified client methods and return a `SyncPlaylistResult` object.
- [ ] T008 [US1] Update the `sync_playlist_endpoint` in `src/shell/api.py` to handle the new `SyncPlaylistResult` from the service.
- [ ] T009 [US1] Implement the response logic in `sync_playlist_endpoint` to return a 200 status code with the categorized song lists, or a 400 status code if any songs resulted in an error.
- [ ] T010 [US1] Add structured logging using `loguru` in `sync_playlist_endpoint` to log any songs that have an `ERROR` status at the `ERROR` level.
- [ ] T011 [US1] Create comprehensive unit tests for the refactored `sync_playlist` service in `tests/unit/test_services.py`.
- [ ] T012 [US1] Create integration tests for the `sync_playlist_endpoint` in `tests/integration/test_playlist.py`, covering all scenarios (success, not found, error, and mixed batches).

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T013 Run `poe check-all` to ensure all quality gates (formatting, linting, type checking, testing) pass.
- [ ] T014 [P] Update the project's `README.md` to document the new, detailed API response format for the `/sync-playlist` endpoint.
- [ ] T015 [P] Update the `ai-assistants/current-state.md` file to reflect the changes to the core models and services.

## Dependencies

```mermaid
graph TD
    subgraph Phase 2 (Foundational)
        T002(T002: Define Enum)
        T003(T003: Update SongRequest)
        T004(T004: Create Result Model)
    end

    subgraph Phase 3 (User Story 1)
        T005(T005: Refactor add_songs)
        T006(T006: Refactor update_songs)
        T007(T007: Refactor sync_playlist service)
        T008(T008: Update endpoint)
        T009(T009: Implement response logic)
        T010(T010: Add logging)
        T011(T011: Unit Tests)
        T012(T012: Integration Tests)
    end

    subgraph Phase 4 (Polish)
        T013(T013: Quality Check)
        T014(T014: Update README)
        T015(T015: Update GEMINI.md)
    end

    T001(T001: Review Code) --> T002
    T001 --> T003
    T001 --> T004

    T002 --> T005
    T003 --> T005
    T003 --> T006

    T005 --> T007
    T006 --> T007
    T004 --> T007

    T007 --> T008
    T008 --> T009
    T009 --> T010
    T007 --> T011
    T009 --> T012

    T010 --> T013
    T011 --> T013
    T012 --> T013

    T013 --> T014
    T013 --> T015
```

## Parallel Execution Examples

- **Phase 2**: Tasks T002, T003, and T004 can be executed in parallel as they modify different parts of the same file or are new additions.
- **Phase 3**:
    - T005 and T006 can be worked on in parallel.
    - T011 (Unit Tests) and T012 (Integration Tests) can be developed in parallel once the core service and endpoint signatures are defined.
- **Phase 4**: T014 and T015 (documentation) can be done in parallel.

## Implementation Strategy

The implementation will follow the user story, which represents the Minimum Viable Product (MVP).
1.  First, the foundational data model changes will be implemented.
2.  Next, the core logic in the clients and services will be updated.
3.  The API endpoint will then be modified to expose the new functionality.
4.  Testing will be performed throughout to ensure correctness.
5.  Finally, documentation will be updated and a final quality check will be performed.
This ensures that a complete, testable slice of functionality is delivered.
