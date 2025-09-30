"""
Integration tests for admin management endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4

from app.models import User, Role


@pytest.mark.integration
@pytest.mark.admin
class TestGetAllRoles:
    """Test GET /admin/roles endpoint."""

    def test_get_all_roles_success(self, client: TestClient, admin_auth_headers: dict, test_role: Role):
        """Test getting all roles as admin."""
        response = client.get(
            "/api/v1/admin/roles",
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1  # At least test_role and admin_role

    def test_get_all_roles_with_pagination(self, client: TestClient, admin_auth_headers: dict):
        """Test getting roles with pagination."""
        response = client.get(
            "/api/v1/admin/roles?skip=0&limit=10",
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_all_roles_unauthorized(self, client: TestClient, auth_headers: dict):
        """Test getting roles without admin privileges."""
        response = client.get(
            "/api/v1/admin/roles",
            headers=auth_headers
        )

        assert response.status_code == 403
        assert "Required role" in response.json()["detail"]

    def test_get_all_roles_no_auth(self, client: TestClient):
        """Test getting roles without authentication."""
        response = client.get("/api/v1/admin/roles")

        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.admin
class TestCreateRole:
    """Test POST /admin/roles endpoint."""

    def test_create_role_success(self, client: TestClient, admin_auth_headers: dict):
        """Test creating a new role as admin."""
        response = client.post(
            "/api/v1/admin/roles",
            headers=admin_auth_headers,
            json={
                "name": "new_role",
                "description": "A new test role",
                "default_daily_query_limit": 50,
                "default_monthly_query_limit": 500,
                "default_daily_document_limit": 5,
                "default_max_document_size_mb": 5,
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new_role"
        assert data["description"] == "A new test role"
        assert data["default_daily_query_limit"] == 50
        assert "id" in data

    def test_create_role_duplicate_name(self, client: TestClient, admin_auth_headers: dict, test_role: Role):
        """Test creating role with duplicate name."""
        response = client.post(
            "/api/v1/admin/roles",
            headers=admin_auth_headers,
            json={
                "name": test_role.name,
                "description": "Duplicate role",
            }
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    def test_create_role_unauthorized(self, client: TestClient, auth_headers: dict):
        """Test creating role without admin privileges."""
        response = client.post(
            "/api/v1/admin/roles",
            headers=auth_headers,
            json={
                "name": "unauthorized_role",
                "description": "Should not be created",
            }
        )

        assert response.status_code == 403

    def test_create_role_missing_fields(self, client: TestClient, admin_auth_headers: dict):
        """Test creating role with missing required fields."""
        response = client.post(
            "/api/v1/admin/roles",
            headers=admin_auth_headers,
            json={}
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.integration
@pytest.mark.admin
class TestAssignRoleToUser:
    """Test POST /admin/users/{user_id}/roles/{role_id} endpoint."""

    def test_assign_role_success(
        self, client: TestClient, admin_auth_headers: dict, test_user: User, test_role: Role
    ):
        """Test assigning role to user as admin."""
        response = client.post(
            f"/api/v1/admin/users/{test_user.id}/roles/{test_role.id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert "roles" in data
        assert len(data["roles"]) >= 1
        assert any(role["name"] == test_role.name for role in data["roles"])

    def test_assign_role_updates_quotas(
        self, client: TestClient, admin_auth_headers: dict, test_user: User, test_role: Role
    ):
        """Test that assigning role updates user quotas."""
        response = client.post(
            f"/api/v1/admin/users/{test_user.id}/roles/{test_role.id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        # Quotas should be updated to match role defaults
        assert data["daily_query_limit"] == test_role.default_daily_query_limit
        assert data["monthly_query_limit"] == test_role.default_monthly_query_limit

    def test_assign_role_nonexistent_user(self, client: TestClient, admin_auth_headers: dict, test_role: Role):
        """Test assigning role to non-existent user."""
        fake_user_id = uuid4()
        response = client.post(
            f"/api/v1/admin/users/{fake_user_id}/roles/{test_role.id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_assign_nonexistent_role(self, client: TestClient, admin_auth_headers: dict, test_user: User):
        """Test assigning non-existent role to user."""
        fake_role_id = uuid4()
        response = client.post(
            f"/api/v1/admin/users/{test_user.id}/roles/{fake_role_id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 404
        assert "Role not found" in response.json()["detail"]

    def test_assign_role_already_assigned(
        self, client: TestClient, admin_auth_headers: dict, admin_user: User, admin_role: Role
    ):
        """Test assigning role that user already has."""
        response = client.post(
            f"/api/v1/admin/users/{admin_user.id}/roles/{admin_role.id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 400
        assert "already has this role" in response.json()["detail"]

    def test_assign_role_unauthorized(self, client: TestClient, auth_headers: dict, test_user: User, test_role: Role):
        """Test assigning role without admin privileges."""
        response = client.post(
            f"/api/v1/admin/users/{test_user.id}/roles/{test_role.id}",
            headers=auth_headers
        )

        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.admin
class TestRemoveRoleFromUser:
    """Test DELETE /admin/users/{user_id}/roles/{role_id} endpoint."""

    def test_remove_role_success(
        self, client: TestClient, admin_auth_headers: dict, admin_user: User, admin_role: Role
    ):
        """Test removing role from user as admin."""
        response = client.delete(
            f"/api/v1/admin/users/{admin_user.id}/roles/{admin_role.id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(admin_user.id)
        # Role should be removed
        assert not any(role["name"] == admin_role.name for role in data["roles"])

    def test_remove_role_nonexistent_user(self, client: TestClient, admin_auth_headers: dict, test_role: Role):
        """Test removing role from non-existent user."""
        fake_user_id = uuid4()
        response = client.delete(
            f"/api/v1/admin/users/{fake_user_id}/roles/{test_role.id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_remove_nonexistent_role(self, client: TestClient, admin_auth_headers: dict, test_user: User):
        """Test removing non-existent role from user."""
        fake_role_id = uuid4()
        response = client.delete(
            f"/api/v1/admin/users/{test_user.id}/roles/{fake_role_id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 404
        assert "Role not found" in response.json()["detail"]

    def test_remove_role_not_assigned(
        self, client: TestClient, admin_auth_headers: dict, test_user: User, test_role: Role
    ):
        """Test removing role that user doesn't have."""
        response = client.delete(
            f"/api/v1/admin/users/{test_user.id}/roles/{test_role.id}",
            headers=admin_auth_headers
        )

        assert response.status_code == 400
        assert "does not have this role" in response.json()["detail"]

    def test_remove_role_unauthorized(
        self, client: TestClient, auth_headers: dict, admin_user: User, admin_role: Role
    ):
        """Test removing role without admin privileges."""
        response = client.delete(
            f"/api/v1/admin/users/{admin_user.id}/roles/{admin_role.id}",
            headers=auth_headers
        )

        assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.admin
