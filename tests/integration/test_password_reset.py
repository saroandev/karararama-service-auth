"""
Integration tests for password reset functionality.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.crud import password_reset
from app.core.security import password_handler


@pytest.mark.integration
@pytest.mark.asyncio
class TestPasswordReset:
    """Test password reset flow."""

    async def test_forgot_password_success(
        self,
        client: AsyncClient,
        test_user: User
    ):
        """Test forgot password request with valid email."""
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": test_user.email}
        )
        assert response.status_code == 200
        assert "sistemde kayıtlıysa" in response.json()["message"]

    async def test_forgot_password_nonexistent_email(
        self,
        client: AsyncClient
    ):
        """Test forgot password with non-existent email (should still return success)."""
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@example.com"}
        )
        assert response.status_code == 200
        assert "sistemde kayıtlıysa" in response.json()["message"]

    async def test_forgot_password_rate_limit(
        self,
        client: AsyncClient,
        test_user: User
    ):
        """Test forgot password rate limiting."""
        # Make 3 requests (should succeed)
        for _ in range(3):
            response = await client.post(
                "/api/v1/auth/forgot-password",
                json={"email": test_user.email}
            )
            assert response.status_code == 200

        # 4th request should fail
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": test_user.email}
        )
        assert response.status_code == 429
        assert "Çok fazla" in response.json()["detail"]

    async def test_validate_reset_token_invalid(
        self,
        client: AsyncClient
    ):
        """Test token validation with invalid token."""
        response = await client.post(
            "/api/v1/auth/validate-reset-token",
            json={"token": "invalid-token-123"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "Geçersiz" in data["error"]

    async def test_validate_reset_token_valid(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_user: User
    ):
        """Test token validation with valid token."""
        # Create reset token
        reset_token_record, raw_token = await password_reset.create_reset_token(
            db,
            user_id=test_user.id
        )

        response = await client.post(
            "/api/v1/auth/validate-reset-token",
            json={"token": raw_token}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["email"] == test_user.email

    async def test_reset_password_success(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_user: User
    ):
        """Test password reset with valid token."""
        # Create reset token
        reset_token_record, raw_token = await password_reset.create_reset_token(
            db,
            user_id=test_user.id
        )

        new_password = "NewPassword123!"

        # Reset password
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": new_password,
                "new_password_confirm": new_password
            }
        )
        assert response.status_code == 200
        assert "başarıyla güncellendi" in response.json()["message"]

        # Verify password was updated
        await db.refresh(test_user)
        assert password_handler.verify_password(new_password, test_user.password_hash)

        # Verify token was marked as used
        await db.refresh(reset_token_record)
        assert reset_token_record.is_used is True

    async def test_reset_password_invalid_token(
        self,
        client: AsyncClient
    ):
        """Test password reset with invalid token."""
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "invalid-token",
                "new_password": "NewPassword123!",
                "new_password_confirm": "NewPassword123!"
            }
        )
        assert response.status_code == 400
        assert "Geçersiz" in response.json()["detail"]

    async def test_reset_password_mismatched_passwords(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_user: User
    ):
        """Test password reset with mismatched passwords."""
        # Create reset token
        reset_token_record, raw_token = await password_reset.create_reset_token(
            db,
            user_id=test_user.id
        )

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "NewPassword123!",
                "new_password_confirm": "DifferentPassword123!"
            }
        )
        assert response.status_code == 422  # Validation error

    async def test_reset_password_token_reuse(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_user: User
    ):
        """Test that reset token cannot be reused."""
        # Create reset token
        reset_token_record, raw_token = await password_reset.create_reset_token(
            db,
            user_id=test_user.id
        )

        new_password = "NewPassword123!"

        # First reset (should succeed)
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": new_password,
                "new_password_confirm": new_password
            }
        )
        assert response.status_code == 200

        # Try to use same token again (should fail)
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "AnotherPassword123!",
                "new_password_confirm": "AnotherPassword123!"
            }
        )
        assert response.status_code == 400
        assert "Geçersiz" in response.json()["detail"]

    async def test_reset_password_sessions_invalidated(
        self,
        client: AsyncClient,
        db: AsyncSession,
        test_user: User
    ):
        """Test that all user sessions are invalidated after password reset."""
        from app.crud import refresh_token_crud
        from app.core.security import jwt_handler

        # Create some refresh tokens (simulate multiple sessions)
        token1 = jwt_handler.create_refresh_token({"sub": str(test_user.id)})
        token2 = jwt_handler.create_refresh_token({"sub": str(test_user.id)})
        await refresh_token_crud.create(db, test_user.id, token1)
        await refresh_token_crud.create(db, test_user.id, token2)

        # Create reset token
        reset_token_record, raw_token = await password_reset.create_reset_token(
            db,
            user_id=test_user.id
        )

        new_password = "NewPassword123!"

        # Reset password
        response = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": new_password,
                "new_password_confirm": new_password
            }
        )
        assert response.status_code == 200

        # Verify refresh tokens were revoked
        rt1 = await refresh_token_crud.get_by_token(db, token1)
        rt2 = await refresh_token_crud.get_by_token(db, token2)
        assert rt1.revoked_at is not None
        assert rt2.revoked_at is not None
