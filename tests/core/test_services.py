import pytest
from hypothesis import given
from hypothesis import strategies as st
from returns.future import FutureResult, FutureResultE
from returns.pipeline import is_successful
from returns.result import Failure, Success
from returns.unsafe import unsafe_perform_io

from src.core import services
from src.core.models import User


# --- Technique 1: Unit-Testing ---
def test_simple_pipeline_logic() -> None:
    """A simple unit test for a deterministic function."""
    result = services.example_transform_service("  Test  ")
    # `returns` provides helpers to safely extract the content
    assert result.unwrap() == "transformed: test"


# --- Technique 3: Mocking with Protocols ---
class MockUserFetcher:
    _users = {
        1: User(id=1, name="Mocked User", age=25),
    }

    def fetch_by_id(self, key: int) -> FutureResultE[User]:
        user = self._users.get(key)
        if user is None:
            return FutureResult.from_failure(
                ValueError(f"No user found with id: {key}")
            )

        return FutureResult.from_value(user)


mock_fetcher = MockUserFetcher()


@pytest.mark.anyio
async def test_get_user_details_success_with_mock() -> None:
    """Tests the success path of get_user_details with a mock."""
    result = await services.get_user_details(mock_fetcher, 1)

    assert is_successful(result)
    assert unsafe_perform_io(result.unwrap()).name == "Mocked User"


@pytest.mark.anyio
async def test_get_user_details_not_found_with_mock() -> None:
    """Tests the failure path (user not found) with a mock."""
    result = await services.get_user_details(mock_fetcher, 999)

    assert not is_successful(result)
    assert "No user found" in str(result.failure())


# --- Technique 2: Property-Based Testing ---
@given(st.text().filter(lambda s: s != "error"))
def test_example_transform_service_properties(s: str) -> None:
    """
    Tests properties of the transformation function.
    Hypothesis generates hundreds of different strings.
    """
    result = services.example_transform_service(s)
    # Property 1: The output should always be a Success object for any string.
    assert isinstance(result, Success)
    # Property 2: The output should always start with "transformed:".
    assert result.unwrap().startswith("transformed:")
    # Property 3: The transformed text should not have leading/trailing whitespace.
    assert result.unwrap().replace(
        "transformed: ", ""
    ).strip() == result.unwrap().replace("transformed: ", "")


def test_example_transform_service_failure() -> None:
    """
    Tests the failure path of the transformation function with non-string input.
    """
    result = services.example_transform_service("error")
    assert isinstance(result, Failure)
    assert isinstance(result.failure(), ValueError)
