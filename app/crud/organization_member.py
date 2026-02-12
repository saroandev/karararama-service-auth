"""
CRUD operations for OrganizationMember model.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import UUID as UUIDType
from app.models import OrganizationMember, User, Organization


class CRUDOrganizationMember:
    """CRUD operations for OrganizationMember model."""

    async def create(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID,
        role: str = "member",
        is_primary: bool = False
    ) -> OrganizationMember:
        """
        Create organization membership.

        Args:
            db: Database session
            user_id: User ID
            organization_id: Organization ID
            role: User's role in the organization (default: member)
            is_primary: Whether this is user's primary org (default: False)

        Returns:
            Created membership
        """
        membership = OrganizationMember(
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            is_primary=is_primary,
            joined_at=datetime.utcnow()
        )

        db.add(membership)
        await db.commit()
        await db.refresh(membership)
        return membership

    async def get_membership(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID
    ) -> Optional[OrganizationMember]:
        """
        Get specific membership.

        Args:
            db: Database session
            user_id: User ID
            organization_id: Organization ID

        Returns:
            Membership or None
        """
        stmt = select(OrganizationMember).where(
            and_(
                OrganizationMember.user_id == user_id,
                OrganizationMember.organization_id == organization_id
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_memberships(
        self,
        db: AsyncSession,
        *,
        user_id: UUID
    ) -> List[OrganizationMember]:
        """
        Get all organizations a user belongs to.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of memberships
        """
        stmt = select(OrganizationMember).where(
            OrganizationMember.user_id == user_id
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_org_members(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID
    ) -> List[OrganizationMember]:
        """
        Get all members of an organization.

        Args:
            db: Database session
            organization_id: Organization ID

        Returns:
            List of memberships
        """
        stmt = select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_role(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID,
        new_role: str
    ) -> Optional[OrganizationMember]:
        """
        Update user's role in organization.

        Args:
            db: Database session
            user_id: User ID
            organization_id: Organization ID
            new_role: New role to assign

        Returns:
            Updated membership or None
        """
        membership = await self.get_membership(
            db, user_id=user_id, organization_id=organization_id
        )

        if membership:
            membership.role = new_role
            db.add(membership)
            await db.commit()
            await db.refresh(membership)

        return membership

    async def set_primary(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID
    ) -> Optional[OrganizationMember]:
        """
        Set an organization as user's primary organization.
        This will set all other memberships to is_primary=False.

        Args:
            db: Database session
            user_id: User ID
            organization_id: Organization ID to set as primary

        Returns:
            Updated membership or None
        """
        # First, verify membership exists
        membership = await self.get_membership(
            db, user_id=user_id, organization_id=organization_id
        )

        if not membership:
            return None

        # Set all user's memberships to is_primary=False
        await self.clear_primary(db, user_id=user_id)

        # Set this membership as primary
        membership.is_primary = True
        db.add(membership)

        # Also update user's organization_id for backward compatibility
        stmt_user = select(User).where(User.id == user_id)
        result = await db.execute(stmt_user)
        user = result.scalar_one_or_none()
        if user:
            user.organization_id = organization_id
            db.add(user)

        await db.commit()
        await db.refresh(membership)
        return membership

    async def clear_primary(
        self,
        db: AsyncSession,
        *,
        user_id: UUID
    ) -> int:
        """
        Set all user's memberships to is_primary=False.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Number of memberships updated
        """
        stmt = (
            update(OrganizationMember)
            .where(OrganizationMember.user_id == user_id)
            .values(is_primary=False)
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount

    async def remove_member(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        organization_id: UUID
    ) -> bool:
        """
        Remove user from organization.

        Args:
            db: Database session
            user_id: User ID
            organization_id: Organization ID

        Returns:
            True if removed, False if not found
        """
        membership = await self.get_membership(
            db, user_id=user_id, organization_id=organization_id
        )

        if membership:
            await db.delete(membership)
            await db.commit()
            return True

        return False

    async def get_primary_membership(
        self,
        db: AsyncSession,
        *,
        user_id: UUID
    ) -> Optional[OrganizationMember]:
        """
        Get user's primary organization membership.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Primary membership or None
        """
        stmt = select(OrganizationMember).where(
            and_(
                OrganizationMember.user_id == user_id,
                OrganizationMember.is_primary == True
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


# Create singleton instance
organization_member_crud = CRUDOrganizationMember()
