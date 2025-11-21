# Data Model: Clear Played Tracks

This document defines the data structures required for the "Clear Played Tracks" feature.

## New Data Models

### `ClearPlayedTracksResponse`

This model represents the successful response body for the new endpoint. It will be defined in `src/core/models.py`.

**Purpose**: To provide a clear, structured confirmation to the client after tracks have been successfully removed.

**Fields**:

| Field Name        | Type      | Description                               | Example |
|-------------------|-----------|-------------------------------------------|---------|
| `deleted_count`   | `int`     | The number of tracks removed from the playlist. | `5`       |

**Pydantic Definition**:

```python
from pydantic import BaseModel, Field

class ClearPlayedTracksResponse(BaseModel):
    """Response model for the clear played tracks endpoint."""
    deleted_count: int = Field(
        ...,
        description="The number of tracks successfully deleted from the playlist.",
        example=5,
    )
```

### `ErrorDetail`

This model represents the structured error response used for expected failures (e.g., playback inactive). It will be reused if not already present, or defined in `src/core/models.py`.

**Purpose**: To provide a consistent error format for clients.

**Fields**:

| Field Name  | Type     | Description                               | Example                               |
|-------------|----------|-------------------------------------------|---------------------------------------|
| `error`     | `str`    | A unique code for the error type.         | `"playback_inactive"`                 |
| `message`   | `str`    | A human-readable description of the error. | `"Cannot clear tracks when no music is playing."` |

**Pydantic Definition**:

```python
from pydantic import BaseModel, Field

class ErrorDetail(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="A unique code for the error type.")
    message: str = Field(..., description="A human-readable description of the error.")
```
