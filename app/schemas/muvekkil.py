"""
Pydantic schemas for Muvekkil (Client).
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, computed_field, field_validator

from app.models.muvekkil import MuvekkilUnvan


class MuvekkillBase(BaseModel):
    """Base muvekkil schema."""
    unvan: MuvekkilUnvan = MuvekkilUnvan.KISI
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    muvekkil_aciklama: Optional[str] = None


class MuvekkillCreate(MuvekkillBase):
    """Muvekkil creation schema."""
    organization_id: Optional[UUID] = None


class MuvekkillUpdate(BaseModel):
    """Muvekkil update schema."""
    unvan: Optional[MuvekkilUnvan] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    muvekkil_aciklama: Optional[str] = None


class IliskiliMuvekkillSummary(BaseModel):
    """Lightweight summary of an assigned iliskili muvekkil."""
    id: UUID
    name: str
    unvan: MuvekkilUnvan

    class Config:
        from_attributes = True


class MuvekkillResponse(MuvekkillBase):
    """Muvekkil response schema."""
    id: UUID
    created_at: datetime
    updated_at: datetime
    iliskili_muvekkiller: List[IliskiliMuvekkillSummary] = []

    @computed_field
    @property
    def muvekkil_id(self) -> UUID:
        return self.id

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
