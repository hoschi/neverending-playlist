# Implementation Plan: Clear Played Tracks

**Branch**: `003-clear-played-tracks` | **Date**: 2025-11-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-clear-played-tracks/spec.md`

## Summary

This feature introduces a new API endpoint (`POST /clear-played`) to remove tracks from a configured Spotify playlist that have already been played. The implementation will extend the existing FastAPI application, reusing the existing `spotipy` client for all interactions with the Spotify API. The core logic will be implemented as a pure function in the `src/core` layer, adhering to the FCIS pattern, with the API endpoint acting as the imperative shell. Error handling will be managed using `returns.Result` to comply with Railway Oriented Programming principles.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Pydantic, Spotipy, Loguru, returns
**Storage**: N/A (State is managed by Spotify)
**Testing**: pytest, mypy, ruff
**Target Platform**: Linux server (via Docker)
**Project Type**: Web service (FastAPI)
**Performance Goals**: API response time < 1.5 seconds.
**Constraints**: The operation is conditional and only runs if music is actively playing from the specific playlist defined in the environment configuration.
**Scale/Scope**: This is a single endpoint addition to an existing service.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Functional Core, Imperative Shell (FCIS)**: **PASS**. The core logic (determining which tracks to delete) will be a pure function in `src/core/services/playlist_service.py`. The FastAPI endpoint in `src/shell/api.py` will handle the HTTP request/response and call the core function.
- **II. Strict Typing**: **PASS**. All new functions and data models will be strictly typed and validated with `mypy --strict`.
- **III. Functional & Immutable by Default**: **PASS**. New data structures (e.g., response models) will be Pydantic models. Logic will be implemented as free functions. No stateful classes will be introduced.
- **IV. Railway Oriented Programming for Error Handling**: **PASS**. The core service function will return a `Result[Success, Failure]` to handle expected failures (e.g., playback inactive, wrong playlist) explicitly.
- **V. Data Validation at Boundaries**: **PASS**. While there is no request body to validate, the response will be structured using a Pydantic model.
- **VI. Dependency Inversion via Protocols**: **PASS**. No new protocols are needed. The existing `SpotifyClient` will be used directly, as there is only one implementation.
- **VII. Comprehensive and Automated Testing**: **PASS**. Unit tests will be created for the new core service function, and integration tests will be added for the new API endpoint.
- **VIII. Don't Repeat Yourself (DRY)**: **PASS**. The plan reuses the existing Spotify client and configuration setup.
- **IX. Structured and Asynchronous Logging**: **PASS**. `Loguru` will be used for logging any unexpected errors.

## Project Structure

### Documentation (this feature)

```text
specs/003-clear-played-tracks/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── openapi.yaml     # Phase 1 output
└── tasks.md             # Phase 2 output (to be created later)
```

### Source Code (repository root)
```text
src/
├── core/
│   ├── models.py        # Add new response model here
│   └── services/
│       └── playlist_service.py # Add new core logic function here
└── shell/
    └── api.py           # Add new FastAPI endpoint here

tests/
├── integration/
│   └── test_playlist.py # Add new integration test here
└── unit/
    └── test_services.py # Add new unit test here
```

**Structure Decision**: The feature will extend the existing single project structure. New code will be added to the appropriate existing files to maintain cohesion and adhere to the established FCIS pattern.

## Complexity Tracking

No constitutional violations are anticipated.