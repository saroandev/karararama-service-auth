"""
OrganizationMember model for managing user memberships in organizations.

This model enables multi-organization support where users can belong to multiple
organizations with different roles in each.
"""
from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class OrganizationMember(Base, UUIDMixin, TimestampMixin):
    """
    Organization membership model for many-to-many user-organization relationships.

    Attributes:
        id: Unique membership identifier (UUID)
        user_id: User ID (foreign key to users table)
        organization_id: Organization ID (foreign key to organizations table)
        role: User's role in this organization (e.g., 'owner', 'admin', 'member')
        is_primary: Whether this is the user's active/primary organization
        joined_at: Timestamp when the user joined this organization
        user: User relationship
        organization: Organization relationship
    """

    __tablename__ = "organization_members"

    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default="member")
    is_primary = Column(Boolean, nullable=False, default=False, index=True)
    joined_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('ix_org_members_user_org', 'user_id', 'organization_id', unique=True),
    )

    # Relationships
    user = relationship(
        "User",
        back_populates="memberships",
        lazy="selectin"
    )

    organization = relationship(
        "Organization",
        back_populates="memberships",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<OrganizationMember(user_id={self.user_id}, org_id={self.organization_id}, role={self.role})>"
