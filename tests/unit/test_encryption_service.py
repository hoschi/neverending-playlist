import base64

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from src.core.services.encryption_service import EncryptionService


def test_encrypt_decrypt_roundtrip() -> None:
    """Test that encrypting and then decrypting a value returns the original value."""
    # Arrange
    key = Fernet.generate_key().decode()  # Generate a valid, base64-encoded key
    service = EncryptionService(key=key)
    original_value = "my-secret-refresh-token"

    # Act
    encrypted_value = service.encrypt(original_value)
    decrypted_value = service.decrypt(encrypted_value)

    # Assert
    assert decrypted_value == original_value
    assert encrypted_value != original_value


def test_encryption_service_with_invalid_key_raises_validation_error() -> None:
    """Test that the service raises a ValidationError for a non-base64 key."""
    # Arrange
    invalid_key = "this-is-not-a-valid-base64-key"

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        EncryptionService(key=invalid_key)
    assert "Invalid encryption key" in str(exc_info.value)


def test_encryption_service_with_wrong_key_length_raises_validation_error() -> None:
    """Test that the service raises a ValidationError for a key of the wrong decoded length."""
    # Arrange
    # A valid base64 string that does not decode to 32 bytes.
    wrong_length_key = base64.urlsafe_b64encode(b"a key of the wrong length").decode()

    # Act & Assert
    with pytest.raises(ValidationError) as exc_info:
        EncryptionService(key=wrong_length_key)
    assert "Decoded encryption key must be 32 bytes long" in str(exc_info.value)
