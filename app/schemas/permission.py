"""
Pydantic schemas for Permission model.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class PermissionBase(BaseModel):
    """Base permission schema."""
    resource: str
    action: str
    description: Optional[str] = None


class PermissionCreate(PermissionBase):
    """Schema for creating a new permission."""
    pass


class PermissionUpdate(BaseModel):
    """Schema for updating a permission."""
    description: Optional[str] = None


class PermissionResponse(PermissionBase):
    """Permission response schema."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True