"""
Department model for system-wide department reference data.
"""
from sqlalchemy import Column, String

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Department(Base, UUIDMixin, TimestampMixin):
    """System-wide department reference. Seeded by admin."""

    __tablename__ = "departments"

    name = Column(String(150), nullable=False, unique=True, index=True)

    def __repr__(self) -> str:
        return f"<Department(id={self.id}, name={self.name})>"
