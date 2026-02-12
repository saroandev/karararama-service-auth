"""
Email verification model for user email verification.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class EmailVerification(Base, UUIDMixin, TimestampMixin):
    """
    Email verification model for tracking verification codes sent to users.

    Attributes:
        id: Unique verification record identifier (UUID)
        user_id: ID of the user this verification is for
        email: Email address to verify
        code: 6-digit verification code
        expires_at: When the code expires
        is_used: Whether the code has been used
        attempts: Number of failed verification attempts
        created_at: When the code was created
        updated_at: When the record was last updated
    """

    __tablename__ = "email_verifications"

    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False, index=True)
    code = Column(String(6), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_used = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)

    # Relationship
    user = relationship("User", backref="email_verifications", lazy="select")

    def __repr__(self) -> str:
        return f"<EmailVerification(email={self.email}, code={self.code}, is_used={self.is_used})>"
