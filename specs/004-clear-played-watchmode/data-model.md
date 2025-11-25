# Data Model: Clear Played Watchmode

## CheckerState

This Pydantic model represents the state of the background checker. A single instance of this model will be maintained in memory to track the checker's status.

### Fields

- **`is_running`** (`bool`):
  - `True` if the checker's background task is currently scheduled. `False` otherwise.
- **`retries_left`** (`int`):
  - The number of remaining attempts the checker will make to find an active playback session before stopping itself. Initialized to 5.
- **`last_playback_detected`** (`bool`):
  - `True` if the last check found an active playback session. `False` otherwise. This is used for status reporting.
- **`last_checked`** (`datetime`):
  - The timestamp of when the checker last executed its task.
- **`next_check`** (`datetime`):
  - The timestamp of the next scheduled check.
