"""
CRUD operations for Organization model.
"""
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models import Organization, User, UsageLog
from app.schemas.organization import OrganizationCreate, OrganizationUpdate


class CRUDOrganization(CRUDBase[Organization, OrganizationCreate, OrganizationUpdate]):
    """CRUD operations for Organization model."""

    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str
    ) -> Optional[Organization]:
        """
        Get organization by name.

        Args:
            db: Database session
            name: Organization name

        Returns:
            Organization or None
        """
        stmt = select(Organization).where(Organization.name == name)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_members(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID
    ) -> List[User]:
        """
        Get all members of an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            List of users
        """
        stmt = select(User).where(User.organization_id == organization_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_member_count(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID
    ) -> int:
        """
        Get total number of members in an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            Number of members
        """
        stmt = select(func.count(User.id)).where(User.organization_id == organization_id)
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_organization_stats(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID
    ) -> dict:
        """
        Get statistics for an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            Dictionary with total_members, total_queries, total_documents
        """
        # Get member count
        member_count = await self.get_member_count(db, organization_id=organization_id)

        # Get total queries and documents from users
        stmt = select(
            func.sum(User.total_queries_used).label("total_queries"),
            func.sum(User.total_documents_uploaded).label("total_documents")
        ).where(User.organization_id == organization_id)

        result = await db.execute(stmt)
        row = result.one()

        return {
            "total_members": member_count,
            "total_queries": row.total_queries or 0,
            "total_documents": row.total_documents or 0
        }


# Global instance
organization_crud = CRUDOrganization(Organization)
