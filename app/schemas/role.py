"""
Pydantic schemas for Role model.
"""
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class RoleBase(BaseModel):
    """Base role schema."""
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating a new role."""
    default_daily_query_limit: Optional[int] = None
    default_monthly_query_limit: Optional[int] = None
    default_daily_document_limit: Optional[int] = None
    default_max_document_size_mb: int = 10


class RoleUpdate(BaseModel):
    """Schema for updating a role."""
    name: Optional[str] = None
    description: Optional[str] = None
    default_daily_query_limit: Optional[int] = None
    default_monthly_query_limit: Optional[int] = None
    default_daily_document_limit: Optional[int] = None
    default_max_document_size_mb: Optional[int] = None


class RoleResponse(RoleBase):
    """Role response schema."""
    id: UUID
    default_daily_query_limit: Optional[int] = None
    default_monthly_query_limit: Optional[int] = None
    default_daily_document_limit: Optional[int] = None
    default_max_document_size_mb: int

    class Config:
        from_attributes = True


class RoleWithPermissions(RoleResponse):
    """Role response with permissions included."""
    permissions: List['PermissionResponse'] = []

    class Config:
        from_attributes = True


# Import PermissionResponse for type hint
from app.schemas.permission import PermissionResponse
RoleWithPermissions.model_rebuild()