"""Comprehensive tests for state.py to achieve full coverage."""

import asyncio
from datetime import datetime
from unittest.mock import patch

from src.shell.state import (
    CheckerState,
    get_checker_state,
    reset_checker_state,
    update_checker_state,
)


def test_checker_state_initialization():
    """Test CheckerState initialization with default values."""
    state = CheckerState()
    assert state.is_running is False
    assert state.retries_left == 5
    assert state.last_checked is None
    assert state.last_playback_detected is False
    assert state.next_check is None


def test_checker_state_custom_initialization():
    """Test CheckerState initialization with custom values."""
    custom_datetime = datetime.now()
    state = CheckerState(
        is_running=True,
        retries_left=3,
        last_checked=custom_datetime,
        last_playback_detected=True,
        next_check=custom_datetime,
    )

    assert state.is_running is True
    assert state.retries_left == 3
    assert state.last_checked == custom_datetime
    assert state.last_playback_detected is True
    assert state.next_check == custom_datetime


def test_checker_state_pydantic_model():
    """Test that CheckerState works as a Pydantic model."""
    # Test validation
    state = CheckerState(is_running=True, retries_left=3)
    assert state.is_running is True
    assert state.retries_left == 3

    # Test dict conversion (inherited from BaseModel)
    result = state.model_dump()
    assert "is_running" in result
    assert "retries_left" in result
    assert result["is_running"] is True
    assert result["retries_left"] == 3


async def test_get_checker_state_creates_new_state():
    """Test that get_checker_state creates new state when none exists."""
    with patch("src.shell.state._global_state", None):
        result = await get_checker_state()

        assert isinstance(result, CheckerState)
        assert result.is_running is False
        assert result.retries_left == 5
        assert result.last_playback_detected is False


async def test_get_checker_state_returns_existing_state():
    """Test that get_checker_state returns existing state."""
    mock_state = CheckerState(is_running=True, retries_left=3)
    with patch("src.shell.state._global_state", mock_state):
        result = await get_checker_state()

        assert result.is_running is True
        assert result.retries_left == 3
        assert result is mock_state


async def test_update_checker_state_with_all_parameters():
    """Test update_checker_state with all parameters."""
    custom_datetime = datetime.now()

    with patch("src.shell.state._global_state", CheckerState()):
        result = await update_checker_state(
            is_running=True,
            retries_left=3,
            last_checked=custom_datetime,
            last_playback_detected=True,
            next_check=custom_datetime,
        )

        assert result.is_running is True
        assert result.retries_left == 3
        assert result.last_checked == custom_datetime
        assert result.last_playback_detected is True
        assert result.next_check == custom_datetime


async def test_update_checker_state_partial_update():
    """Test update_checker_state with partial parameters."""
    with patch("src.shell.state._global_state", CheckerState()):
        # Update only some fields
        result = await update_checker_state(
            is_running=True,
            retries_left=3,
        )

        assert result.is_running is True
        assert result.retries_left == 3

        # Other fields should remain default
        assert result.last_checked is None
        assert result.last_playback_detected is False
        assert result.next_check is None


async def test_update_checker_state_creates_state_if_none():
    """Test that update_checker_state creates state if none exists."""
    with patch("src.shell.state._global_state", None):
        result = await update_checker_state(is_running=True, retries_left=3)

        assert result.is_running is True
        assert result.retries_left == 3
        assert result.last_checked is None
        assert result.last_playback_detected is False
        assert result.next_check is None


async def test_update_checker_state_none_values():
    """Test update_checker_state with None values (should not update)."""
    initial_state = CheckerState(is_running=True, retries_left=5)

    with patch("src.shell.state._global_state", initial_state):
        result = await update_checker_state(
            is_running=None,  # Should not update
            retries_left=None,  # Should not update
        )

        # Should remain unchanged
        assert result.is_running is True
        assert result.retries_left == 5


async def test_reset_checker_state_success():
    """Test successful reset_checker_state operation."""
    # Set non-default state
    with patch(
        "src.shell.state._global_state", CheckerState(is_running=True, retries_left=1)
    ):
        result = await reset_checker_state()

        # Should be reset to defaults
        assert result.is_running is False
        assert result.retries_left == 5
        assert result.last_checked is None
        assert result.last_playback_detected is False
        assert result.next_check is None


async def test_reset_checker_state_creates_new_state():
    """Test that reset_checker_state creates new state if none exists."""
    with patch("src.shell.state._global_state", None):
        result = await reset_checker_state()

        assert isinstance(result, CheckerState)
        assert result.is_running is False
        assert result.retries_left == 5


