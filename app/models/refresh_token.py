"""
RefreshToken model for managing refresh tokens.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Index, Text, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB as PostgreSQLJSONB
from sqlalchemy.orm import relationship
import json

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class JSONB(TypeDecorator):
    """Platform-independent JSONB type.
    Uses PostgreSQL's JSONB type on PostgreSQL, otherwise uses TEXT with JSON encoding.
    """
    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgreSQLJSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            return json.loads(value) if value else None


class RefreshToken(Base, UUIDMixin, TimestampMixin):
    """
    RefreshToken model for storing refresh tokens.

    Attributes:
        id: Unique token identifier (UUID)
        user_id: User ID this token belongs to
        token_hash: Hashed refresh token
        expires_at: Token expiration timestamp
        revoked_at: Token revocation timestamp (if revoked)
        device_info: Device information (browser, IP, etc.) as JSON
        user: User this token belongs to
    """

    __tablename__ = "refresh_tokens"

    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token_hash = Column(String(255), nullable=False, index=True, unique=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    device_info = Column(JSONB(), nullable=True)

    # Relationships
    user = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index('idx_refresh_tokens_user_id', 'user_id'),
        Index('idx_refresh_tokens_token_hash', 'token_hash'),
    )

    def __repr__(self) -> str:
        return f"<RefreshToken(id={self.id}, user_id={self.user_id})>"

    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def is_revoked(self) -> bool:
        """Check if token is revoked."""
        return self.revoked_at is not None

    @property
    def is_valid(self) -> bool:
        """Check if token is valid (not expired and not revoked)."""
        return not self.is_expired and not self.is_revoked