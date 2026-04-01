"""Token encryption utilities for secure OAuth credential storage."""

import os
from typing import Optional
from cryptography.fernet import Fernet
from loguru import logger


class TokenEncryption:
    """Handles encryption and decryption of OAuth tokens."""

    _cipher: Optional[Fernet] = None

    @classmethod
    def get_cipher(cls) -> Fernet:
        """Get or initialize the Fernet cipher instance."""
        if cls._cipher is None:
            key = os.getenv("TOKEN_ENCRYPTION_KEY")
            if not key:
                raise ValueError(
                    "TOKEN_ENCRYPTION_KEY environment variable not set. "
                    "Generate with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
                )
            cls._cipher = Fernet(key.encode() if isinstance(key, str) else key)
        return cls._cipher

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """Encrypt a token string."""
        if not plaintext:
            return plaintext
        try:
            cipher = cls.get_cipher()
            encrypted = cipher.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            raise

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """Decrypt a token string."""
        if not ciphertext:
            return ciphertext
        try:
            cipher = cls.get_cipher()
            decrypted = cipher.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            raise


def encrypt_token(token: str) -> str:
    """Convenience function to encrypt a token."""
    return TokenEncryption.encrypt(token)


def decrypt_token(token: str) -> str:
    """Convenience function to decrypt a token."""
    return TokenEncryption.decrypt(token)
