# Implementation Plan: Authorization Code Flow

**Branch**: `002-feature-request-authorization` | **Date**: 2025-10-07 | **Spec**: [./spec.md](./spec.md)
**Input**: Feature specification from `/Users/hoschi/repos/supabase-to-spotify/specs/002-feature-request-authorization/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code or `AGENTS.md` for opencode).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary
The feature requires implementing the OAuth 2.0 Authorization Code Flow to allow the application to act on behalf of a user. This will replace the existing Client Credentials Flow. The technical approach is to use the `spotipy` library with its `SpotifyOAuth` helper, adding web endpoints to handle the authorization redirect and callback. The refresh token will be stored securely in the `.env` file after being encrypted.

## Technical Context
**Language/Version**: Python 3.12
**Primary Dependencies**: FastAPI, Spotipy, Pydantic, returns, Loguru
**Storage**: `.env` file for the encrypted refresh token.
**Testing**: pytest
**Target Platform**: Linux server (or any OS capable of running Python)
**Project Type**: Web Service (Backend)
**Performance Goals**: The authorization flow is user-interactive, so callbacks should complete within a reasonable time (e.g., <2 seconds).
**Constraints**: Must securely handle and store the refresh token.
**Scale/Scope**: Single-user authorization model for this application.

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Functional Core, Imperative Shell (FCIS)**: Adhered to. Authorization logic will be in the `shell`, while any core logic remains pure.
- **Strict Typing**: Adhered to. All new code will be strictly typed.
- **Functional & Immutable by Default**: Adhered to.
- **Railway Oriented Programming**: Adhered to for error handling in the callback.
- **Data Validation at Boundaries**: Adhered to. The callback will validate the incoming query parameters.
- **Dependency Inversion via Protocols**: Not required for this feature.
- **Comprehensive and Automated Testing**: Adhered to. New endpoints and logic will be tested.
- **Don't Repeat Yourself (DRY)**: Adhered to.
- **Structured and Asynchronous Logging**: Adhered to for logging authorization events.

## Project Structure

### Documentation (this feature)
```
specs/002-feature-request-authorization/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
src/
├── core/
│   ├── config.py
│   └── services/
│       └── encryption_service.py
└── shell/
    ├── api.py
    └── clients.py

tests/
├── contract/
├── integration/
└── unit/
```

**Structure Decision**: The project is a single web service. New logic will be added to the existing `src/core` and `src/shell` directories as appropriate, following the established FCIS architecture.

## Phase 0: Outline & Research
1. **Extract unknowns from Technical Context**: Completed. No unknowns remain.
2. **Generate and dispatch research agents**: Completed.
3. **Consolidate findings** in `research.md`: Completed.

**Output**: `research.md` with all NEEDS CLARIFICATION resolved.

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`: Completed.
2. **Generate API contracts**: No new OpenAPI contracts are needed as the interaction is a browser-based redirect flow. The "contracts" are the `/login` and `/callback` endpoints.
3. **Generate contract tests**: Not applicable in the traditional sense. Integration tests will serve to validate the endpoint behavior.
4. **Extract test scenarios** from user stories → `quickstart.md`: Completed.
5. **Update agent file incrementally**: Skipped as per instructions.

**Output**: `data-model.md`, `quickstart.md`.

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- The `tasks.md` file has been generated based on the design artifacts. The strategy involves setting up configuration, creating the authorization endpoints, refactoring the Spotify client to use the new auth flow, and writing corresponding tests for each component.

**Ordering Strategy**:
- The tasks are ordered to follow a logical implementation sequence: configuration first, then endpoints, then client logic, followed by integration and documentation. TDD is encouraged within each phase.

**Estimated Output**: A `tasks.md` file with approximately 15 tasks.

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)
**Phase 4**: Implementation (execute tasks.md following constitutional principles)
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A       | N/A        | N/A                                 |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented

---
*Based on Constitution v1.0.1 - See `/.specify/memory/constitution.md`*