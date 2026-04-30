"""
CRUD operations for UYAP accounts.

UYAP accounts are organization-level resources. Uniqueness is enforced on
(org_id, uyap_account_name); the creator is recorded for audit but is not
part of the key, so any member of the org can add or remove entries.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.uyap_account import UyapAccount


class CRUDUyapAccount:
    """CRUD operations for UYAP accounts."""

    async def create(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
        uyap_account_name: str,
        created_by_user_id: UUID,
    ) -> Optional[UyapAccount]:
        """
        Create a new UYAP account in the organization.

        Returns the created UyapAccount, or None if an account with the same
        name already exists in this organization.
        """
        try:
            uyap_account = UyapAccount(
                org_id=org_id,
                uyap_account_name=uyap_account_name,
                created_by_user_id=created_by_user_id,
            )
            db.add(uyap_account)
            await db.commit()
            await db.refresh(uyap_account)
            return uyap_account
        except IntegrityError:
            await db.rollback()
            return None

    async def get_by_org(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
    ) -> List[UyapAccount]:
        """List all UYAP accounts connected within an organization."""
        result = await db.execute(
            select(UyapAccount)
            .where(UyapAccount.org_id == org_id)
            .order_by(UyapAccount.created_at.desc())
        )
        return list(result.scalars().all())

    async def get(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
        uyap_account_name: str,
    ) -> Optional[UyapAccount]:
        """Get a specific UYAP account in an organization."""
        result = await db.execute(
            select(UyapAccount)
            .where(
                and_(
                    UyapAccount.org_id == org_id,
                    UyapAccount.uyap_account_name == uyap_account_name,
                )
            )
        )
        return result.scalar_one_or_none()

    async def delete(
        self,
        db: AsyncSession,
        *,
        org_id: UUID,
        uyap_account_name: str,
    ) -> bool:
        """Delete a UYAP account from the organization. Returns True if deleted."""
        uyap_account = await self.get(
            db, org_id=org_id, uyap_account_name=uyap_account_name
        )
        if uyap_account:
            await db.delete(uyap_account)
            await db.commit()
            return True
        return False


uyap_account_crud = CRUDUyapAccount()
