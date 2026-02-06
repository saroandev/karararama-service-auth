"""
Pydantic schemas for UETS account operations.
"""
from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, Field


class UetsAccountCreate(BaseModel):
    """Request schema for connecting a UETS account."""

    uets_account_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="UETS account name to connect"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "uets_account_name": "hesap_adi"
            }
        }
    }


class UetsAccountResponse(BaseModel):
    """Response schema for a UETS account."""

    org_id: UUID = Field(..., description="Organization ID")
    user_id: UUID = Field(..., description="User ID")
    uets_account_name: str = Field(..., description="UETS account name")
    created_at: datetime = Field(..., description="Account connection timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "org_id": "8ea36362-29d4-4aa5-b815-f64d484f6aae",
                "user_id": "9fa47473-3ae5-5bb6-c926-g75e595f7bbf",
                "uets_account_name": "hesap_adi",
                "created_at": "2026-02-06T12:00:00Z"
            }
        }
    }


class UetsAccountItem(BaseModel):
    """Schema for a UETS account item in list response."""

    uets_account_name: str = Field(..., description="UETS account name")
    created_at: datetime = Field(..., description="Account connection timestamp")

    model_config = {
        "from_attributes": True
    }


class UetsAccountListResponse(BaseModel):
    """Response schema for listing connected UETS accounts."""

    accounts: List[UetsAccountItem] = Field(
        default_factory=list,
        description="List of connected UETS accounts"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "accounts": [
                    {
                        "uets_account_name": "hesap1",
                        "created_at": "2026-02-06T12:00:00Z"
                    },
                    {
                        "uets_account_name": "hesap2",
                        "created_at": "2026-02-06T13:00:00Z"
                    }
                ]
            }
        }
    }
