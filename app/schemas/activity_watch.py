"""
Pydantic schemas for Activity Watch authentication.
"""
from pydantic import BaseModel, EmailStr, Field


class ActivityWatchLoginRequest(BaseModel):
    """Activity Watch login request schema."""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123"
            }
        }


class ActivityWatchTokenResponse(BaseModel):
    """Activity Watch token response schema."""
    token: str = Field(..., description="Long-lived Activity Watch token")
    token_type: str = Field(default="activity_watch", description="Token type identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "token": "aw_a1b2c3d4e5f6...",
                "token_type": "activity_watch"
            }
        }


class ActivityWatchVerifyResponse(BaseModel):
    """Activity Watch token verification response schema."""
    is_active: bool = Field(..., description="Whether the user account is active")

    class Config:
        json_schema_extra = {
            "example": {
                "is_active": True
            }
        }


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    detail: str = Field(..., description="Error message")

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Email veya şifre hatalı"
            }
        }
