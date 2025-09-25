from typing import Annotated, Any

from pydantic import BaseModel, Field


class User(BaseModel):
    """
    Represents a user in the system.
    Uses `Annotated` for clean metadata that is interpreted by Pydantic.
    """

    id: int

    # The type is `str`, enriched with metadata from Pydantic's `Field`.
    # Other tools could also add annotations here.
    name: Annotated[str, Field(min_length=2, description="The user's name")]

    age: Annotated[int, Field(gt=0, le=120, description="Age in years")]


class ApiResponse(BaseModel):
    """A generic API response model."""

    status: str
    data: dict[str, Any] | None = None
