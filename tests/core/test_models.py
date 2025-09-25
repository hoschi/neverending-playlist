from polyfactory.factories.pydantic_factory import ModelFactory

from src.core.models import User


# 1. A factory for our User model is defined
class UserFactory(ModelFactory[User]):
    __model__ = User
    __check_model__ = True


def test_user_model_creation_with_factory() -> None:
    """Shows how to automatically generate valid User instances."""
    # `build()` creates a Pydantic instance with random but type-correct data
    user_instance = UserFactory.build()

    assert isinstance(user_instance, User)
    assert isinstance(user_instance.name, str)
    assert len(user_instance.name) >= 2  # Respects Pydantic constraints
    assert user_instance.age > 0
    assert user_instance.age <= 120


def test_user_model_creation_with_overrides() -> None:
    """Shows how to set specific values during generation."""
    user_instance = UserFactory.build(name="Specific Test Name", id=123)

    assert user_instance.name == "Specific Test Name"
    assert user_instance.id == 123
