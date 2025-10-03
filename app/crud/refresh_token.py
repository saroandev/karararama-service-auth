"""
CRUD operations for refresh tokens.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import settings
from app.models.refresh_token import RefreshToken


class CRUDRefreshToken:
    """CRUD operations for refresh tokens."""

    @staticmethod
    def hash_token(token: str) -> str:
        """Hash a token for secure storage."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def create(
        self,
        db: AsyncSession,
        user_id: UUID,
        token: str,
        device_info: Optional[dict] = None
    ) -> RefreshToken:
        """
        Create a new refresh token.

        Args:
            db: Database session
            user_id: User ID
            token: Raw refresh token (will be hashed)
            device_info: Optional device information

        Returns:
            Created refresh token
        """
        token_hash = self.hash_token(token)
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

        db_token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            device_info=device_info
        )
        db.add(db_token)
        await db.commit()
        await db.refresh(db_token)
        return db_token

    async def get_by_token(
        self,
        db: AsyncSession,
        token: str
    ) -> Optional[RefreshToken]:
        """
        Get refresh token by token value.

        Args:
            db: Database session
            token: Raw refresh token

        Returns:
            RefreshToken if found, None otherwise
        """
        token_hash = self.hash_token(token)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(
        self,
        db: AsyncSession,
        token: str
    ) -> bool:
        """
        Revoke a refresh token.

        Args:
            db: Database session
            token: Raw refresh token

        Returns:
            True if revoked, False if not found
        """
        db_token = await self.get_by_token(db, token)
        if not db_token:
            return False

        db_token.revoked_at = datetime.utcnow()
        await db.commit()
        return True

    async def revoke_all_user_tokens(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> int:
        """
        Revoke all refresh tokens for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Number of tokens revoked
        """
        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None)
            )
        )
        tokens = result.scalars().all()

        count = 0
        for token in tokens:
            token.revoked_at = datetime.utcnow()
            count += 1

        await db.commit()
        return count

    async def cleanup_expired(
        self,
        db: AsyncSession
    ) -> int:
        """
        Delete expired and revoked tokens.

        Args:
            db: Database session

        Returns:
            Number of tokens deleted
        """
        result = await db.execute(
            select(RefreshToken).where(
                (RefreshToken.expires_at < datetime.utcnow()) |
                (RefreshToken.revoked_at.is_not(None))
            )
        )
        tokens = result.scalars().all()

        count = len(tokens)
        for token in tokens:
            await db.delete(token)

        await db.commit()
        return count


refresh_token_crud = CRUDRefreshToken()
