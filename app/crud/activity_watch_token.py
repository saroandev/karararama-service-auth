"""
CRUD operations for Activity Watch tokens.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_watch_token import ActivityWatchToken
from app.core.security import aw_token_handler


class CRUDActivityWatchToken:
    """CRUD operations for Activity Watch tokens."""

    async def get_by_user_id(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> Optional[ActivityWatchToken]:
        """
        Get Activity Watch token by user ID.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            ActivityWatchToken instance or None if not found
        """
        result = await db.execute(
            select(ActivityWatchToken).where(ActivityWatchToken.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> tuple[str, ActivityWatchToken]:
        """
        Get existing Activity Watch token or create a new one for a user.

        Since each user can only have one token, this method will:
        - Return the existing token (decrypted) if one exists
        - Create a new token only if none exists

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Tuple of (plain_token, ActivityWatchToken instance)
            The plain_token should be returned to the user
        """
        # Check if user already has a token
        existing_token = await self.get_by_user_id(db, user_id)

        if existing_token:
            # Decrypt and return existing token
            plain_token = aw_token_handler.decrypt_token(existing_token.token_hash)
            # Update last_used_at
            existing_token.last_used_at = datetime.utcnow()
            db.add(existing_token)
            await db.commit()
            await db.refresh(existing_token)
            return plain_token, existing_token
        else:
            # Generate new token
            plain_token, encrypted_token = aw_token_handler.generate_token()

            # Create new token
            new_token = ActivityWatchToken(
                user_id=user_id,
                token_hash=encrypted_token,
                last_used_at=datetime.utcnow()
            )
            db.add(new_token)
            await db.commit()
            await db.refresh(new_token)
            return plain_token, new_token

    async def verify_token(
        self,
        db: AsyncSession,
        plain_token: str
    ) -> Optional[ActivityWatchToken]:
        """
        Verify an Activity Watch token and return the associated token record.

        This method checks all tokens in the database and verifies the plain token
        against their encrypted versions.

        Args:
            db: Database session
            plain_token: Plain text token from user

        Returns:
            ActivityWatchToken instance if token is valid, None otherwise
        """
        # Get all tokens (in production, you might want to optimize this)
        # For now, since we expect one token per user, this is acceptable
        result = await db.execute(select(ActivityWatchToken))
        all_tokens = result.scalars().all()

        for token in all_tokens:
            if aw_token_handler.verify_token(plain_token, token.token_hash):
                return token

        return None

    async def update_last_used(
        self,
        db: AsyncSession,
        token: ActivityWatchToken
    ) -> ActivityWatchToken:
        """
        Update the last_used_at timestamp for a token.

        Args:
            db: Database session
            token: ActivityWatchToken instance

        Returns:
            Updated ActivityWatchToken instance
        """
        token.update_last_used()
        db.add(token)
        await db.commit()
        await db.refresh(token)
        return token

    async def delete(
        self,
        db: AsyncSession,
        user_id: UUID
    ) -> bool:
        """
        Delete Activity Watch token for a user.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            True if token was deleted, False if not found
        """
        token = await self.get_by_user_id(db, user_id)
        if token:
            await db.delete(token)
            await db.commit()
            return True
        return False


# Instance to use in endpoints
activity_watch_token_crud = CRUDActivityWatchToken()
