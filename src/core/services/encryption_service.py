import base64
from typing import Any

from cryptography.fernet import Fernet
from pydantic import BaseModel, Field, PrivateAttr, SecretStr


class EncryptionService(BaseModel):
    """
    A service for encrypting and decrypting data using Fernet symmetric encryption.
    """

    key: SecretStr = Field(
        ..., description="The secret key for encryption and decryption."
    )
    _fernet: Fernet = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        """
        Validate the key and initialize the Fernet instance after model creation.
        """
        super().model_post_init(__context)
        try:
            key_bytes = self.key.get_secret_value().encode()
            decoded_key = base64.urlsafe_b64decode(key_bytes)
            if len(decoded_key) != 32:
                raise ValueError("Decoded encryption key must be 32 bytes long.")
            self._fernet = Fernet(key_bytes)
        except (ValueError, TypeError) as e:
            # Pydantic will catch this ValueError on init and raise a ValidationError
            raise ValueError(f"Invalid encryption key: {e}") from e  # pragma: no cover

    def encrypt(self, value: str) -> str:
        """Encrypts a string value."""
        encrypted_data = self._fernet.encrypt(value.encode())
        return encrypted_data.decode()

    def decrypt(self, value: str) -> str:
        """Decrypts an encrypted string value."""
        decrypted_data = self._fernet.decrypt(value.encode())
        return decrypted_data.decode()
