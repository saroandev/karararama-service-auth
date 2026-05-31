"""
Pydantic schemas for PortalMember.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.models.portal_member import PortalRole


class PortalMemberBase(BaseModel):
    portal_role: PortalRole


class PortalMemberCreate(PortalMemberBase):
    """Add an existing user to a portal directly (no invitation).

    Used when the host org already has the user's account and just
    wants to grant portal access. For onboarding a brand-new client
    user, use the invitation endpoint instead.
    """
    user_id: UUID


class PortalMemberUpdate(BaseModel):
    portal_role: Optional[PortalRole] = None
    is_active: Optional[bool] = None


class PortalMemberInviteRequest(BaseModel):
    """Send a portal-scoped invitation by email.

    If a user already exists for the email, accepting just adds them to
    the portal_members table. Otherwise the accept flow provisions a
    Guest user (user_type='guest') and pins them to this portal only.
    """
    email: EmailStr
    portal_role: PortalRole

    @field_validator("portal_role", mode="before")
    @classmethod
    def coerce_role(cls, v):
        # Allow plain strings from the FE without forcing them to
        # know the enum class.
        if isinstance(v, str):
            return v.lower()
        return v


class PortalMemberUserSummary(BaseModel):
    """Minimal user info embedded in member responses."""
    id: UUID
    email: str
    first_name: str
    last_name: str
    user_type: str

    class Config:
        from_attributes = True


class PortalMemberResponse(BaseModel):
    id: UUID
    muvekkil_id: UUID
    user_id: UUID
    portal_role: PortalRole
    is_active: bool
    joined_at: datetime
    invited_by_user_id: Optional[UUID] = None
    user: Optional[PortalMemberUserSummary] = None

    class Config:
        from_attributes = True


class PortalPendingInvite(BaseModel):
    """Portal-scoped invitation still awaiting acceptance."""
    id: UUID
    email: str
    portal_role: str
    invited_by_user_id: UUID
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class PortalMembersListResponse(BaseModel):
    members: List[PortalMemberResponse]
    pending_invitations: List[PortalPendingInvite]
    total_members: int
    total_pending: int
