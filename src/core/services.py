from loguru import logger
from returns import pointfree as p
from returns.future import FutureResultE
from returns.pipeline import flow, pipe
from returns.result import Failure, Result, Success

from src.core.models import User
from src.core.protocols import Fetcher


def example_transform_service(text: str) -> Result[str, ValueError]:
    """
    An example of a pure function for data transformation.
    This function is easily testable and has no side effects.
    """
    logger.debug(f"Transforming text: '{text}'")

    return flow(
        text,
        # force error to be able to test this example code
        lambda s: Failure(ValueError(text)) if s == "error" else Success(s),
        # if not do the thing!
        p.map_(
            pipe(
                lambda s: s.strip(),
                lambda s: s.lower(),
                lambda s: f"transformed: {s}",
            )
        ),
    )


# Richtig: Wir nutzen Dependency Inversion und programmieren gegen den abstrakten Fetcher-Protocol.
# Falsch wäre: eine konkrete Klasse wie `SupabaseFetcher` hier zu importieren,
# da dies unsere Kernlogik an eine externe Implementierung koppeln würde.
def get_user_details(
    user_fetcher: Fetcher[int, User],  # Programming against the abstraction!
    user_id: int,
) -> FutureResultE[User]:
    """
    Fetches user details without knowing where they come from.
    """
    logger.info(f"Fetching details for user_id: {user_id}")
    return user_fetcher.fetch_by_id(user_id)
