"""
Unit tests for security module (password hashing and JWT handling).
"""
from datetime import datetime, timedelta

import pytest
from jose import JWTError, jwt

from app.core.security import password_handler, jwt_handler, pwd_context
from app.core.config import settings


class TestPasswordHandler:
    """Test password hashing and verification."""

    def test_hash_password(self):
        """Test password hashing."""
        password = "mysecretpassword123"
        hashed = password_handler.hash_password(password)

        # Hash should be different from original password
        assert hashed != password
        # Hash should be a bcrypt hash
        assert hashed.startswith("$2b$")
        # Hash should be verifiable
        assert pwd_context.verify(password, hashed)

    def test_hash_password_different_each_time(self):
        """Test that same password produces different hashes (salt)."""
        password = "samepassword"
        hash1 = password_handler.hash_password(password)
        hash2 = password_handler.hash_password(password)

        assert hash1 != hash2
        # But both should verify correctly
        assert password_handler.verify_password(password, hash1)
        assert password_handler.verify_password(password, hash2)

    def test_verify_password_success(self):
        """Test successful password verification."""
        password = "correctpassword"
        hashed = password_handler.hash_password(password)

        assert password_handler.verify_password(password, hashed) is True

    def test_verify_password_failure(self):
        """Test failed password verification."""
        password = "correctpassword"
        wrong_password = "wrongpassword"
        hashed = password_handler.hash_password(password)

        assert password_handler.verify_password(wrong_password, hashed) is False

    def test_verify_password_empty(self):
        """Test password verification with empty strings."""
        hashed = password_handler.hash_password("password")

        assert password_handler.verify_password("", hashed) is False


class TestJWTHandler:
    """Test JWT token creation and validation."""

    def test_create_access_token(self):
        """Test access token creation."""
        data = {
            "sub": "user-id-123",
            "email": "test@example.com",
        }
        token = jwt_handler.create_access_token(data)

        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify token
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        assert decoded["sub"] == "user-id-123"
        assert decoded["email"] == "test@example.com"
        assert decoded["type"] == "access"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_create_access_token_with_custom_expiry(self):
        """Test access token creation with custom expiration."""
        data = {"sub": "user-id-123"}
        expires_delta = timedelta(minutes=15)
        token = jwt_handler.create_access_token(data, expires_delta=expires_delta)

        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Check expiration is approximately 15 minutes from now
        exp_time = datetime.fromtimestamp(decoded["exp"])
        iat_time = datetime.fromtimestamp(decoded["iat"])
        time_diff = exp_time - iat_time

        # Allow 1 second tolerance
        assert abs(time_diff.total_seconds() - 900) < 1  # 900 seconds = 15 minutes

    def test_create_refresh_token(self):
        """Test refresh token creation."""
        data = {"sub": "user-id-123"}
        token = jwt_handler.create_refresh_token(data)

        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify token
        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        assert decoded["sub"] == "user-id-123"
        assert decoded["type"] == "refresh"
        assert "exp" in decoded
        assert "iat" in decoded

    def test_create_refresh_token_with_custom_expiry(self):
        """Test refresh token creation with custom expiration."""
        data = {"sub": "user-id-123"}
        expires_delta = timedelta(days=30)
        token = jwt_handler.create_refresh_token(data, expires_delta=expires_delta)

        decoded = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        # Check expiration is approximately 30 days from now
        exp_time = datetime.fromtimestamp(decoded["exp"])
        iat_time = datetime.fromtimestamp(decoded["iat"])
        time_diff = exp_time - iat_time

        # Allow 1 second tolerance
        assert abs(time_diff.total_seconds() - (30 * 24 * 60 * 60)) < 1

    def test_decode_token_success(self):
        """Test successful token decoding."""
        data = {
            "sub": "user-id-123",
            "email": "test@example.com",
            "roles": ["user"],
        }
        token = jwt_handler.create_access_token(data)

        decoded = jwt_handler.decode_token(token)

        assert decoded["sub"] == "user-id-123"
        assert decoded["email"] == "test@example.com"
        assert decoded["roles"] == ["user"]
        assert decoded["type"] == "access"

    def test_decode_token_invalid(self):
        """Test decoding invalid token."""
        invalid_token = "invalid.token.here"

        with pytest.raises(JWTError):
            jwt_handler.decode_token(invalid_token)

    def test_decode_token_expired(self):
        """Test decoding expired token."""
        data = {"sub": "user-id-123"}
        # Create token that expires immediately
        expired_token = jwt_handler.create_access_token(
            data,
            expires_delta=timedelta(seconds=-1)
        )

        with pytest.raises(JWTError):
            jwt_handler.decode_token(expired_token)

    def test_decode_token_wrong_secret(self):
        """Test decoding token with wrong secret."""
        data = {"sub": "user-id-123"}
        token = jwt.encode(
            data,
            "wrong-secret-key",
            algorithm=settings.JWT_ALGORITHM
        )

        with pytest.raises(JWTError):
            jwt_handler.decode_token(token)

    def test_token_contains_all_required_fields(self):
        """Test that created tokens contain all required fields."""
        data = {
            "sub": "user-id-123",
            "email": "test@example.com",
            "roles": ["admin"],
            "permissions": [{"resource": "users", "action": "read"}],
            "quotas": {"daily_limit": 100}
        }
        token = jwt_handler.create_access_token(data)
        decoded = jwt_handler.decode_token(token)

        # Check all data fields are preserved
        assert decoded["sub"] == data["sub"]
        assert decoded["email"] == data["email"]
        assert decoded["roles"] == data["roles"]
        assert decoded["permissions"] == data["permissions"]
        assert decoded["quotas"] == data["quotas"]

        # Check system fields are added
        assert "exp" in decoded
        assert "iat" in decoded
        assert "type" in decoded
        assert decoded["type"] == "access"
