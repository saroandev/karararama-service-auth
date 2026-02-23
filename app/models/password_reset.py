"""
Password reset token model for secure password reset functionality.
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class PasswordResetToken(Base, UUIDMixin, TimestampMixin):
    """
    Password reset token model for tracking reset tokens sent to users.

    Attributes:
        id: Unique reset token record identifier (UUID)
        user_id: ID of the user this reset token is for
        token_hash: SHA256 hash of the reset token (for security)
        expires_at: When the token expires (default 30 minutes)
        is_used: Whether the token has been used
        used_at: When the token was used (nullable)
        ip_address: IP address of the requester (optional, for audit)
        created_at: When the token was created
        updated_at: When the record was last updated
    """

    __tablename__ = "password_reset_tokens"

    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)  # SHA256 hash = 64 chars
    expires_at = Column(DateTime, nullable=False, index=True)
    is_used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length = 45 chars

    # Relationship
    user = relationship("User", backref="password_reset_tokens", lazy="select")

    @property
    def is_expired(self) -> bool:
        """Check if the token has expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if the token is valid (not expired and not used)."""
        return not self.is_expired and not self.is_used

    def __repr__(self) -> str:
        return f"<PasswordResetToken(user_id={self.user_id}, is_used={self.is_used}, is_expired={self.is_expired})>"
