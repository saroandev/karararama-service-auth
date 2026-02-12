"""
Pydantic schemas for organization.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class OrganizationBase(BaseModel):
    """Base organization schema."""
    name: str


class OrganizationCreate(OrganizationBase):
    """Organization creation schema."""
    owner_email: str
    organization_type: Optional[str] = None  # "law-firm", "legal-department", "other"
    organization_size: Optional[str] = None  # "1-9", "10-49", "50-200", "200+"
    description: Optional[str] = None


class OrganizationUpdate(BaseModel):
    """Organization update schema."""
    name: Optional[str] = None
    is_active: Optional[bool] = None


class OrganizationResponse(OrganizationBase):
    """Organization response schema."""
    id: UUID
    owner_id: Optional[UUID]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrganizationWithStats(OrganizationResponse):
    """Organization with statistics."""
    total_members: int
    total_queries: int
    total_documents: int


class OrganizationMemberResponse(BaseModel):
    """Schema for organization member information."""
    id: UUID
    first_name: str
    last_name: str
    email: str
    role: str  # Role name within the organization
    role_display_name: str  # Turkish display name for the role
    is_owner: bool
    is_verified: bool
    joined_at: datetime

    class Config:
        from_attributes = True


class PendingInvitationResponse(BaseModel):
    """Schema for pending invitation information."""
    id: UUID
    email: str
    role: str
    role_display_name: str
    invited_by_name: str
    invited_by_email: str
    expires_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class OrganizationMembersResponse(BaseModel):
    """Schema for organization members list with pending invitations."""
    members: list[OrganizationMemberResponse]
    pending_invitations: list[PendingInvitationResponse]
    total_members: int
    total_pending: int
