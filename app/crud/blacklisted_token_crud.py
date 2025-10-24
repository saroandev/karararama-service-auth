"""
CRUD operations for blacklisted tokens.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
import hashlib

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.blacklisted_token import BlacklistedToken


class CRUDBlacklistedToken:
    """CRUD operations for blacklisted tokens."""

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def add_to_blacklist(
        self,
        db: AsyncSession,
        token: str,
        user_id: UUID,
        expires_at: datetime,
        reason: str = "logout"
    ) -> BlacklistedToken:
        """
        Add an access token to the blacklist.

        Args:
            db: Database session
            token: Raw access token (will be hashed)
            user_id: User ID who owns this token
            expires_at: Token expiration timestamp
            reason: Reason for blacklisting (default: "logout")

        Returns:
            Created blacklisted token record
        """
        token_hash = self.hash_token(token)

        db_token = BlacklistedToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            reason=reason
        )
        db.add(db_token)
        await db.commit()
        await db.refresh(db_token)
        return db_token

    async def is_blacklisted(
        self,
        db: AsyncSession,
        token: str
    ) -> bool:
        """
        Check if an access token is blacklisted.

        Args:
            db: Database session
            token: Raw access token

        Returns:
            True if token is blacklisted, False otherwise
        """
        token_hash = self.hash_token(token)
        result = await db.execute(
            select(BlacklistedToken).where(
                BlacklistedToken.token_hash == token_hash
            )
        )
        blacklisted_token = result.scalar_one_or_none()
        return blacklisted_token is not None

    async def cleanup_expired(
        self,
        db: AsyncSession
    ) -> int:
        """
        Delete expired tokens from blacklist.

        Tokens that have naturally expired no longer need to be in the blacklist.

        Args:
            db: Database session

        Returns:
            Number of tokens deleted
        """
        result = await db.execute(
            delete(BlacklistedToken).where(
                BlacklistedToken.expires_at < datetime.utcnow()
            )
        )
        await db.commit()
        return result.rowcount


blacklisted_token_crud = CRUDBlacklistedToken()
