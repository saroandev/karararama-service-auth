"""
CRUD operations for UETS accounts.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.uets_account import UetsAccount


class CRUDUetsAccount:
    """CRUD operations for UETS accounts."""

    async def create(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
        user_id: UUID,
        uets_account_name: str
    ) -> Optional[UetsAccount]:
        """
        Create a new UETS account connection.

        Args:
            db: Database session
            org_id: Organization ID
            user_id: User ID
            uets_account_name: UETS account name

        Returns:
            Created UetsAccount instance or None if already exists
        """
        try:
            uets_account = UetsAccount(
                org_id=org_id,
                user_id=user_id,
                uets_account_name=uets_account_name
            )
            db.add(uets_account)
            await db.commit()
            await db.refresh(uets_account)
            return uets_account
        except IntegrityError:
            await db.rollback()
            return None

    async def get_by_user(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
        user_id: UUID
    ) -> List[UetsAccount]:
        """
        Get all UETS accounts for a user within their organization.

        Args:
            db: Database session
            org_id: Organization ID
            user_id: User ID

        Returns:
            List of UetsAccount instances
        """
        result = await db.execute(
            select(UetsAccount)
            .where(
                and_(
                    UetsAccount.org_id == org_id,
                    UetsAccount.user_id == user_id
                )
            )
            .order_by(UetsAccount.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
        user_id: UUID,
        uets_account_name: str
    ) -> Optional[UetsAccount]:
        """
        Get a specific UETS account.

        Args:
            db: Database session
            org_id: Organization ID
            user_id: User ID
            uets_account_name: UETS account name

        Returns:
            UetsAccount instance or None if not found
        """
        result = await db.execute(
            select(UetsAccount)
            .where(
                and_(
                    UetsAccount.org_id == org_id,
                    UetsAccount.user_id == user_id,
                    UetsAccount.uets_account_name == uets_account_name
                )
            )
        )
        return result.scalar_one_or_none()

    async def delete(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
        user_id: UUID,
        uets_account_name: str
    ) -> bool:
        """
        Delete a UETS account connection.

        Args:
            db: Database session
            org_id: Organization ID
            user_id: User ID
            uets_account_name: UETS account name

        Returns:
            True if deleted, False if not found
        """
        uets_account = await self.get(
            db,
            org_id=org_id,
            user_id=user_id,
            uets_account_name=uets_account_name
        )
        if uets_account:
            await db.delete(uets_account)
            await db.commit()
            return True
        return False


# Global instance
uets_account_crud = CRUDUetsAccount()
