"""
Pydantic schemas for authentication.
"""
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    needs_onboarding: Optional[bool] = None


class DataAccess(BaseModel):
    """Data access control schema."""
    own_data: bool = True
    shared_data: bool = False
    all_users_data: bool = False


class TokenPayload(BaseModel):
    """JWT token payload schema."""
    sub: UUID  # user_id (renamed from user_id for JWT standard)
    organization_id: Optional[UUID] = None
    email: str
    role: str = "member"  # Primary role: admin, member, viewer
    roles: List[str] = []  # All roles (for backward compatibility)
    permissions: List[dict] = []
    data_access: Optional[DataAccess] = None
    remaining_credits: Optional[int] = None
    quotas: Optional[dict] = None  # For backward compatibility
    exp: int
    iat: int
    type: str  # 'access' or 'refresh'


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema."""
    email: EmailStr


class ValidateResetTokenRequest(BaseModel):
    """Validate reset token request schema."""
    token: str = Field(..., min_length=1, description="Password reset token")


class ValidateResetTokenResponse(BaseModel):
    """Validate reset token response schema."""
    valid: bool
    email: Optional[str] = None
    error: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    """Reset password request schema."""
    token: str = Field(..., min_length=1, description="Password reset token")
    new_password: str = Field(..., min_length=6, description="New password (min 6 characters)")
    new_password_confirm: str = Field(..., min_length=6, description="Password confirmation")

    @validator('new_password_confirm')
    def passwords_match(cls, v, values):
        """Validate that passwords match."""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class ResetPasswordResponse(BaseModel):
    """Reset password response schema."""
    message: str