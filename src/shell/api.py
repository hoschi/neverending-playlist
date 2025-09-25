from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

import uvicorn
from fastapi import FastAPI, HTTPException
from loguru import logger
from returns.future import FutureResult, FutureResultE
from returns.io import IOResultE, IOSuccess
from returns.result import Failure, Success
from returns.unsafe import unsafe_perform_io

from src.core.models import User
from src.core.services import example_transform_service, get_user_details
from src.shell.logging_config import setup_logging


# This is a *concrete* implementation that satisfies the Fetcher protocol.
# Important: It does NOT need to inherit from `Fetcher`!
class InMemoryUserFetcher:
    """A concrete implementation of a user fetcher that uses an in-memory dictionary."""

    _users = {
        1: User(id=1, name="Alice", age=30),
        2: User(id=2, name="Bob", age=25),
    }

    def fetch_by_id(self, key: int) -> FutureResultE[User]:
        logger.info(f"Fetching user {key} from in-memory store.")
        user = self._users.get(key)
        if user is None:
            return FutureResult.from_failure(
                ValueError(f"No user found with id: {key}")
            )

        return FutureResult.from_value(user)


user_fetcher: InMemoryUserFetcher = InMemoryUserFetcher()  # Instance is created here


@asynccontextmanager
async def lifespan(_: object) -> AsyncGenerator[None, None]:  # pragma: no cover
    setup_logging()
    logger.info("FastAPI application starting up...")
    yield


app: FastAPI = FastAPI(lifespan=lifespan)


@app.get("/users/{user_id}", response_model=User)
async def read_user(user_id: int) -> User:
    """
    API endpoint to retrieve a user by their ID.
    It uses the core service function to fetch the data.
    """
    result: IOResultE[User] = await get_user_details(user_fetcher, user_id).awaitable()

    if isinstance(result, IOSuccess):
        success: IOSuccess[User] = cast(IOSuccess[User], result)
        return unsafe_perform_io(success.unwrap())
    else:
        raise HTTPException(
            status_code=404, detail=str(unsafe_perform_io(result.failure()))
        )


@app.get("/transform/")
async def transform_text(text: str) -> dict[str, str]:
    """API endpoint to demonstrate a simple transformation service."""
    result = example_transform_service(text)
    match result:
        case Success(transformed_text):
            return {"original": text, "transformed": transformed_text}
        case Failure(error):
            raise HTTPException(status_code=400, detail=str(error))
        case _:  # pragma: no cover
            raise HTTPException(status_code=500, detail="Unbekannter Fehler")


def main() -> None:  # pragma: no cover
    """Main function to run the FastAPI application."""
    uvicorn.run(app, host="0.0.0.0", port=6361)


if __name__ == "__main__":  # pragma: no cover
    main()
