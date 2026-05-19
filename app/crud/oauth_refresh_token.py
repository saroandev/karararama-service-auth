"""CRUD for rotating OAuth refresh tokens."""
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID as PyUUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_refresh_token import OAuthRefreshToken


REFRESH_TTL_DAYS = 30


def hash_refresh_token(plain: str) -> str:
    """SHA-256 hex digest of the raw refresh token."""
    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


class CRUDOAuthRefreshToken:
    async def mint(
        self,
        db: AsyncSession,
        *,
        plain_token: str,
        client_id: str,
        user_id: PyUUID,
        scope: str,
        resource: str,
        ttl_days: int = REFRESH_TTL_DAYS,
    ) -> OAuthRefreshToken:
        row = OAuthRefreshToken(
            token_hash=hash_refresh_token(plain_token),
            client_id=client_id,
            user_id=user_id,
            scope=scope,
            resource=resource,
            expires_at=datetime.utcnow() + timedelta(days=ttl_days),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    async def get_by_plain(
        self, db: AsyncSession, plain_token: str
    ) -> Optional[OAuthRefreshToken]:
        result = await db.execute(
            select(OAuthRefreshToken).where(
                OAuthRefreshToken.token_hash == hash_refresh_token(plain_token)
            )
        )
        return result.scalar_one_or_none()

    async def revoke(
        self, db: AsyncSession, row: OAuthRefreshToken
    ) -> None:
        row.revoked_at = datetime.utcnow()
        await db.commit()

    async def rotate(
        self,
        db: AsyncSession,
        *,
        old_row: OAuthRefreshToken,
        new_plain_token: str,
    ) -> OAuthRefreshToken:
        """Revoke `old_row` and mint a fresh token bound to the same (user, client).

        Atomic: both changes commit together.
        """
        old_row.revoked_at = datetime.utcnow()
        new_row = OAuthRefreshToken(
            token_hash=hash_refresh_token(new_plain_token),
            client_id=old_row.client_id,
            user_id=old_row.user_id,
            scope=old_row.scope,
            resource=old_row.resource,
            expires_at=datetime.utcnow() + timedelta(days=REFRESH_TTL_DAYS),
        )
        db.add(new_row)
        await db.commit()
        await db.refresh(new_row)
        return new_row


oauth_refresh_token_crud = CRUDOAuthRefreshToken()
