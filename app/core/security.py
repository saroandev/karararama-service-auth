"""
Security utilities for password hashing and JWT token management.
"""
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from cryptography.fernet import Fernet
from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordHandler:
    """Handle password hashing and verification."""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a plain text password.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hash.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to compare against

        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)


class JWTHandler:
    """Handle JWT token creation and validation."""

    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT access token.

        Args:
            data: Data to encode in the token
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def create_refresh_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create a JWT refresh token.

        Args:
            data: Data to encode in the token
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decode and validate a JWT token.

        Args:
            token: JWT token to decode

        Returns:
            Decoded token payload

        Raises:
            JWTError: If token is invalid or expired
        """
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload


class ActivityWatchTokenHandler:
    """Handle Activity Watch token generation and encryption."""

    def __init__(self):
        """Initialize with encryption key derived from JWT secret."""
        # Derive a Fernet key from JWT secret (must be 32 url-safe base64-encoded bytes)
        import base64
        import hashlib
        # Use SHA256 to get 32 bytes from JWT secret, then base64 encode
        key_bytes = hashlib.sha256(settings.JWT_SECRET_KEY.encode()).digest()
        self.fernet_key = base64.urlsafe_b64encode(key_bytes)
        self.cipher = Fernet(self.fernet_key)

    def generate_token(self) -> Tuple[str, str]:
        """
        Generate a new Activity Watch token.

        Returns a tuple of (plain_token, encrypted_token) where:
        - plain_token: The token to return to the user (aw_ prefix + 64 hex chars)
        - encrypted_token: Encrypted token to store in database (can be decrypted)

        Returns:
            Tuple[str, str]: (plain_token, encrypted_token)
        """
        # Generate a secure random token using uuid + secrets
        random_part = uuid.uuid4().hex + secrets.token_hex(32)
        plain_token = f"aw_{random_part}"

        # Encrypt the token for storage (can be decrypted later)
        encrypted_token = self.cipher.encrypt(plain_token.encode()).decode()

        return plain_token, encrypted_token

    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt an encrypted Activity Watch token.

        Args:
            encrypted_token: Encrypted token from database

        Returns:
            Decrypted plain text token
        """
        return self.cipher.decrypt(encrypted_token.encode()).decode()

    def verify_token(self, plain_token: str, encrypted_token: str) -> bool:
        """
        Verify an Activity Watch token against its encrypted version.

        Args:
            plain_token: Plain text token from user
            encrypted_token: Encrypted token from database

        Returns:
            True if token matches, False otherwise
        """
        try:
            decrypted = self.decrypt_token(encrypted_token)
            return decrypted == plain_token
        except Exception:
            return False


# Convenience instances
password_handler = PasswordHandler()
jwt_handler = JWTHandler()
aw_token_handler = ActivityWatchTokenHandler()

# Helper functions for backward compatibility
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a plain text password."""
    return pwd_context.hash(password)