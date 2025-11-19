# Feature Specification: Clear Played Tracks in Playlist

**Feature Branch**: `003-clear-played-tracks`  
**Created**: 2025-11-19
**Status**: Draft  
**Input**: User description: "Ich brauche einen weiteren Endpunkt für die API. Dieser soll alle Titel der Playlist löschen, die vor dem aktuell laufenden Titel sind. Dazu ergibt sich die harte Anforderung, dass dieser Endpunkt nur funktioniert, wenn gerade Musik abgespielt wird. Sonst liefert er zwar einen Rückgabewert, macht aber nichts."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clear Playlist History (Priority: P1)

As a user, I want to remove all tracks from my playlist that have already been played, so that I can easily see what's coming up next without manual cleanup.

**Why this priority**: This is the core functionality of the feature request and provides immediate user value by simplifying playlist management.

**Independent Test**: This can be tested by setting up a playlist, marking a track as "currently playing", and calling the new API endpoint. The expected result is a modified playlist, which can be verified by fetching the playlist state before and after the call.

**Acceptance Scenarios**:

1. **Given** a playlist contains multiple tracks and one track is actively playing, **When** the user triggers the "clear played tracks" action, **Then** all tracks preceding the currently playing track are removed from the playlist.
2. **Given** a playlist contains tracks but no track is currently playing, **When** the user triggers the "clear played tracks" action, **Then** the playlist remains unchanged and the system returns a message indicating that no action was taken.
3. **Given** the currently playing track is the first item in the playlist, **When** the user triggers the "clear played tracks" action, **Then** the playlist remains unchanged.

### Edge Cases

- **Empty Playlist**: What happens when the endpoint is called for an empty playlist? (Expected: No change, specific response)
- **Current Track Not Found**: How does the system handle cases where the "currently playing track" cannot be determined, even if playback is active? (Expected: No change, error response)
- **Simultaneous Modifications**: What happens if the playlist is modified by another process at the same time? (Expected: The operation should be atomic or fail gracefully).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a dedicated API endpoint to remove all tracks from a user's playlist that appear before the currently playing track.
- **FR-002**: The track removal operation MUST only be executed if there is a track actively playing for the user.
- **FR-003**: If no track is actively playing, the endpoint MUST NOT perform any modification on the playlist.
- **FR-004**: The system MUST be able to reliably identify the user's currently playing track to use as a reference for the deletion.
- **FR-005**: Upon successful removal of tracks, the endpoint MUST return a success confirmation.
- **FR-006**: When no track is playing, the endpoint MUST return a `409 Conflict` HTTP status code with a JSON body containing `{"error": "playback_inactive", "message": "Cannot clear tracks when no music is playing."}`.

### Key Entities *(include if feature involves data)*

- **Playlist**: A user-specific, ordered collection of tracks.
- **Track**: A representation of a song, which can be part of a playlist and have a playback status.
- **User Session**: Represents the user's current interaction, including information about active playback.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: When the endpoint is triggered while a track is playing, the preceding tracks are successfully removed from the playlist in over 99% of attempts, with the operation completing within 1.5 seconds.
- **SC-002**: In 100% of cases where no track is playing, triggering the endpoint results in no changes to the user's playlist.
- **SC-003**: The feature correctly identifies the "currently playing" track and its position in the playlist for 99.9% of requests where playback is active.