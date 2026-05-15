"""
Subscription model — active paid plan for an organization.

A subscription is created when a `Payment` succeeds. Only one active
subscription per organization is expected; older ones are marked
`cancelled` or `expired`.
"""
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUID, UUIDMixin


class Subscription(Base, UUIDMixin, TimestampMixin):
    """Active or historical subscription record for an organization."""

    __tablename__ = "subscriptions"

    organization_id = Column(UUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id = Column(UUID(), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)

    plan = Column(String(50), nullable=False)
    billing_cycle = Column(String(20), nullable=False)
    seat_count = Column(Integer, nullable=False)
    storage_gb_per_user = Column(Numeric(6, 2), nullable=False)

    started_at = Column(DateTime, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    # active | expired | cancelled
    status = Column(String(20), nullable=False, default="active", index=True)

    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id], lazy="select")
    payment = relationship("Payment", back_populates="subscription", foreign_keys=[payment_id], lazy="select")

    __table_args__ = (
        Index("ix_subscriptions_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Subscription(org={self.organization_id}, plan={self.plan}, status={self.status})>"
