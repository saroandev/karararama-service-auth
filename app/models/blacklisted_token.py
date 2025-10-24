"""
BlacklistedToken model for managing blacklisted access tokens.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Index
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class BlacklistedToken(Base, UUIDMixin, TimestampMixin):
    """
    BlacklistedToken model for storing revoked access tokens.

    When a user logs out, their access token is added to this blacklist
    to prevent further use until it naturally expires.

    Attributes:
        id: Unique identifier (UUID)
        user_id: User ID this token belongs to
        token_hash: Hashed access token (SHA256)
        expires_at: Token expiration timestamp
        reason: Reason for blacklisting (logout, security, etc.)
        user: User this token belongs to
    """

    __tablename__ = "blacklisted_tokens"

    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token_hash = Column(String(255), nullable=False, index=True, unique=True)
    expires_at = Column(DateTime, nullable=False)
    reason = Column(String(50), nullable=True, default="logout")

    # Relationships
    user = relationship("User", back_populates="blacklisted_tokens")

    __table_args__ = (
        Index('idx_blacklisted_tokens_token_hash', 'token_hash'),
        Index('idx_blacklisted_tokens_user_id', 'user_id'),
        Index('idx_blacklisted_tokens_expires_at', 'expires_at'),
    )

    def __repr__(self) -> str:
        return f"<BlacklistedToken(id={self.id}, user_id={self.user_id})>"

    @property
    def is_expired(self) -> bool:
        """Check if token has expired and can be removed from blacklist."""
        return datetime.utcnow() > self.expires_at
