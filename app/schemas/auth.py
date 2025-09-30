"""
Pydantic schemas for authentication.
"""
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload schema."""
    sub: UUID  # user_id
    email: str
    roles: List[str] = []
    permissions: List[dict] = []
    quotas: Optional[dict] = None
    exp: int
    iat: int
    type: str  # 'access' or 'refresh'


class RefreshTokenRequest(BaseModel):
    """Refresh token request schema."""
    refresh_token: str