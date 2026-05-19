"""Integration tests for MCP API key endpoints.

Covers:
- POST /api/v1/mcp/keys — create (auth required)
- GET  /api/v1/mcp/keys — list
- DELETE /api/v1/mcp/keys/{id} — revoke
- POST /api/v1/mcp/exchange — API key → JWT
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.mcp_api_key import mcp_api_key_crud
from app.models import User


@pytest.mark.integration
class TestMCPKeyCreate:
    """POST /api/v1/mcp/keys."""

    def test_requires_authentication(self, client: TestClient):
        response = client.post("/api/v1/mcp/keys", json={"name": "Laptop"})
        assert response.status_code == 401

    def test_creates_key_and_returns_raw_once(
        self,
        client: TestClient,
        test_user: User,
        auth_headers: dict,
    ):
        response = client.post(
            "/api/v1/mcp/keys",
            json={"name": "My Laptop Claude"},
            headers=auth_headers,
        )
        assert response.status_code == 201
        body = response.json()
        # Raw key returned exactly once
        assert body["api_key"].startswith("od_mcp_")
        assert len(body["api_key"]) > 30
        # Metadata
        meta = body["metadata"]
        assert meta["name"] == "My Laptop Claude"
        assert meta["key_prefix"].startswith("od_mcp_")
        assert meta["is_active"] is True
        assert meta["usage_count"] == 0
        assert meta["revoked_at"] is None

    def test_rejects_empty_name(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/api/v1/mcp/keys",
            json={"name": ""},
            headers=auth_headers,
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestMCPKeyList:
    """GET /api/v1/mcp/keys."""

    def test_empty_initially(self, client: TestClient, auth_headers: dict):
        response = client.get("/api/v1/mcp/keys", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"keys": []}

    def test_lists_created_keys(self, client: TestClient, auth_headers: dict):
        client.post("/api/v1/mcp/keys", json={"name": "First"}, headers=auth_headers)
        client.post("/api/v1/mcp/keys", json={"name": "Second"}, headers=auth_headers)

        response = client.get("/api/v1/mcp/keys", headers=auth_headers)
        assert response.status_code == 200
        keys = response.json()["keys"]
        assert len(keys) == 2
        # Newest first
        names = [k["name"] for k in keys]
        assert names == ["Second", "First"]
        # No raw secret leaks
        for k in keys:
            assert "api_key" not in k
            assert "key_hash" not in k


@pytest.mark.integration
class TestMCPKeyRevoke:
    """DELETE /api/v1/mcp/keys/{id}."""

    def test_revokes_own_key(self, client: TestClient, auth_headers: dict):
        created = client.post(
            "/api/v1/mcp/keys", json={"name": "to-revoke"}, headers=auth_headers
        ).json()
        key_id = created["metadata"]["id"]

        del_resp = client.delete(f"/api/v1/mcp/keys/{key_id}", headers=auth_headers)
        assert del_resp.status_code == 204

        # Active list now empty
        listed = client.get("/api/v1/mcp/keys", headers=auth_headers).json()
        assert listed["keys"] == []

        # But still visible with include_revoked
        with_revoked = client.get(
            "/api/v1/mcp/keys?include_revoked=true", headers=auth_headers
        ).json()
        assert len(with_revoked["keys"]) == 1
        assert with_revoked["keys"][0]["revoked_at"] is not None
        assert with_revoked["keys"][0]["is_active"] is False

    def test_404_for_unknown_key(self, client: TestClient, auth_headers: dict):
        response = client.delete(
            "/api/v1/mcp/keys/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code == 404


@pytest.mark.integration
class TestMCPExchange:
    """POST /api/v1/mcp/exchange."""

    def test_exchanges_valid_key_for_jwt(
        self, client: TestClient, auth_headers: dict
    ):
        created = client.post(
            "/api/v1/mcp/keys", json={"name": "exchange-test"}, headers=auth_headers
        ).json()
        raw_key = created["api_key"]

        # Exchange uses the API key, not a JWT — so no auth_headers
        resp = client.post("/api/v1/mcp/exchange", json={"api_key": raw_key})
        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"]
        assert body["token_type"] == "bearer"
        # 15 minutes = 900s
        assert body["expires_in"] == 900

    def test_rejects_invalid_key(self, client: TestClient):
        resp = client.post(
            "/api/v1/mcp/exchange", json={"api_key": "od_mcp_garbage"}
        )
        assert resp.status_code == 401

    def test_rejects_revoked_key(
        self, client: TestClient, auth_headers: dict
    ):
        created = client.post(
            "/api/v1/mcp/keys", json={"name": "revoked"}, headers=auth_headers
        ).json()
        raw_key = created["api_key"]
        key_id = created["metadata"]["id"]
        client.delete(f"/api/v1/mcp/keys/{key_id}", headers=auth_headers)

        resp = client.post("/api/v1/mcp/exchange", json={"api_key": raw_key})
        assert resp.status_code == 401

    def test_exchange_updates_last_used_and_usage_count(
        self, client: TestClient, auth_headers: dict
    ):
        created = client.post(
            "/api/v1/mcp/keys", json={"name": "touch-test"}, headers=auth_headers
        ).json()
        raw_key = created["api_key"]

        # 1st exchange
        client.post("/api/v1/mcp/exchange", json={"api_key": raw_key})
        # 2nd exchange
        client.post("/api/v1/mcp/exchange", json={"api_key": raw_key})

        listed = client.get("/api/v1/mcp/keys", headers=auth_headers).json()
        meta = listed["keys"][0]
        assert meta["usage_count"] == 2
        assert meta["last_used_at"] is not None


@pytest.mark.integration
class TestCRUDHelpers:
    """Direct CRUD tests for hashing invariants."""

    @pytest.mark.asyncio
    async def test_raw_key_not_stored_anywhere(
        self, db_session: AsyncSession, test_user: User
    ):
        row, raw = await mcp_api_key_crud.create(
            db_session, user_id=test_user.id, name="hash-check"
        )
        await db_session.refresh(row)
        # The raw key must not equal the persisted hash
        assert row.key_hash != raw
        # SHA-256 hex length is 64
        assert len(row.key_hash) == 64
        # Prefix must be the first 12 chars of the raw key
        assert row.key_prefix == raw[:12]
        # Lookup by raw key works
        found = await mcp_api_key_crud.get_by_raw_key(db_session, raw)
        assert found is not None
        assert found.id == row.id
