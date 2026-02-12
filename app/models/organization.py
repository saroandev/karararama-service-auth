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

    Users can belong to multiple organizations with different roles in each.
    Each user has one primary/active organization. Organizations own:
    - Shared data (accessible to all members)
    - Individual user data (private to each user)

    Attributes:
        id: Unique organization identifier (UUID)
        name: Organization name
        owner_id: User ID of the organization owner
        is_active: Whether the organization is active
        users: List of users with this as their primary organization
        owner: User who owns this organization
        memberships: All user memberships in this organization
    """

    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    owner_id = Column(UUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    organization_type = Column(String(50), nullable=True)  # "law-firm", "legal-department", "other"
    organization_size = Column(String(20), nullable=True)  # "1-9", "10-49", "50-200", "200+"
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

    memberships = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name={self.name})>"
