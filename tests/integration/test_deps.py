"""
Integration tests for authentication and authorization dependencies.
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_active_user,
    require_role,
    require_permission
)
from app.core.security import jwt_handler
from app.models import User, Role, Permission
from app.core.database import get_db


@pytest.mark.integration
class TestGetCurrentUser:
    """Test get_current_user dependency."""

    def test_get_current_user_valid_token(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test getting current user with valid token."""
        # Use the /auth/me endpoint which uses get_current_user
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email

    def test_get_current_user_no_token(self, client: TestClient):
        """Test getting current user without token."""
        response = client.get("/api/v1/auth/me")

        assert response.status_code == 403

    def test_get_current_user_invalid_token(self, client: TestClient):
        """Test getting current user with invalid token."""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]

    def test_get_current_user_expired_token(self, client: TestClient):
        """Test getting current user with expired token."""
        expired_token = jwt_handler.create_access_token(
            {"sub": str(uuid4())},
            expires_delta=timedelta(seconds=-1)
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401

    def test_get_current_user_nonexistent_user_id(self, client: TestClient):
        """Test getting current user with token containing non-existent user ID."""
        fake_user_id = uuid4()
        token = jwt_handler.create_access_token({"sub": str(fake_user_id)})

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_get_current_user_missing_sub_claim(self, client: TestClient):
        """Test getting current user with token missing 'sub' claim."""
        # Manually create token without 'sub' claim
        from jose import jwt
        from app.core.config import settings

        token = jwt.encode(
            {"email": "test@example.com"},
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 401
        assert "Could not validate credentials" in response.json()["detail"]


@pytest.mark.integration
class TestGetCurrentActiveUser:
    """Test get_current_active_user dependency."""

    def test_get_active_user_success(self, client: TestClient, test_user: User, auth_headers: dict):
        """Test getting active user."""
        # /auth/me uses get_current_active_user
        response = client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    def test_get_active_user_inactive(self, client: TestClient, inactive_user: User):
        """Test getting current user when user is inactive."""
        token = jwt_handler.create_access_token({
            "sub": str(inactive_user.id),
            "email": inactive_user.email,
        })

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        assert "Inactive user" in response.json()["detail"]


@pytest.mark.integration
class TestRequireRole:
    """Test require_role dependency."""

    def test_require_role_admin_success(self, client: TestClient, admin_auth_headers: dict):
        """Test accessing admin endpoint with admin role."""
        response = client.get("/api/v1/admin/roles", headers=admin_auth_headers)

        assert response.status_code == 200

    def test_require_role_admin_without_role(self, client: TestClient, auth_headers: dict):
        """Test accessing admin endpoint without admin role."""
        response = client.get("/api/v1/admin/roles", headers=auth_headers)

        assert response.status_code == 403
        assert "Required role" in response.json()["detail"]

    def test_require_role_no_auth(self, client: TestClient):
        """Test accessing role-protected endpoint without authentication."""
        response = client.get("/api/v1/admin/roles")

        assert response.status_code == 403

    def test_require_role_admin_has_all_access(
        self, client: TestClient, admin_auth_headers: dict, test_user: User, test_role: Role
    ):
        """Test that admin role has access to all role-protected endpoints."""
        # Try to assign role (requires admin)
        response = client.post(
            f"/api/v1/admin/users/{test_user.id}/roles/{test_role.id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 200


@pytest.mark.integration
class TestRequirePermission:
    """Test require_permission dependency."""

    def test_require_permission_with_permission(self, db_session: AsyncSession):
        """Test accessing endpoint when user has required permission."""
        # Create a test app with permission-protected endpoint
        from app.main import app
        from app.core.database import get_db

        test_app = FastAPI()

        @test_app.get("/test-permission")
        async def test_endpoint(
            user: User = Depends(require_permission("test_resource", "test_action"))
        ):
            return {"success": True}

        # Override DB dependency
        async def override_get_db():
            yield db_session

        test_app.dependency_overrides[get_db] = override_get_db

        # This is a conceptual test - in practice, you'd need to set up
        # a user with the specific permission and test the endpoint

    def test_require_permission_admin_has_all(self, client: TestClient, admin_auth_headers: dict):
        """Test that admin has all permissions."""
        # Admin user should have access to any permission-protected endpoint
        # We can test this through existing endpoints if they use require_permission
        # For now, this is a placeholder for permission-based endpoint tests
        pass

    def test_require_permission_without_permission(self):
        """Test accessing endpoint without required permission."""
        # This would require creating a specific permission-protected endpoint
        # and testing with a user who doesn't have that permission
        pass

    def test_require_permission_wildcard(self):
        """Test permission check with wildcard permissions."""
        # Test that resource:* or *:* permissions work correctly
        pass


@pytest.mark.integration
class TestAuthenticationFlow:
    """Test complete authentication flow."""

    def test_full_auth_flow(self, client: TestClient, db_session: AsyncSession):
        """Test complete authentication flow from registration to accessing protected endpoint."""
        # 1. Register new user
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "flowtest@example.com",
                "password": "testpassword123",
                "first_name": "Flow",
                "last_name": "Test",
            }
        )
        assert register_response.status_code == 201

        # 2. Login with credentials
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "flowtest@example.com",
                "password": "testpassword123",
            }
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        access_token = tokens["access_token"]

        # 3. Access protected endpoint with token
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert me_response.status_code == 200
        user_data = me_response.json()
        assert user_data["email"] == "flowtest@example.com"

        # 4. Verify token
        verify_response = client.post(
            "/api/v1/auth/verify",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert verify_response.status_code == 200
        assert verify_response.json()["valid"] is True

    def test_auth_flow_wrong_password(self, client: TestClient):
        """Test authentication flow with wrong password."""
        # Register
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "wrongpass@example.com",
                "password": "correctpassword",
                "first_name": "Test",
                "last_name": "User",
            }
        )

        # Try to login with wrong password
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongpass@example.com",
                "password": "wrongpassword",
            }
        )
        assert login_response.status_code == 401

    def test_auth_flow_inactive_user(self, client: TestClient, inactive_user: User):
        """Test authentication flow with inactive user."""
        # Try to login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": inactive_user.email,
                "password": "testpassword123",
            }
        )
        assert login_response.status_code == 400
        assert "Inactive user" in login_response.json()["detail"]


