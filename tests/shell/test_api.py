from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from src.shell.api import app


@pytest.fixture(scope="module")
async def test_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.mark.anyio
async def test_read_user_success(test_client: AsyncClient) -> None:
    """Tests successful user retrieval."""
    response = await test_client.get("/users/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Alice"


@pytest.mark.anyio
async def test_read_user_not_found(test_client: AsyncClient) -> None:
    """Tests the case where a user is not found."""
    response = await test_client.get("/users/999")
    assert response.status_code == 404
    assert response.json() == {"detail": "No user found with id: 999"}


@pytest.mark.anyio
async def test_transform_text_success(test_client: AsyncClient) -> None:
    """Tests the transformation endpoint."""
    response = await test_client.get("/transform/?text=  Hello World  ")
    assert response.status_code == 200
    assert response.json() == {
        "original": "  Hello World  ",
        "transformed": "transformed: hello world",
    }


@pytest.mark.anyio
async def test_transform_text_error(test_client: AsyncClient) -> None:
    """Tests the transformation endpoint."""
    response = await test_client.get("/transform/?text=error")
    assert response.status_code == 400
    assert response.json() == {"detail": "error"}
