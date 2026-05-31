"""
CRUD operations for Invitation model.
"""
from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud.base import CRUDBase
from app.models import Invitation
from app.models.invitation import InvitationStatus
from app.schemas.invitation import InvitationCreate, InvitationResponse


class CRUDInvitation(CRUDBase[Invitation, InvitationCreate, InvitationResponse]):
    """CRUD operations for Invitation model."""

    async def get_by_token(
        self,
        db: AsyncSession,
        *,
        token: str
    ) -> Optional[Invitation]:
        """
        Get invitation by token.

        Args:
            db: Database session
            token: Invitation token

        Returns:
            Invitation or None
        """
        stmt = select(Invitation).where(Invitation.token == token)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_and_org(
        self,
        db: AsyncSession,
        *,
        email: str,
        organization_id: UUID
    ) -> Optional[Invitation]:
        """
        Get pending invitation by email and organization.

        Args:
            db: Database session
            email: Email address
            organization_id: Organization ID

        Returns:
            Invitation or None
        """
        stmt = select(Invitation).where(
            and_(
                Invitation.email == email,
                Invitation.organization_id == organization_id,
                Invitation.status == InvitationStatus.PENDING
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_organization(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        status: Optional[InvitationStatus] = None
    ) -> List[Invitation]:
        """
        Get all invitations for an organization.

        Args:
            db: Database session
            organization_id: Organization ID
            status: Optional status filter

        Returns:
            List of invitations
        """
        conditions = [Invitation.organization_id == organization_id]
        if status:
            conditions.append(Invitation.status == status)

        stmt = select(Invitation).where(and_(*conditions))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create_with_token(
        self,
        db: AsyncSession,
        *,
        email: str,
        organization_id: UUID,
        invited_by_user_id: UUID,
        role: str = "member",
        muvekkil_id: Optional[UUID] = None,
        portal_role: Optional[str] = None,
        expires_in_days: Optional[int] = None,
    ) -> Invitation:
        """Create invitation with auto-generated token.

        Org-level invite (legacy): omit `muvekkil_id` / `portal_role`.
        Portal-scoped invite:       set both — `role` is preserved for
        the org-level fallback but `portal_role` drives membership on
        accept.
        """
        if expires_in_days is None:
            expires_in_days = settings.INVITATION_EXPIRE_DAYS

        token = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

        invitation = Invitation(
            email=email,
            organization_id=organization_id,
            invited_by_user_id=invited_by_user_id,
            role=role,
            muvekkil_id=muvekkil_id,
            portal_role=portal_role,
            token=token,
            status=InvitationStatus.PENDING,
            expires_at=expires_at,
        )

        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)
        return invitation

    async def mark_accepted(
        self,
        db: AsyncSession,
        *,
        invitation: Invitation
    ) -> Invitation:
        """
        Mark invitation as accepted.

        Args:
            db: Database session
            invitation: Invitation to mark as accepted

        Returns:
            Updated invitation
        """
        invitation.status = InvitationStatus.ACCEPTED
        invitation.accepted_at = datetime.utcnow()

        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)
        return invitation

    async def mark_expired(
        self,
        db: AsyncSession,
        *,
        invitation: Invitation
    ) -> Invitation:
        """
        Mark a single invitation as expired.

        Args:
            db: Database session
            invitation: Invitation to mark as expired

        Returns:
            Updated invitation
        """
        invitation.status = InvitationStatus.EXPIRED

        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)
        return invitation

    async def mark_revoked(
        self,
        db: AsyncSession,
        *,
        invitation: Invitation
    ) -> Invitation:
        """
        Mark invitation as revoked.

        Args:
            db: Database session
            invitation: Invitation to revoke

        Returns:
            Updated invitation
        """
        invitation.status = InvitationStatus.REVOKED

        db.add(invitation)
        await db.commit()
        await db.refresh(invitation)
        return invitation

    async def cleanup_expired(
        self,
        db: AsyncSession
    ) -> int:
        """
        Mark all expired pending invitations as expired.

        Args:
            db: Database session

        Returns:
            Number of invitations marked as expired
        """
        now = datetime.utcnow()

        stmt = select(Invitation).where(
            and_(
                Invitation.status == InvitationStatus.PENDING,
                Invitation.expires_at < now
            )
        )
        result = await db.execute(stmt)
        expired_invitations = result.scalars().all()

        count = 0
        for invitation in expired_invitations:
            invitation.status = InvitationStatus.EXPIRED
            db.add(invitation)
            count += 1

        if count > 0:
            await db.commit()

        return count


# Create singleton instance
invitation_crud = CRUDInvitation(Invitation)
