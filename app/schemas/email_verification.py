"""
Pydantic schemas for Email Verification.
"""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class SendVerificationEmailRequest(BaseModel):
    """Schema for sending verification email request."""
    email: EmailStr = Field(..., description="Email address to send verification code to")


class SendVerificationEmailResponse(BaseModel):
    """Schema for send verification email response."""
    success: bool
    message: str
    cooldown_remaining: Optional[int] = Field(None, description="Seconds remaining before can resend (if cooldown active)")


class VerifyEmailCodeRequest(BaseModel):
    """Schema for verifying email code request."""
    email: EmailStr = Field(..., description="Email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class VerifyEmailCodeResponse(BaseModel):
    """Schema for verify email code response."""
    success: bool
    message: str


class ResendVerificationEmailRequest(BaseModel):
    """Schema for resending verification email request."""
    email: EmailStr = Field(..., description="Email address to resend verification code to")


class ResendVerificationEmailResponse(BaseModel):
    """Schema for resend verification email response."""
    success: bool
    message: str
    cooldown_remaining: Optional[int] = Field(None, description="Seconds until can resend again")
    next_resend_time: Optional[int] = Field(None, description="Timestamp when next resend is allowed")
