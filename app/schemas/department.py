"""
Pydantic schemas for Department.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel


class DepartmentBase(BaseModel):
    """Base department schema."""
    name: str


class DepartmentCreate(DepartmentBase):
    """Department creation schema."""
    pass


class DepartmentUpdate(BaseModel):
    """Department update schema."""
    name: Optional[str] = None


class DepartmentResponse(DepartmentBase):
    """Department response schema."""
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
