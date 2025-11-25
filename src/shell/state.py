"""In-Memory State Management for Watchmode Checker.

This module provides singleton-based state management for the background
watchmode checker, ensuring thread-safe access to checker state across
the application in asyncio environments.
"""

import asyncio
from datetime import datetime

from pydantic import BaseModel


class CheckerState(BaseModel):
    """Represents the state of the background checker.

    This Pydantic model tracks the status of the watchmode background task,
    including retry counts, playback detection status, and scheduling information.
    """

    is_running: bool = False
    retries_left: int = 5
    last_playback_detected: bool = False
    last_checked: datetime | None = None
    next_check: datetime | None = None


# Global state instance and lock for thread-safe asyncio operations
_global_state: CheckerState | None = None
_state_lock = asyncio.Lock()


async def get_checker_state() -> CheckerState:
    """Get the global checker state instance.

    This function provides thread-safe access to the global checker state
    in asyncio environments using asyncio.Lock for synchronization.

    Returns:
        CheckerState: The global checker state instance
    """
    global _global_state

    async with _state_lock:
        if _global_state is None:
            _global_state = CheckerState()

        return _global_state


async def reset_checker_state() -> CheckerState:
    """Reset the global checker state to initial values.

    This function is useful for testing or when the state needs to be
    completely reset to its default configuration.

    Returns:
        CheckerState: The reset checker state instance
    """
    global _global_state

    async with _state_lock:
        _global_state = CheckerState()
        return _global_state


async def update_checker_state(
    is_running: bool | None = None,
    retries_left: int | None = None,
    last_playback_detected: bool | None = None,
    last_checked: datetime | None = None,
    next_check: datetime | None = None,
) -> CheckerState:
    """Update specific fields of the global checker state.

    This function provides atomic updates to the checker state with
    thread-safety guarantees in asyncio environments.

    Args:
        is_running: Whether the checker is currently running
        retries_left: Number of remaining retry attempts
        last_playback_detected: Whether playback was detected in last check
        last_checked: Timestamp of the last check execution
        next_check: Timestamp of the next scheduled check

    Returns:
        CheckerState: The updated checker state instance
    """
    global _global_state

    async with _state_lock:
        if _global_state is None:
            _global_state = CheckerState()

        # Update only provided fields
        if is_running is not None:
            _global_state.is_running = is_running
        if retries_left is not None:
            _global_state.retries_left = retries_left
        if last_playback_detected is not None:
            _global_state.last_playback_detected = last_playback_detected
        if last_checked is not None:
            _global_state.last_checked = last_checked
        if next_check is not None:
            _global_state.next_check = next_check

        return _global_state