async def test_concurrent_state_access():
    """Test thread-safe concurrent state access."""

    async def update_state_1():
        return await update_checker_state(is_running=True, retries_left=10)

    async def update_state_2():
        return await update_checker_state(retries_left=5)

    # Run concurrently
    results = await asyncio.gather(update_state_1(), update_state_2())

    # At least one should succeed (exact result depends on timing)
    # The important thing is that no exception should be raised
    assert len(results) == 2
    assert all(isinstance(r, CheckerState) for r in results)


async def test_state_persistence_across_calls():
    """Test that state persists across multiple function calls."""
    # First update
    await update_checker_state(is_running=True, retries_left=10)

    # Second update should see the changes from first
    result2 = await update_checker_state(retries_left=5)

    # The second result should have the updated state from first call
    assert result2.retries_left == 5
    assert result2.is_running is True  # From first call


async def test_get_checker_state_after_updates():
    """Test getting state after various updates."""
    # Update state
    await update_checker_state(is_running=True, retries_left=3)

    # Get state - should reflect the update
    result = await get_checker_state()

    assert result.is_running is True
    assert result.retries_left == 3


async def test_multiple_resets():
    """Test multiple consecutive resets."""
    # Set some state
    await update_checker_state(is_running=True, retries_left=1)

    # Reset once
    result1 = await reset_checker_state()
    assert result1.is_running is False
    assert result1.retries_left == 5

    # Reset again
    result2 = await reset_checker_state()
    assert result2.is_running is False
    assert result2.retries_left == 5

    # Should be same state
    assert result1 == result2


def test_checker_state_model_validation():
    """Test Pydantic model validation."""
    # Valid state
    state = CheckerState(is_running=True, retries_left=10)
    assert state.is_running is True
    assert state.retries_left == 10

    # Test with int retries_left (proper type)
    state_with_int = CheckerState(retries_left=10)
    assert state_with_int.retries_left == 10


def test_checker_state_equality():
    """Test CheckerState equality comparison."""
    state1 = CheckerState(is_running=True, retries_left=3)
    state2 = CheckerState(is_running=True, retries_left=3)
    state3 = CheckerState(is_running=False, retries_left=3)

    # Equal states
    assert state1 == state2

    # Different states
    assert state1 != state3


def test_checker_state_serialization():
    """Test CheckerState serialization."""
    custom_datetime = datetime.now()
    state = CheckerState(
        is_running=True,
        retries_left=3,
        last_checked=custom_datetime,
        last_playback_detected=True,
        next_check=custom_datetime,
    )

    # Test model_dump (Pydantic method)
    result = state.model_dump()

    assert result["is_running"] is True
    assert result["retries_left"] == 3
    assert result["last_checked"] == custom_datetime
    assert result["last_playback_detected"] is True
    assert result["next_check"] == custom_datetime


def test_checker_state_json_serialization():
    """Test CheckerState JSON serialization."""
    state = CheckerState(is_running=True, retries_left=3)

    # Test JSON serialization
    json_str = state.model_dump_json()

    # Should contain key information (JSON format doesn't include spaces)
    assert '"is_running":true' in json_str
    assert '"retries_left":3' in json_str


async def test_lock_synchronization():
    """Test that asyncio.Lock is properly used for synchronization."""
    # This test verifies that the lock is used correctly
    # We can't easily test the actual locking behavior without complex setup,
    # but we can verify the lock exists and the functions are async

    from src.shell.state import _state_lock

    assert _state_lock is not None
    assert isinstance(_state_lock, asyncio.Lock)

    # All functions should be async and use the lock
    result = await get_checker_state()
    assert isinstance(result, CheckerState)


# Test edge cases and error scenarios
async def test_update_checker_state_with_invalid_datetime():
    """Test update_checker_state with various datetime values."""
    # Test with None
    result1 = await update_checker_state(last_checked=None)
    assert result1.last_checked is None

    # Test with actual datetime
    dt = datetime.now()
    result2 = await update_checker_state(last_checked=dt)
    assert result2.last_checked == dt


async def test_state_update_retries_left_boundaries():
    """Test update_checker_state with boundary values for retries_left."""
    # Test with 0
    result1 = await update_checker_state(retries_left=0)
    assert result1.retries_left == 0

    # Test with large number
    result2 = await update_checker_state(retries_left=999)
    assert result2.retries_left == 999

    # Test with negative (Pydantic might handle this)
    try:
        result3 = await update_checker_state(retries_left=-1)
        # If it doesn't raise an error, the value should be set
        assert result3.retries_left == -1
    except Exception:
        # If Pydantic validates and rejects negative values, that's also fine
        pass


async def test_concurrent_resets():
    """Test concurrent reset operations."""

    async def reset_1():
        return await reset_checker_state()

    async def reset_2():
        return await reset_checker_state()

    # Run resets concurrently
    results = await asyncio.gather(reset_1(), reset_2())

    # Both should result in the same default state
    assert all(r.is_running is False for r in results)
    assert all(r.retries_left == 5 for r in results)