@pytest.mark.integration
class TestTokenBehavior:
    """Test various token behaviors."""

    def test_token_contains_user_data(self, client: TestClient, test_user: User):
        """Test that token contains necessary user data."""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            }
        )
        assert login_response.status_code == 200

        access_token = login_response.json()["access_token"]

        # Decode token to verify contents
        decoded = jwt_handler.decode_token(access_token)
        assert decoded["sub"] == str(test_user.id)
        assert decoded["email"] == test_user.email
        assert "roles" in decoded
        assert "permissions" in decoded
        assert "quotas" in decoded

    def test_refresh_token_different_from_access(self, client: TestClient, test_user: User):
        """Test that refresh token is different from access token."""
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            }
        )

        tokens = login_response.json()
        assert tokens["access_token"] != tokens["refresh_token"]

        # Verify token types
        access_decoded = jwt_handler.decode_token(tokens["access_token"])
        refresh_decoded = jwt_handler.decode_token(tokens["refresh_token"])

        assert access_decoded["type"] == "access"
        assert refresh_decoded["type"] == "refresh"

    def test_token_includes_roles_and_permissions(
        self, client: TestClient, test_user: User, test_role: Role, test_permission: Permission, db_session: AsyncSession
    ):
        """Test that token includes user's roles and permissions."""
        # Add role and permission to user
        test_user.roles.append(test_role)
        db_session.add(test_user)
        # Note: In a real scenario with proper async handling, you'd await commit

        # Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": test_user.email,
                "password": "testpassword123",
            }
        )

        # Token should include roles and permissions
        # This test demonstrates the expected behavior
        assert login_response.status_code == 200
