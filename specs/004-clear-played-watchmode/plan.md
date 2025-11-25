# Implementation Plan: Clear Played Watchmode

**Feature Branch**: `001-clear-played-watchmode`
**Feature Spec**: [spec.md](spec.md)

## 1. Technical Context & Dependencies

### Existing System
- **Framework**: FastAPI
- **Architecture**: Functional Core, Imperative Shell (FCIS)
- **Error Handling**: `returns.Result` monad
- **Existing Logic**: The core logic for clearing tracks already exists in a function called by the `POST /clear-played` endpoint. This new feature will act as an automated orchestrator for this existing logic.

### New Dependencies
- **Background Task Scheduling**: A library is needed to manage the recurring 10-minute task.
- **State Management**: A mechanism is required to store the state of the running checker (e.g., is it active, retry count, last status).

### Technical Unknowns & Risks
- **Background Task Management**: How to best implement a long-running, stateful background task in FastAPI without tightly coupling it to the web server process. The solution must be robust to server restarts.
- **State Storage**: Where to store the checker's state. An in-memory solution is simple but volatile and won't work with multiple server workers or survive restarts. A persistent solution (like a database or Redis) is more robust but adds complexity.
- **Concurrency**: Ensuring that only one checker instance runs per user. The current spec mentions "per user/playlist combination," but the new user input simplifies this to just "a checker," implying a single, global checker. This needs to be confirmed, but we will assume a single global checker for now.

## 2. Constitution Check & Gate Evaluation

### Gate Evaluation
- **FCIS**: The solution must keep the scheduling and state management logic (imperative shell) separate from the core business logic (which is already implemented). The new endpoint and the background task runner belong in `src/shell`.
- **Strict Typing**: All new components must be strictly typed.
- **Functional & Immutable**: The checker's state must be managed immutably. When the state changes (e.g., retry count decreases), a new state object should be created rather than mutating an existing one.
- **Railway Oriented Programming**: The background task must handle potential failures from the `/clear-played` logic gracefully, using `Result` to wrap outcomes.

**Result**: Proceed. The plan is compatible with the constitution, but careful design is needed for state management.

## 3. Phase 0: Outline & Research

### Research Tasks
1.  **Task**: Research and select the best library for managing recurring background tasks in a FastAPI application.
    - **Candidates**: `apscheduler`, `arq`, `celery`.
    - **Criteria**: Simplicity, reliability, ease of integration with FastAPI, and support for managing job state.
2.  **Task**: Determine the best approach for persisting the checker's state.
    - **Candidates**: In-memory singleton (for simplicity, but with noted drawbacks), a new Supabase table, or a Redis cache.
    - **Criteria**: Persistence, scalability (handling multiple workers), and low implementation overhead.

**Output**: A `research.md` file will be created to document the decisions.

## 4. Phase 1: Design & Contracts

### Data Model (`data-model.md`)
- A Pydantic model, `CheckerState`, will be defined to represent the state of the background task.
  - `is_running: bool`
  - `retries_left: int`
  - `last_playback_detected: bool`
  - `last_checked: datetime`
  - `next_check: datetime`

### API Contracts (`contracts/openapi.yaml`)
- **Endpoint**: `GET /clear-played-watchmode`
- **Success Response (200 OK)**:
  - If checker is newly installed: `{ "status": "checker_installed" }`
  - If checker is already running: `{ "status": "checker_running", "state": CheckerState }`
- **Error Response (400 Bad Request)**:
  - If no active playback is found on the initial call: `{ "detail": "No active playback detected. Checker not started." }`

### Quickstart Guide (`quickstart.md`)
- Instructions on how to use the new `GET /clear-played-watchmode` endpoint with `curl`.
- Explanation of the different status responses.

### Agent Context Update
- The chosen scheduling library (e.g., `apscheduler`) will be added to the agent's context file.

## 5. Phase 2: Implementation & Testing (High-Level Plan)

### Implementation Tasks
1.  **Task**: Integrate the chosen scheduling library into the FastAPI application lifecycle (startup/shutdown events).
2.  **Task**: Implement the state management service to handle the `CheckerState` (e.g., `get_checker_state`, `update_checker_state`).
3.  **Task**: Create the background job function that:
    - Fetches the current `CheckerState`.
    - Calls the existing `clear_played_tracks_from_playlist` logic.
    - Handles success: resets the retry counter.
    - Handles playback-not-found errors: decrements the retry counter.
    - Stops the job if retries are exhausted.
    - Updates the `CheckerState`.
4.  **Task**: Implement the `GET /clear-played-watchmode` endpoint that:
    - Checks for active playback.
    - Checks if a checker is already running by querying the state.
    - Starts a new checker job if not running.
    - Returns the appropriate status response.

### Testing Strategy
- **Unit Tests**:
  - Test the state management functions in isolation.
  - Test the logic of the background job function with mocked dependencies.
- **Integration Tests**:
  - Test the API endpoint's behavior under different conditions (e.g., playback active/inactive, checker already running).
  - Test the interaction between the endpoint, the scheduler, and the state management service.