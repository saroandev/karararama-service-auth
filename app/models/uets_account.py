"""
UETS Account model for linking user accounts to UETS.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, String, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import UUID


class UetsAccount(Base):
    """
    UETS Account model for storing user UETS account connections.

    This is an association table with composite primary key (org_id, user_id, uets_account_name).
    A user can have multiple UETS accounts within their organization.

    Attributes:
        org_id: Organization ID (from JWT)
        user_id: User ID (from JWT)
        uets_account_name: UETS account name
        created_at: Account connection timestamp
    """

    __tablename__ = "uets_accounts"

    org_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    uets_account_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Composite primary key
    __table_args__ = (
        PrimaryKeyConstraint("org_id", "user_id", "uets_account_name"),
    )

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[org_id])

    def __repr__(self) -> str:
        return f"<UetsAccount(org_id={self.org_id}, user_id={self.user_id}, uets_account_name={self.uets_account_name})>"
