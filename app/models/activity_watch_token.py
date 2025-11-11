"""
ActivityWatchToken model for managing long-lived Activity Watch desktop app tokens.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Index
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class ActivityWatchToken(Base, UUIDMixin, TimestampMixin):
    """
    ActivityWatchToken model for storing long-lived Activity Watch tokens.

    These tokens are used by the Activity Watch desktop application for authentication.
    Each user can have only one active token at a time. Tokens have no expiration date.

    Attributes:
        id: Unique token identifier (UUID)
        user_id: User ID this token belongs to (unique - one token per user)
        token_hash: Hashed Activity Watch token
        last_used_at: Last time this token was used for authentication
        user: User this token belongs to
    """

    __tablename__ = "activity_watch_tokens"

    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # Only one token per user
        index=True
    )
    token_hash = Column(String(255), nullable=False, index=True, unique=True)
    last_used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="activity_watch_token")

    __table_args__ = (
        Index('idx_activity_watch_tokens_user_id', 'user_id'),
        Index('idx_activity_watch_tokens_token_hash', 'token_hash'),
    )

    def __repr__(self) -> str:
        return f"<ActivityWatchToken(id={self.id}, user_id={self.user_id})>"

    def update_last_used(self):
        """Update the last_used_at timestamp to current time."""
        self.last_used_at = datetime.utcnow()
