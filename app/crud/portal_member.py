"""
CRUD for PortalMember.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import PortalMember


class CRUDPortalMember:
    """CRUD operations for PortalMember."""

    async def get(
        self, db: AsyncSession, *, id: UUID
    ) -> Optional[PortalMember]:
        stmt = select(PortalMember).where(PortalMember.id == id).options(
            selectinload(PortalMember.user)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get_membership(
        self, db: AsyncSession, *, muvekkil_id: UUID, user_id: UUID
    ) -> Optional[PortalMember]:
        """Look up the unique (muvekkil, user) pair."""
        stmt = select(PortalMember).where(
            PortalMember.muvekkil_id == muvekkil_id,
            PortalMember.user_id == user_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def list_by_portal(
        self,
        db: AsyncSession,
        *,
        muvekkil_id: UUID,
        active_only: bool = True,
    ) -> List[PortalMember]:
        stmt = (
            select(PortalMember)
            .where(PortalMember.muvekkil_id == muvekkil_id)
            .options(selectinload(PortalMember.user))
        )
        if active_only:
            stmt = stmt.where(PortalMember.is_active.is_(True))
        stmt = stmt.order_by(PortalMember.joined_at.asc())
        return list((await db.execute(stmt)).scalars().all())

    async def list_active_by_user(
        self, db: AsyncSession, *, user_id: UUID
    ) -> List[PortalMember]:
        """All portals a user is currently active in. Used by Guest user
        flows (post-login portal list) and by JWT portals[] claim."""
        stmt = (
            select(PortalMember)
            .where(
                PortalMember.user_id == user_id,
                PortalMember.is_active.is_(True),
            )
            .options(selectinload(PortalMember.muvekkil))
        )
        return list((await db.execute(stmt)).scalars().all())

    async def create(
        self,
        db: AsyncSession,
        *,
        muvekkil_id: UUID,
        user_id: UUID,
        portal_role: str,
        invited_by_user_id: Optional[UUID] = None,
    ) -> PortalMember:
        """Add (or reactivate) a membership.

        If a row already exists for (muvekkil, user) we flip is_active
        back on and update the role — preserves history and avoids the
        unique-constraint violation when a previously-removed user is
        re-added.
        """
        existing = await self.get_membership(
            db, muvekkil_id=muvekkil_id, user_id=user_id
        )
        if existing is not None:
            existing.is_active = True
            existing.portal_role = portal_role
            if invited_by_user_id is not None:
                existing.invited_by_user_id = invited_by_user_id
            db.add(existing)
            await db.flush()
            return existing

        member = PortalMember(
            muvekkil_id=muvekkil_id,
            user_id=user_id,
            portal_role=portal_role,
            is_active=True,
            invited_by_user_id=invited_by_user_id,
        )
        db.add(member)
        await db.flush()
        await db.refresh(member)
        return member

    async def update(
        self,
        db: AsyncSession,
        *,
        member: PortalMember,
        portal_role: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> PortalMember:
        if portal_role is not None:
            member.portal_role = portal_role
        if is_active is not None:
            member.is_active = is_active
        db.add(member)
        await db.flush()
        return member

    async def deactivate(
        self, db: AsyncSession, *, member: PortalMember
    ) -> PortalMember:
        """Remove access without dropping the row (preserves audit trail)."""
        member.is_active = False
        db.add(member)
        await db.flush()
        return member


portal_member_crud = CRUDPortalMember()
