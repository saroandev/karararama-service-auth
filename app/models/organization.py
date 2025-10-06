"""
Organization model for multi-tenancy and data access control.
"""
from sqlalchemy import Boolean, Column, String, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class Organization(Base, UUIDMixin, TimestampMixin):
    """
    Organization model for multi-tenant data isolation.

    Each user belongs to one organization. Organizations own:
    - Shared data (accessible to all members)
    - Individual user data (private to each user)

    Attributes:
        id: Unique organization identifier (UUID)
        name: Organization name
        owner_id: User ID of the organization owner
        is_active: Whether the organization is active
        users: List of users in this organization
        owner: User who owns this organization
    """

    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    owner_id = Column(UUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    users = relationship(
        "User",
        back_populates="organization",
        foreign_keys="User.organization_id",
        lazy="select"
    )

    owner = relationship(
        "User",
        foreign_keys=[owner_id],
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"
