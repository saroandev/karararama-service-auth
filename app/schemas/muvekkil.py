"""
Pydantic schemas for Muvekkil (Client).
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr


class MuvekkillBase(BaseModel):
    """Base muvekkil schema."""
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None


class MuvekkillCreate(MuvekkillBase):
    """Muvekkil creation schema."""
    pass


class MuvekkillUpdate(BaseModel):
    """Muvekkil update schema."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None


class MuvekkillResponse(MuvekkillBase):
    """Muvekkil response schema."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MuvekkillWithOrganizations(MuvekkillResponse):
    """Muvekkil with organizations."""
    organizations: List['OrganizationResponse'] = []

    class Config:
        from_attributes = True


# Forward reference resolution
from app.schemas.organization import OrganizationResponse
MuvekkillWithOrganizations.model_rebuild()
