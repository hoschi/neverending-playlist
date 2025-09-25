from typing import Protocol, TypeVar

from returns.future import future_safe

# TypeVars for generic keys and return values
KeyType = TypeVar("KeyType", contravariant=True)
ReturnType = TypeVar("ReturnType", covariant=True)


class Fetcher(Protocol[KeyType, ReturnType]):
    """
    A generic contract for any component that can fetch data by a key.
    This could be a DB client, an API client, or an in-memory cache.
    """

    @future_safe
    async def fetch_by_id(
        self, key: KeyType
    ) -> (
        ReturnType
    ): ...  # The '...' is intentional; Protocols only define the signature.
