"""OAuthRefreshToken — long-lived rotating refresh token storage.

Issued alongside every access token at /oauth/token. Lifetime: 30 days.
Each successful refresh_token grant **rotates** the token: the old row
is marked revoked and a new one is issued.

Plain token returned to the client once. Only SHA-256 hash persisted —
same pattern as ``mcp_api_keys`` and ``oauth_authorization_codes``.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String

from app.core.database import Base
from app.models.base import TimestampMixin, UUID, UUIDMixin


class OAuthRefreshToken(Base, UUIDMixin, TimestampMixin):
    """One refresh token bound to (user, client, resource, scope).

    Attributes:
        token_hash: SHA-256 hex digest of the plain refresh token.
        client_id: The OAuth client this token was issued to.
        user_id: The user whose access this token represents.
        scope: Space-separated scope set granted.
        resource: RFC 8707 resource indicator (e.g. mcp.onedocs.ai).
        expires_at: Creation time + 30 days.
        revoked_at: Set on rotation OR explicit revoke.
    """

    __tablename__ = "oauth_refresh_tokens"

    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    client_id = Column(String(80), nullable=False)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope = Column(String(500), nullable=False)
    resource = Column(String(500), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_oauth_refresh_token_hash", "token_hash", unique=True),
        Index("ix_oauth_refresh_user_client", "user_id", "client_id"),
        Index("ix_oauth_refresh_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<OAuthRefreshToken(id={self.id}, client_id={self.client_id!r}, "
            f"user_id={self.user_id}, revoked={self.revoked_at is not None})>"
        )

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_active(self) -> bool:
        return not self.is_expired and not self.is_revoked
