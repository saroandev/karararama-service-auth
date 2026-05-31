"""
PortalMember model — junction between a Muvekkil (Portal) and a User.

Each row grants a user a role on a specific portal. Replaces the
"any user in the host org touches any muvekkil" rule with explicit
per-portal membership.

Roles (stored as plain VARCHAR, not native enum, so additions stay
schema-clean):
  - manager     — the OneDocs user who opened the portal, manages members
  - responsible — sorumlu avukat assigned to the matter
  - user        — regular org-side user with portal access
  - guest       — Guest user (client side), invited via portal-scoped flow
"""
import enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class PortalRole(str, enum.Enum):
    """Roles a user can hold inside a single portal."""
    MANAGER = "manager"
    RESPONSIBLE = "responsible"
    USER = "user"
    GUEST = "guest"


class PortalMember(Base, UUIDMixin, TimestampMixin):
    """
    A user's membership in a portal.

    Uniqueness on (muvekkil_id, user_id) means a user holds at most one
    role per portal — role changes are updates, not duplicate rows.

    Attributes:
        muvekkil_id: Portal this membership belongs to
        user_id: Member user
        portal_role: One of PortalRole values (stored as string)
        is_active: Toggling to False revokes access without losing history
        joined_at: When the user accepted the invite (or was added)
        invited_by_user_id: Who invited them (NULL on system-created rows)
    """

    __tablename__ = "portal_members"

    muvekkil_id = Column(
        UUID(),
        ForeignKey("muvekkiller.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    portal_role = Column(String(32), nullable=False)
    is_active = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    joined_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
    invited_by_user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    muvekkil = relationship(
        "Muvekkil", back_populates="portal_members", lazy="select"
    )
    user = relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="portal_memberships",
        lazy="select",
    )
    invited_by = relationship(
        "User", foreign_keys=[invited_by_user_id], lazy="select"
    )

    __table_args__ = (
        UniqueConstraint(
            "muvekkil_id", "user_id", name="uq_portal_members_muvekkil_user"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PortalMember(muvekkil_id={self.muvekkil_id}, "
            f"user_id={self.user_id}, role={self.portal_role})>"
        )
