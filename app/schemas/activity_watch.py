"""
Pydantic schemas for Activity Watch authentication.
"""
from pydantic import BaseModel, EmailStr


class ActivityWatchLoginRequest(BaseModel):
    """Activity Watch login request schema."""
    email: EmailStr
    password: str


class ActivityWatchTokenResponse(BaseModel):
    """Activity Watch token response schema."""
    token: str
    token_type: str = "activity_watch"

    class Config:
        json_schema_extra = {
            "example": {
                "token": "aw_a1b2c3d4e5f6...",
                "token_type": "activity_watch"
            }
        }
