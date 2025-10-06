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
    owner_id: Optional[UUID] = None


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
