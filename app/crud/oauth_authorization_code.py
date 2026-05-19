"""CRUD for short-lived OAuth authorization codes.

Codes are stored hashed; the plain value lives only in the user's browser
URL bar between /oauth/authorize → /oauth/token. Single-use is enforced
atomically at consume time.
"""
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_authorization_code import OAuthAuthorizationCode


CODE_TTL_SECONDS = 60


def hash_code(plain_code: str) -> str:
    """SHA-256 hex digest of the raw authorization code."""
    return hashlib.sha256(plain_code.encode("utf-8")).hexdigest()


class CRUDOAuthAuthorizationCode:
    async def mint(
        self,
        db: AsyncSession,
        *,
        plain_code: str,
        client_id: str,
        user_id: PyUUID,
        redirect_uri: str,
        code_challenge: str,
        code_challenge_method: str,
        scope: str,
        resource: str,
        ttl_seconds: int = CODE_TTL_SECONDS,
    ) -> OAuthAuthorizationCode:
        row = OAuthAuthorizationCode(
            code_hash=hash_code(plain_code),
            client_id=client_id,
            user_id=user_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            scope=scope,
            resource=resource,
            expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    async def get_by_plain(
        self, db: AsyncSession, plain_code: str
    ) -> Optional[OAuthAuthorizationCode]:
        result = await db.execute(
            select(OAuthAuthorizationCode).where(
                OAuthAuthorizationCode.code_hash == hash_code(plain_code)
            )
        )
        return result.scalar_one_or_none()

    async def consume(
        self, db: AsyncSession, plain_code: str
    ) -> Optional[OAuthAuthorizationCode]:
        """Look up and atomically mark used.

        Returns the row only if it was previously unused AND not expired.
        Callers MUST treat `None` as a hard reject (replay or expired).
        """
        row = await self.get_by_plain(db, plain_code)
        if row is None:
            return None
        if row.is_used or row.is_expired:
            return None
        row.used_at = datetime.utcnow()
        await db.commit()
        await db.refresh(row)
        return row


oauth_authorization_code_crud = CRUDOAuthAuthorizationCode()
