"""
UYAP Account model for linking accounts to UYAP within an organization.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, String, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import UUID


class UyapAccount(Base):
    """
    UYAP Account model for storing organization-level UYAP account connections.

    Composite primary key is (org_id, uyap_account_name): account names must
    be unique *per organization*. Any member of the org can list, add or
    remove UYAP accounts; the creator is recorded for audit only.

    Attributes:
        org_id: Organization ID (from JWT, part of PK)
        uyap_account_name: UYAP account name (part of PK, unique per org)
        created_by_user_id: User ID of the member who added the account
        created_at: Account connection timestamp
    """

    __tablename__ = "uyap_accounts"

    org_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    uyap_account_name = Column(String(255), nullable=False)
    created_by_user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("org_id", "uyap_account_name"),
    )

    organization = relationship("Organization", foreign_keys=[org_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    def __repr__(self) -> str:
        return f"<UyapAccount(org_id={self.org_id}, uyap_account_name={self.uyap_account_name})>"
