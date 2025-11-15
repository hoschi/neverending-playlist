import pytest
from fastapi.testclient import TestClient

from src.shell.api import app


@pytest.fixture(scope="module")
def anyio_backend() -> str:
    """Required for pytest-asyncio."""
    return "asyncio"


@pytest.fixture
def client():
    """Provides a TestClient for testing FastAPI endpoints."""
    return TestClient(app)
