"""
OtpCode model — one-time email codes for Guest user OTP login.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class OtpCode(Base, UUIDMixin, TimestampMixin):
    """
    One-time email code.

    Codes are 6-digit, SHA-256-hashed at rest, single-use (consumed_at),
    and time-boxed (expires_at, default 1 hour). `attempts` lets the
    verify endpoint lock a row after repeated wrong guesses without
    needing a separate rate-limit table.
    """

    __tablename__ = "otp_codes"

    email = Column(String(255), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False)
    organization_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    requested_ip = Column(String(64), nullable=True)
    requested_user_agent = Column(String(255), nullable=True)

    organization = relationship("Organization", lazy="select")

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_usable(self) -> bool:
        return not self.is_expired and not self.is_consumed
