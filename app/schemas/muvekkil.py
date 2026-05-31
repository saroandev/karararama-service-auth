"""
Pydantic schemas for Muvekkil (Portal).
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, EmailStr, computed_field, field_validator, model_validator

from app.models.muvekkil import MuvekkilUnvan


def _clean_digits(value: Optional[str]) -> Optional[str]:
    """Strip whitespace + non-digits; empty → None."""
    if value is None:
        return None
    digits = "".join(c for c in str(value) if c.isdigit())
    return digits or None


class MuvekkillBase(BaseModel):
    """Base muvekkil schema."""
    unvan: MuvekkilUnvan = MuvekkilUnvan.KISI
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    tckn: Optional[str] = None
    vkn: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    muvekkil_aciklama: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

    @field_validator("tckn", mode="before")
    @classmethod
    def normalize_tckn(cls, v):
        cleaned = _clean_digits(v)
        if cleaned is not None and len(cleaned) != 11:
            raise ValueError("TCKN 11 haneli olmalı")
        return cleaned

    @field_validator("vkn", mode="before")
    @classmethod
    def normalize_vkn(cls, v):
        cleaned = _clean_digits(v)
        if cleaned is not None and len(cleaned) != 10:
            raise ValueError("VKN 10 haneli olmalı")
        return cleaned


class MuvekkillCreate(MuvekkillBase):
    """Muvekkil creation schema.

    organization_id is implicit at the API boundary — set from the
    caller's active organization. It is NOT accepted from the request
    body to keep the isolation invariant: a muvekkil always belongs to
    the caller's organization.

    Enforces TCKN/VKN matches the chosen unvan, since the DB partial
    indexes only catch duplicates, not type mismatches.
    """

    @model_validator(mode="after")
    def check_identity_matches_unvan(self):
        if self.unvan == MuvekkilUnvan.KISI:
            if self.vkn is not None:
                raise ValueError("Gerçek kişi müvekkilde VKN olamaz")
            if not self.tckn:
                raise ValueError("Gerçek kişi müvekkil için TCKN zorunlu")
        elif self.unvan == MuvekkilUnvan.SIRKET:
            if self.tckn is not None:
                raise ValueError("Tüzel kişi müvekkilde TCKN olamaz")
            if not self.vkn:
                raise ValueError("Tüzel kişi müvekkil için VKN zorunlu")
        return self


class MuvekkillUpdate(BaseModel):
    """Muvekkil update schema. All fields optional; only those provided
    are persisted. tckn/vkn changes must respect unvan rules — caller
    can also change unvan in the same request, the API layer enforces
    consistency post-merge."""
    unvan: Optional[MuvekkilUnvan] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    tckn: Optional[str] = None
    vkn: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    notes: Optional[str] = None
    muvekkil_aciklama: Optional[str] = None

    @field_validator("email", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        if v == "":
            return None
        return v

    @field_validator("tckn", mode="before")
    @classmethod
    def normalize_tckn(cls, v):
        cleaned = _clean_digits(v)
        if cleaned is not None and len(cleaned) != 11:
            raise ValueError("TCKN 11 haneli olmalı")
        return cleaned

    @field_validator("vkn", mode="before")
    @classmethod
    def normalize_vkn(cls, v):
        cleaned = _clean_digits(v)
        if cleaned is not None and len(cleaned) != 10:
            raise ValueError("VKN 10 haneli olmalı")
        return cleaned


class IliskiliMuvekkillSummary(BaseModel):
    """Lightweight summary of an assigned iliskili muvekkil."""
    id: UUID
    name: str
    unvan: MuvekkilUnvan

    class Config:
        from_attributes = True


class MuvekkillResponse(MuvekkillBase):
    """Muvekkil (portal) response schema."""
    id: UUID
    organization_id: UUID
    is_archived: bool = False
    archived_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    iliskili_muvekkiller: List[IliskiliMuvekkillSummary] = []

    @computed_field
    @property
    def muvekkil_id(self) -> UUID:
        return self.id

    class Config:
        from_attributes = True


class MuvekkillListResponse(BaseModel):
    """Paginated muvekkil list with total count."""
    total: int
    items: List[MuvekkillResponse]
