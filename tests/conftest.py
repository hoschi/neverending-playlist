# This file can be used to define global fixtures for pytest.
# For example, you could define a fixture that sets up a database connection
# or creates a test client for your API.
# For now, it's empty, but it's a good practice to have it in your project.

import pytest


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    return "asyncio"
