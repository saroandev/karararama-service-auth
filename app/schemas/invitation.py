"""
Pydantic schemas for invitation.
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.invitation import InvitationStatus


class InvitationBase(BaseModel):
    """Base invitation schema."""
    email: EmailStr
    role: str = Field(default="member", description="Role to assign (member, admin, owner)")


class InvitationCreate(InvitationBase):
    """Invitation creation schema."""
    organization_id: UUID


class InvitationBatchCreate(BaseModel):
    """Schema for creating multiple invitations."""
    emails: List[EmailStr] = Field(..., min_items=1, max_items=10, description="List of emails to invite (max 10)")
    role: str = Field(default="member", description="Role to assign to all invitees")


class InvitationAccept(BaseModel):
    """Schema for accepting an invitation."""
    token: str


class InvitationResponse(InvitationBase):
    """Invitation response schema."""
    id: UUID
    organization_id: UUID
    invited_by_user_id: UUID
    token: str
    status: InvitationStatus
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InvitationPublicResponse(BaseModel):
    """Public invitation response (without sensitive fields)."""
    email: EmailStr
    organization_id: UUID
    role: str
    status: InvitationStatus
    expires_at: datetime

    class Config:
        from_attributes = True
