"""
Schemas for OrganizationMember operations.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationMembershipBase(BaseModel):
    """Base schema for organization membership."""
    role: str = Field(..., description="User's role in the organization")
    is_primary: bool = Field(False, description="Whether this is the user's primary organization")


class OrganizationMembershipResponse(OrganizationMembershipBase):
    """Response schema for organization membership."""
    id: UUID
    user_id: UUID
    organization_id: UUID
    joined_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserOrganizationResponse(BaseModel):
    """Response schema for user's organization membership with org details."""
    id: UUID = Field(..., description="Membership ID")
    organization_id: UUID
    organization_name: str
    organization_type: Optional[str] = None
    organization_size: Optional[str] = None
    role: str = Field(..., description="User's role in this organization")
    role_display_name: str = Field(..., description="Localized role name")
    is_primary: bool = Field(..., description="Whether this is user's active organization")
    is_owner: bool = Field(..., description="Whether user owns this organization")
    joined_at: datetime

    class Config:
        from_attributes = True


class UserOrganizationsListResponse(BaseModel):
    """Response schema for listing all user's organizations."""
    organizations: list[UserOrganizationResponse]
    primary_organization_id: Optional[UUID] = None
    owned_organization_id: Optional[UUID] = None


class SetPrimaryOrganizationRequest(BaseModel):
    """Request schema for setting primary organization."""
    pass  # Organization ID comes from path parameter


class SetPrimaryOrganizationResponse(BaseModel):
    """Response schema for setting primary organization."""
    message: str
    organization_id: UUID
    organization_name: str
