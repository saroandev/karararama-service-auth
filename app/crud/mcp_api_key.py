"""
CRUD operations for MCP API keys.

Same hash-on-store pattern as RefreshToken: the raw key is never persisted,
only its SHA-256 hex digest. The raw value is returned to the caller exactly
once at creation time.
"""
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mcp_api_key import MCPApiKey


KEY_PREFIX = "od_mcp_"
KEY_RAW_BYTES = 32  # 32 random bytes → 43-char base64url body
PREFIX_VISIBLE_LEN = 12  # `od_mcp_` + 5 chars stored for UI display


class CRUDMcpApiKey:
    """CRUD operations for MCP API keys."""

    # ---- key generation / hashing ----

    @staticmethod
    def generate_raw_key() -> str:
        """Mint a new raw key: `od_mcp_<43 chars of base64url>`."""
        body = secrets.token_urlsafe(KEY_RAW_BYTES)
        return f"{KEY_PREFIX}{body}"

    @staticmethod
    def hash_key(raw_key: str) -> str:
        """SHA-256 hex digest. Constant length 64 chars."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @staticmethod
    def public_prefix(raw_key: str) -> str:
        """First N chars of the raw key, safe to surface in management UI."""
        return raw_key[:PREFIX_VISIBLE_LEN]

    # ---- writes ----

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        name: str,
        expires_at: Optional[datetime] = None,
    ) -> Tuple[MCPApiKey, str]:
        """Mint a new MCP API key.

        Returns (db_row, raw_key). The raw_key is shown to the user ONCE;
        only the hash is persisted.
        """
        raw_key = self.generate_raw_key()
        key_row = MCPApiKey(
            user_id=user_id,
            key_hash=self.hash_key(raw_key),
            key_prefix=self.public_prefix(raw_key),
            name=name,
            expires_at=expires_at,
        )
        db.add(key_row)
        await db.commit()
        await db.refresh(key_row)
        return key_row, raw_key

    async def revoke(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        key_id: UUID,
    ) -> bool:
        """Soft-delete a key. Returns True if the key existed & was revoked."""
        result = await db.execute(
            select(MCPApiKey).where(
                MCPApiKey.id == key_id,
                MCPApiKey.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if row is None or row.revoked_at is not None:
            return False
        row.revoked_at = datetime.utcnow()
        await db.commit()
        return True

    async def touch(self, db: AsyncSession, key_row: MCPApiKey) -> None:
        """Update last_used_at + bump usage_count after a successful exchange."""
        key_row.last_used_at = datetime.utcnow()
        key_row.usage_count = (key_row.usage_count or 0) + 1
        await db.commit()

    # ---- reads ----

    async def get_by_raw_key(
        self, db: AsyncSession, raw_key: str
    ) -> Optional[MCPApiKey]:
        """Look up a key row by its raw value (hashes on the way in)."""
        if not raw_key.startswith(KEY_PREFIX):
            return None
        result = await db.execute(
            select(MCPApiKey).where(MCPApiKey.key_hash == self.hash_key(raw_key))
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        include_revoked: bool = False,
    ) -> list[MCPApiKey]:
        """Return all keys owned by `user_id`, newest first."""
        stmt = select(MCPApiKey).where(MCPApiKey.user_id == user_id)
        if not include_revoked:
            stmt = stmt.where(MCPApiKey.revoked_at.is_(None))
        stmt = stmt.order_by(MCPApiKey.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_active_for_user(self, db: AsyncSession, user_id: UUID) -> int:
        """Count of non-revoked, non-expired keys (for max-keys-per-user cap)."""
        result = await db.execute(
            select(MCPApiKey).where(
                MCPApiKey.user_id == user_id,
                MCPApiKey.revoked_at.is_(None),
            )
        )
        rows = result.scalars().all()
        now = datetime.utcnow()
        return sum(1 for r in rows if r.expires_at is None or r.expires_at > now)


mcp_api_key_crud = CRUDMcpApiKey()
