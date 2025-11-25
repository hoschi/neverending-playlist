# Feature Specification: Clear Played Watchmode

**Feature Branch**: `001-clear-played-watchmode`
**Created**: 2025-11-21
**Status**: Draft
**Input**: User description: "ein weiterer endpunkt `clear-played-watchmode` soll hinzugefügt werden. Dieser installiert einen "Checker" der das aktive playback überwacht und alle 10 min immer wieder automatisch die playlist cleared."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Activate Watchmode (Priority: P1)

As a user, I want to activate a "watchmode" for a specific playlist so that the system automatically triggers the existing playlist clearing functionality, keeping the playlist fresh without manual intervention.

**Why this priority**: This is the core functionality of the feature request and delivers the primary user value by automating an existing process.

**Independent Test**: Can be tested by calling the new endpoint for a playlist and observing that a recurring monitoring process is initiated for that playlist, which subsequently calls the `/clear-played` endpoint.

**Acceptance Scenarios**:

1. **Given** a user has authenticated and has a playlist, **When** they call the `clear-played-watchmode` endpoint for that playlist, **Then** the system starts a background process to periodically trigger the `/clear-played` endpoint for that playlist.
2. **Given** the watchmode is already active for a playlist, **When** the user calls the endpoint again for the same playlist, **Then** the system informs the user that watchmode is already active and does not start a duplicate process.

---

### User Story 2 - Automatic Playlist Clearing Trigger (Priority: P1)

As a user with watchmode active, I expect the system to automatically trigger the existing `/clear-played` functionality every 10 minutes, removing tracks that have been played.

**Why this priority**: This describes the ongoing, automated value of the feature, leveraging existing functionality.

**Independent Test**: Can be tested by playing a song from the monitored playlist, waiting for the 10-minute interval, and verifying that the `/clear-played` endpoint is called and the played track is removed.

**Acceptance Scenarios**:

1. **Given** watchmode is active for a playlist, **When** 10 minutes pass, **Then** the system automatically calls the `/clear-played` endpoint for that playlist.
2. **Given** watchmode is active, **When** the 10-minute trigger runs and the `/clear-played` endpoint is called, **Then** the playlist is updated according to the logic of the `/clear-played` endpoint.

---

### Edge Cases

- What happens if the user's authentication token expires while watchmode is active, preventing calls to `/clear-played`?
- How does the system handle network errors when trying to trigger the `/clear-played` endpoint?
- What happens if the playlist is deleted while watchmode is active?
- What if the `/clear-played` endpoint returns an error during an automated trigger?

### Assumptions

- Users have a way to authenticate with the service to use this feature.
- The existing `/clear-played` endpoint correctly identifies and removes played tracks based on its internal logic.
- The user wants the checker to run indefinitely until explicitly stopped (functionality for stopping is out of scope for this feature).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a new endpoint, `clear-played-watchmode`.
- **FR-002**: This endpoint MUST initiate a global background monitoring process ("Checker") that acts only on the playlist specified in the `.env` file.
- **FR-003**: The monitoring process MUST run automatically at a regular interval of 10 minutes.
- **FR-004**: During each interval, the monitoring process MUST trigger the existing `/clear-played` endpoint for the specified playlist.
- **FR-005**: The system MUST ensure that only one monitoring process is active per user/playlist combination to prevent duplication.
- **FR-006**: The watchmode MUST trigger the `/clear-played` endpoint, which is responsible for removing all tracks in the playlist that appear before the currently playing song.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When watchmode is active, the `/clear-played` endpoint is successfully triggered every 10 minutes (± 1 minute).
- **SC-003**: The watchmode feature results in a 99% success rate for automatically triggering the `/clear-played` endpoint under normal operating conditions.
