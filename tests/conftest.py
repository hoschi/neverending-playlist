# This file can be used to define global fixtures for pytest.
# For example, you could define a fixture that sets up a database connection
# or creates a test client for your API.
# For now, it's empty, but it's a good practice to have it in your project.


import pytest


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    """Required for pytest-asyncio."""
    return "asyncio"


# The http_client fixture has been removed to allow for per-test
# dependency overrides. Tests should now create their own AsyncClient
# within the test function body.
