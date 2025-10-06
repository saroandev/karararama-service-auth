"""
Pydantic schemas for Role model.
"""
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RoleBase(BaseModel):
    """Base role schema."""
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    """Schema for creating a new role."""
    default_daily_query_limit: Optional[int] = Field(None, ge=0, description="Daily query limit (must be >= 0, None = unlimited)")
    default_monthly_query_limit: Optional[int] = Field(None, ge=0, description="Monthly query limit (must be >= 0, None = unlimited)")
    default_daily_document_limit: Optional[int] = Field(None, ge=0, description="Daily document limit (must be >= 0, None = unlimited)")
    default_max_document_size_mb: int = Field(10, ge=1, le=100, description="Max document size in MB (1-100)")

    @field_validator('default_daily_query_limit', 'default_monthly_query_limit', 'default_daily_document_limit')
    @classmethod
    def validate_limits(cls, v):
        """Validate that limits are non-negative or None."""
        if v is not None and v < 0:
            raise ValueError('Limit must be non-negative or None (unlimited)')
        return v


class RoleUpdate(BaseModel):
    """Schema for updating a role."""
    name: Optional[str] = None
    description: Optional[str] = None
    default_daily_query_limit: Optional[int] = Field(None, ge=0, description="Daily query limit (must be >= 0, None = unlimited)")
    default_monthly_query_limit: Optional[int] = Field(None, ge=0, description="Monthly query limit (must be >= 0, None = unlimited)")
    default_daily_document_limit: Optional[int] = Field(None, ge=0, description="Daily document limit (must be >= 0, None = unlimited)")
    default_max_document_size_mb: Optional[int] = Field(None, ge=1, le=100, description="Max document size in MB (1-100)")

    @field_validator('default_daily_query_limit', 'default_monthly_query_limit', 'default_daily_document_limit')
    @classmethod
    def validate_limits(cls, v):
        """Validate that limits are non-negative or None."""
        if v is not None and v < 0:
            raise ValueError('Limit must be non-negative or None (unlimited)')
        return v


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