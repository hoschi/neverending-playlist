# Implementation Plan: Refine Song Addition Status Logic

**Branch**: `001-refine-song-add-status` | **Date**: 2025-11-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-refine-song-add-status/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This feature refines the song addition logic to provide granular status tracking for each song. Instead of a simple boolean success/failure for a batch, the system will now record whether each song was successfully added, not found, or resulted in an error. The implementation will involve updating the data model to store this new status, modifying the service layer to handle individual song processing within a batch, and adjusting the API response to reflect the detailed outcomes.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Pydantic, returns, Loguru, Supabase
**Storage**: Supabase (PostgreSQL)
**Testing**: pytest, mypy, ruff, black
**Target Platform**: Linux server
**Project Type**: Web service
**Performance Goals**: Process batches of up to 100 songs in under 5 seconds.
**Constraints**: The solution must be purely functional within the core, with all side-effects (API calls, DB writes) handled in the imperative shell, adhering to the FCIS principle.
**Scale/Scope**: This change affects the core logic of song processing and the data model for song requests.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Functional Core, Imperative Shell (FCIS)**: Compliant. Logic for determining song status will be in the core. API calls and DB updates are in the shell.
- **II. Strict Typing**: Compliant. All new and modified code will be strictly typed.
- **III. Functional & Immutable by Default**: Compliant. Data structures will be treated as immutable.
- **IV. Railway Oriented Programming for Error Handling**: Compliant. `returns.Result` will be used to handle potential failures in song processing.
- **V. Data Validation at Boundaries**: Compliant. Pydantic models will be used for API request and response validation.
- **VI. Dependency Inversion via Protocols**: Compliant. No new protocols are needed for this feature.
- **VII. Comprehensive and Automated Testing**: Compliant. New logic will be covered by unit and integration tests.
- **VIII. Don't Repeat Yourself (DRY)**: Compliant.
- **IX. Structured and Asynchronous Logging**: Compliant. Loguru will be used for logging errors.

## Project Structure

### Documentation (this feature)

```text
specs/001-refine-song-add-status/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── openapi.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)
```text
src/
├── core/
│   ├── models.py
│   └── services/
│       └── playlist_service.py
└── shell/
    ├── api.py
    └── clients.py

tests/
├── contract/
│   └── test_sync_playlist_post.py
├── integration/
│   └── test_playlist.py
└── unit/
    └── test_services.py
```

**Structure Decision**: The existing single project structure is appropriate and will be maintained.

## Complexity Tracking

No violations of the constitution are anticipated.