"""
Pydantic schemas for User model.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# Base schemas
class UserBase(BaseModel):
    """Base user schema with common fields."""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")


class UserUpdate(BaseModel):
    """Schema for updating user information."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None


class UserUpdatePassword(BaseModel):
    """Schema for updating user password."""
    old_password: str
    new_password: str = Field(..., min_length=6)
    new_password_confirm: str = Field(..., min_length=6)

    @property
    def passwords_match(self) -> bool:
        """Check if new passwords match."""
        return self.new_password == self.new_password_confirm


# Response schemas
class UserResponse(UserBase):
    """User response schema (without sensitive data)."""
    id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    # Organization and Roles
    organization_id: Optional[UUID] = None
    organization: Optional['OrganizationResponse'] = None
    roles: List['RoleResponse'] = []

    # Quota information
    daily_query_limit: Optional[int] = None
    monthly_query_limit: Optional[int] = None
    daily_document_upload_limit: Optional[int] = None
    max_document_size_mb: int

    total_queries_used: int
    total_documents_uploaded: int

    class Config:
        from_attributes = True


class UserWithRoles(UserResponse):
    """User response with roles included."""
    roles: List['RoleResponse'] = []

    class Config:
        from_attributes = True


class UserDeleteResponse(BaseModel):
    """Response for user deletion."""
    id: UUID
    email: str
    message: str = "User deleted successfully"

    class Config:
        from_attributes = True


# Import RoleResponse and OrganizationResponse for type hints
from app.schemas.role import RoleResponse
from app.schemas.organization import OrganizationResponse
UserResponse.model_rebuild()
UserWithRoles.model_rebuild()