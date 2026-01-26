"""
Invitation model for user invitations to organizations.
"""
from datetime import datetime, timedelta
from sqlalchemy import Boolean, Column, String, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class InvitationStatus(str, enum.Enum):
    """Invitation status enum."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Invitation(Base, UUIDMixin, TimestampMixin):
    """
    Invitation model for inviting users to organizations.

    Attributes:
        id: Unique invitation identifier (UUID)
        email: Email address of the invitee
        organization_id: Organization the user is invited to
        invited_by_user_id: User who sent the invitation
        role: Role to be assigned (member, admin, owner)
        token: Unique invitation token for acceptance
        status: Current status (pending, accepted, expired, revoked)
        expires_at: Expiration timestamp
        accepted_at: When the invitation was accepted
        organization: Organization relationship
        invited_by: User who sent the invitation
    """

    __tablename__ = "invitations"

    email = Column(String(255), nullable=False, index=True)
    organization_id = Column(UUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    invited_by_user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False, default="member")
    token = Column(String(255), nullable=False, unique=True, index=True)
    status = Column(
        SQLEnum(
            InvitationStatus,
            values_callable=lambda x: [e.value for e in x],
            native_enum=False,  # Don't use PostgreSQL native ENUM, use VARCHAR instead
        ),
        nullable=False,
        default=InvitationStatus.PENDING,
        index=True
    )
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship(
        "Organization",
        lazy="selectin"
    )

    invited_by = relationship(
        "User",
        foreign_keys=[invited_by_user_id],
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Invitation(id={self.id}, email={self.email}, status={self.status})>"

    @property
    def is_expired(self) -> bool:
        """Check if invitation has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if invitation is valid (pending and not expired)."""
        return self.status == InvitationStatus.PENDING and not self.is_expired
