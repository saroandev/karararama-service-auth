"""
LoginAttempt model — append-only audit row written on every login attempt
(success or failure). Used by progressive brute-force protection: rolling
window counts decide whether the next attempt needs CAPTCHA, a cooldown,
or a hard 24-hour lock. See migration q7r8s9t0u1v2 for the policy table.
"""
from sqlalchemy import Boolean, Column, Index, String

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class LoginAttempt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "login_attempts"

    email = Column(String(255), nullable=False)
    # IPv6 max length = 45 chars. Nullable on purpose — see migration.
    ip_address = Column(String(45), nullable=True)
    success = Column(Boolean, nullable=False)
    # Free-form short code: 'bad_password' | 'unknown_email' | 'inactive'
    # | 'unverified' | 'locked' | 'captcha_required' | 'cooldown'
    failure_reason = Column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_login_attempts_email_created_at", "email", "created_at"),
        Index("ix_login_attempts_ip_created_at", "ip_address", "created_at"),
    )
