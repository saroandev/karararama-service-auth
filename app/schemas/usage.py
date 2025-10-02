"""
Pydantic schemas for usage tracking.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class UsageConsumeRequest(BaseModel):
    """Request schema for consuming service usage."""

    user_id: UUID = Field(..., description="User ID from JWT token (sub field)")
    service_type: str = Field(..., description="Type of service consumed (ocr_text, ocr_structured, etc.)")
    tokens_used: int = Field(default=0, ge=0, description="Number of tokens used")
    processing_time: Optional[float] = Field(None, ge=0, description="Processing time in seconds")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (filename, file_size, model, etc.)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "8ea36362-29d4-4aa5-b815-f64d484f6aae",
                "service_type": "ocr_text",
                "tokens_used": 326,
                "processing_time": 1.825,
                "metadata": {
                    "filename": "test.png",
                    "file_size": 1024,
                    "model": "gpt-4o"
                }
            }
        }
    }


class UsageConsumeResponse(BaseModel):
    """Response schema for successful usage consumption."""

    success: bool = Field(default=True, description="Operation success status")
    remaining_credits: Optional[int] = Field(None, description="Remaining credits/queries for the user")
    credits_consumed: int = Field(default=1, description="Credits consumed in this operation")
    user_id: UUID = Field(..., description="User ID")
    message: str = Field(default="Usage recorded successfully", description="Response message")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "remaining_credits": 99,
                "credits_consumed": 1,
                "user_id": "8ea36362-29d4-4aa5-b815-f64d484f6aae",
                "message": "Usage recorded successfully"
            }
        }
    }


class UsageErrorResponse(BaseModel):
    """Response schema for usage errors."""

    success: bool = Field(default=False, description="Operation success status")
    error: str = Field(..., description="Error message")
    remaining_credits: Optional[int] = Field(None, description="Remaining credits/queries")
    required_credits: Optional[int] = Field(None, description="Required credits for operation")
    daily_limit: Optional[int] = Field(None, description="Daily limit")
    used_today: Optional[int] = Field(None, description="Used today")
    reset_time: Optional[datetime] = Field(None, description="When the limit resets")

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": False,
                "error": "Daily query limit exceeded",
                "daily_limit": 100,
                "used_today": 100,
                "reset_time": "2025-10-03T00:00:00Z"
            }
        }
    }


class UsageLogResponse(BaseModel):
    """Response schema for usage log."""

    id: UUID
    user_id: UUID
    service_type: str
    tokens_used: int
    processing_time: Optional[float]
    timestamp: datetime
    extra_data: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
