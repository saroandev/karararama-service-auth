"""
Pydantic schemas for UYAP account operations.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UyapAccountCreate(BaseModel):
    """Request schema for connecting a UYAP account."""

    uyap_account_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="UYAP account name to connect (unique per organization)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "uyap_account_name": "hesap_adi"
            }
        }
    }


class UyapAccountResponse(BaseModel):
    """Response schema for a UYAP account."""

    org_id: UUID = Field(..., description="Organization ID")
    uyap_account_name: str = Field(..., description="UYAP account name")
    created_by_user_id: Optional[UUID] = Field(
        None, description="User ID of the member who added the account"
    )
    created_at: datetime = Field(..., description="Account connection timestamp")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "org_id": "8ea36362-29d4-4aa5-b815-f64d484f6aae",
                "uyap_account_name": "hesap_adi",
                "created_by_user_id": "9fa47473-3ae5-5bb6-c926-g75e595f7bbf",
                "created_at": "2026-04-30T12:00:00Z"
            }
        }
    }


class UyapAccountItem(BaseModel):
    """Schema for a UYAP account item in list response."""

    uyap_account_name: str = Field(..., description="UYAP account name")
    created_by_user_id: Optional[UUID] = Field(
        None, description="User ID of the member who added the account"
    )
    created_at: datetime = Field(..., description="Account connection timestamp")

    model_config = {
        "from_attributes": True
    }


class UyapAccountListResponse(BaseModel):
    """Response schema for listing connected UYAP accounts in an organization."""

    accounts: List[UyapAccountItem] = Field(
        default_factory=list,
        description="List of connected UYAP accounts in the organization"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "accounts": [
                    {
                        "uyap_account_name": "hesap1",
                        "created_by_user_id": "9fa47473-3ae5-5bb6-c926-g75e595f7bbf",
                        "created_at": "2026-04-30T12:00:00Z"
                    },
                    {
                        "uyap_account_name": "hesap2",
                        "created_by_user_id": "9fa47473-3ae5-5bb6-c926-g75e595f7bbf",
                        "created_at": "2026-04-30T13:00:00Z"
                    }
                ]
            }
        }
    }