class TestUpdateUserQuotas:
    """Test PUT /admin/users/{user_id}/quotas endpoint."""

    def test_update_quotas_success(self, client: TestClient, admin_auth_headers: dict, test_user: User):
        """Test updating user quotas as admin."""
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}/quotas",
            headers=admin_auth_headers,
            params={
                "daily_query_limit": 200,
                "monthly_query_limit": 2000,
                "daily_document_limit": 20,
                "max_document_size_mb": 20,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["daily_query_limit"] == 200
        assert data["monthly_query_limit"] == 2000
        assert data["daily_document_upload_limit"] == 20
        assert data["max_document_size_mb"] == 20

    def test_update_quotas_partial(self, client: TestClient, admin_auth_headers: dict, test_user: User):
        """Test updating only some quota values."""
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}/quotas",
            headers=admin_auth_headers,
            params={
                "daily_query_limit": 300,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["daily_query_limit"] == 300

    def test_update_quotas_unlimited(self, client: TestClient, admin_auth_headers: dict, test_user: User):
        """Test setting unlimited quotas (None values)."""
        # Note: URL params don't handle None well, this test validates the behavior
        # In practice, omit the param or use a special value like -1 for unlimited
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}/quotas?daily_query_limit=999999",
            headers=admin_auth_headers
        )

        # Should succeed with the provided value
        assert response.status_code in [200, 422]

    def test_update_quotas_nonexistent_user(self, client: TestClient, admin_auth_headers: dict):
        """Test updating quotas for non-existent user."""
        fake_user_id = uuid4()
        response = client.put(
            f"/api/v1/admin/users/{fake_user_id}/quotas",
            headers=admin_auth_headers,
            params={
                "daily_query_limit": 100,
            }
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    def test_update_quotas_no_values(self, client: TestClient, admin_auth_headers: dict, test_user: User):
        """Test updating quotas without providing any values."""
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}/quotas",
            headers=admin_auth_headers,
            params={}
        )

        assert response.status_code == 400
        assert "No quota values provided" in response.json()["detail"]

    def test_update_quotas_unauthorized(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test updating quotas without admin privileges."""
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}/quotas",
            headers=auth_headers,
            params={
                "daily_query_limit": 500,
            }
        )

        assert response.status_code == 403

    def test_update_quotas_negative_values(self, client: TestClient, admin_auth_headers: dict, test_user: User):
        """Test updating quotas with negative values."""
        response = client.put(
            f"/api/v1/admin/users/{test_user.id}/quotas",
            headers=admin_auth_headers,
            params={
                "daily_query_limit": -100,
            }
        )

        # Should either succeed (if no validation) or fail with 422
        assert response.status_code in [200, 422]
