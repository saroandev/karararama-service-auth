"""
Pydantic schemas for IliskiliMuvekkil (Related Client).
"""
from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, computed_field

from app.models.muvekkil import MuvekkilUnvan


class IliskiliMuvekkillBase(BaseModel):
    unvan: MuvekkilUnvan = MuvekkilUnvan.KISI
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    muvekkil_aciklama: Optional[str] = None


class IliskiliMuvekkillCreate(IliskiliMuvekkillBase):
    pass


class IliskiliMuvekkillUpdate(BaseModel):
    unvan: Optional[MuvekkilUnvan] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    muvekkil_aciklama: Optional[str] = None


class IliskiliMuvekkillResponse(IliskiliMuvekkillBase):
    id: UUID
    organization_id: UUID
    muvekkil_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def atanmis(self) -> bool:
        return self.muvekkil_id is not None

    class Config:
        from_attributes = True


class IliskiliMuvekkillAssign(BaseModel):
    muvekkil_id: UUID
