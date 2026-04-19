# Tasks for Feature: Clear Played Watchmode

This document outlines the implementation tasks for the "Clear Played Watchmode" feature, organized by user story.

## Phase 1: Setup

- [ ] T001 Add `apscheduler` to project dependencies in `pyproject.toml`
- [ ] T002 Create new file for the checker logic in `src/shell/checker.py`
- [ ] T003 Create new file for the in-memory state management in `src/shell/state.py`

## Phase 2: Foundational Tasks

- [ ] T004 Define the `CheckerState` Pydantic model in `src/core/models.py`
- [ ] T005 [P] Implement the in-memory singleton state manager in `src/shell/state.py` to hold and provide access to the `CheckerState` instance.

## Phase 3: User Story 1 - Activate Watchmode

**Goal**: Implement the endpoint to activate or check the status of the watchmode.
**Independent Test**: Call the `GET /clear-played-watchmode` endpoint. If playback is active, a background job is scheduled and confirmed. If called again, it returns the current status of the job.

- [ ] T006 [US1] Create the placeholder for the background task function in `src/shell/checker.py`
- [ ] T007 [US1] Configure `apscheduler.AsyncIOScheduler` in `src/shell/api.py` to start and shut down with the FastAPI application's lifespan.
- [ ] T008 [US1] Implement the `GET /clear-played-watchmode` endpoint in `src/shell/api.py`
- [ ] T009 [US1] In the endpoint, add logic to access the singleton state from `src/shell/state.py` to check if the checker is already running.
- [ ] T010 [US1] In the endpoint, add logic to check for active Spotify playback.
- [ ] T011 [US1] In the endpoint, add logic to schedule the background task from `src/shell/checker.py` using `apscheduler` if the checker is not already running and playback is active.
- [ ] T012 [US1] In the endpoint, implement the logic to return the correct JSON responses (`checker_installed` or `checker_running` with state) based on the outcome.

## Phase 4: User Story 2 - Automatic Playlist Clearing Trigger

**Goal**: The scheduled task correctly triggers the existing clearing logic, handles retries, and manages its own lifecycle.
**Independent Test**: With watchmode active, play a song from the monitored playlist, wait for the 10-minute interval, and verify that the played track has been removed by the existing `/clear-played` logic.

- [ ] T013 [US2] In `src/shell/checker.py`, implement the core logic of the background task to call the existing `clear_played_tracks_from_playlist` service.
- [ ] T014 [US2] In the background task, implement the retry mechanism: if no playback is detected, decrement the `retries_left` counter in the shared state.
- [ ] T015 [US2] In the background task, implement the logic to reset the `retries_left` counter to its default value whenever playback is successfully detected.
- [ ] T016 [US2] In the background task, implement the logic to stop/remove the scheduled job from `apscheduler` if the `retries_left` counter reaches zero.
- [ ] T017 [US2] Ensure all interactions with the shared state object are thread-safe (using locks if necessary, though `asyncio` reduces this risk).
- [ ] T018 [US2] In the background task, add error handling for network errors or token expiration when calling the clear logic, and log these errors appropriately.
- [ ] T019 [US2] In the background task, handle non-2xx responses from the `/clear-played` logic and factor this into the retry mechanism.

## Phase 5: Polish & Cross-Cutting Concerns

- [ ] T020 [P] Add structured logging using `Loguru` to the checker process in `src/shell/checker.py` to report on job execution, success, and failures.
- [ ] T021 [P] Write comprehensive docstrings for all new functions and modules (`checker.py`, `state.py`).
- [ ] T022 Write unit tests for the checker's retry and state-change logic in `tests/unit/shell/test_checker.py`.
- [ ] T023 Write integration tests for the `GET /clear-played-watchmode` endpoint in `tests/integration/test_playlist.py`, covering all response scenarios.

## Dependencies

- **User Story 1** is a prerequisite for **User Story 2**. The endpoint must be able to schedule the task before the task's internal logic can be tested.

## Parallel Execution

- Within **Phase 3 (US1)**, tasks T008-T012 are sequential as they build upon each other within the same endpoint function.
- Within **Phase 4 (US2)**, tasks T013-T017 are also sequential as they are part of the same background task logic.
- **Phase 5** tasks (Logging, Docs, Tests) can be worked on in parallel with the implementation phases once the relevant modules are created.

## Implementation Strategy

The implementation will follow the user stories in order. The MVP (Minimum Viable Product) consists of completing all tasks for **User Story 1**, which will provide the core functionality of activating the watchmode. **User Story 2** completes the feature by making the background task robust and self-managing.
