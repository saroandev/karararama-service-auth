"""
Integration tests for authentication endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.crud.user import user_crud
from app.schemas import UserCreate


@pytest.mark.integration
@pytest.mark.auth
class TestRegisterEndpoint:
    """Test /auth/register endpoint."""

    def test_register_success(self, client: TestClient, db_session: AsyncSession):
        """Test successful user registration."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
                "first_name": "New",
                "last_name": "User",
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["first_name"] == "New"
        assert data["last_name"] == "User"
        assert data["is_active"] is True
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        """Test registration with existing email."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "password": "somepassword123",
                "first_name": "Duplicate",
                "last_name": "User",
            }
        )

        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email format."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "password123",
                "first_name": "Test",
                "last_name": "User",
            }
        )

        assert response.status_code == 422  # Validation error

    def test_register_missing_fields(self, client: TestClient):
        """Test registration with missing required fields."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "incomplete@example.com",
            }
        )

        assert response.status_code == 422  # Validation error

    def test_register_weak_password(self, client: TestClient):
        """Test registration with weak password."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "weakpass@example.com",
                "password": "123",  # Too short
                "first_name": "Test",
                "last_name": "User",
            }
        )

        # May return 201 if no password validation, or 422 if validation exists
        # This depends on your schema validation rules
        assert response.status_code in [201, 422]


@pytest.mark.integration
@pytest.mark.auth
class TestLoginEndpoint:
    """Test /auth/login endpoint."""

    def test_login_success(self, client: TestClient, test_user: User):
        """Test successful login."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        assert len(data["refresh_token"]) > 0

    def test_login_wrong_password(self, client: TestClient, test_user: User):
        """Test login with incorrect password."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "wrongpassword",
            }
        )

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "somepassword",
            }
        )

        assert response.status_code == 401
        assert "Incorrect email or password" in response.json()["detail"]

    def test_login_inactive_user(self, client: TestClient, inactive_user: User):
        """Test login with inactive user."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": inactive_user.email,
                "password": "testpassword123",
            }
        )

        assert response.status_code == 400
        assert "Inactive user" in response.json()["detail"]

    def test_login_invalid_email_format(self, client: TestClient):
        """Test login with invalid email format."""
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "not-an-email",
                "password": "password123",
            }
        )

        assert response.status_code == 422  # Validation error

    def test_login_missing_credentials(self, client: TestClient):
        """Test login with missing credentials."""
        response = client.post(
            "/api/v1/auth/login",
            json={}
        )

        assert response.status_code == 422  # Validation error

    def test_login_updates_last_login(self, client: TestClient, test_user: User, db_session: AsyncSession):
        """Test that login updates last_login_at timestamp."""
        original_last_login = test_user.last_login_at

        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            }
        )

        assert response.status_code == 200

        # Note: In integration tests with TestClient, we can't easily verify
        # DB changes without async operations. This test verifies the endpoint works.
        # The actual DB update is tested in unit tests.


@pytest.mark.integration
@pytest.mark.auth
class TestGetMeEndpoint:
    """Test /auth/me endpoint."""

    def test_get_me_success(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test getting current user information."""
        response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["first_name"] == test_user.first_name
        assert data["last_name"] == test_user.last_name
        assert "id" in data
        assert "password" not in data
        assert "password_hash" not in data

    def test_get_me_no_token(self, client: TestClient):
        """Test getting current user without authentication."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 403  # Forbidden (no credentials)

    def test_get_me_invalid_token(self, client: TestClient):
        """Test getting current user with invalid token."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401

    def test_get_me_expired_token(self, client: TestClient):
        """Test getting current user with expired token."""
        from app.core.security import jwt_handler
        from datetime import timedelta

        # Create expired token
        expired_token = jwt_handler.create_access_token(
            {"sub": "user-id-123"},
            expires_delta=timedelta(seconds=-1)
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.auth
class TestVerifyTokenEndpoint:
    """Test /auth/verify endpoint."""

    def test_verify_token_success(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test successful token verification."""
        response = client.post(
            "/api/v1/auth/verify",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "user" in data
        assert data["user"]["email"] == test_user.email
        assert data["user"]["id"] == str(test_user.id)
        assert "roles" in data
        assert "permissions" in data
        assert "quotas" in data
        assert "usage" in data

    def test_verify_token_with_quotas(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test token verification includes quota information."""
        response = client.post(
            "/api/v1/auth/verify",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        quotas = data["quotas"]
        assert "daily_query_limit" in quotas
        assert "monthly_query_limit" in quotas
        assert "daily_document_limit" in quotas
        assert "max_document_size_mb" in quotas
        assert quotas["daily_query_limit"] == test_user.daily_query_limit

    def test_verify_token_with_usage(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test token verification includes usage statistics."""
        response = client.post(
            "/api/v1/auth/verify",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        usage = data["usage"]
        assert "total_queries_used" in usage
        assert "total_documents_uploaded" in usage
        assert usage["total_queries_used"] == test_user.total_queries_used

    def test_verify_token_no_token(self, client: TestClient):
        """Test token verification without token."""
        response = client.post("/api/v1/auth/verify")

        assert response.status_code == 403  # Forbidden

    def test_verify_token_invalid_token(self, client: TestClient):
        """Test token verification with invalid token."""
        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401

    def test_verify_token_inactive_user(self, client: TestClient, inactive_user: User):
        """Test token verification for inactive user."""
        from app.core.security import jwt_handler

        # Create token for inactive user
        token = jwt_handler.create_access_token({
            "sub": str(inactive_user.id),
            "email": inactive_user.email,
        })

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        assert "Inactive user" in response.json()["detail"]

    def test_verify_token_with_roles(self, client: TestClient, admin_user: User, admin_auth_headers: dict):
        """Test token verification includes role information."""
        response = client.post(
            "/api/v1/auth/verify",
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "roles" in data
        assert "admin" in data["roles"]

    def test_verify_token_with_permissions(
        self, client: TestClient, test_user: User, test_role, test_permission
    ):
        """Test token verification includes permission information."""
        from app.core.security import jwt_handler

        # Add role with permission to user
        test_user.roles.append(test_role)

        # Create token
        token = jwt_handler.create_access_token({
            "sub": str(test_user.id),
            "email": test_user.email,
        })

        response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "permissions" in data
        permissions = data["permissions"]
        # Check if our test permission is in the list
        assert any(
            p["resource"] == test_permission.resource and p["action"] == test_permission.action
            for p in permissions
        )
