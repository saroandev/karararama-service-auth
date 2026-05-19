"""
MCPApiKey model — long-lived credential a user mints to authenticate the
OneDocs MCP server (consumed by Claude Desktop / claude.ai / Cursor etc.).

The MCP server exchanges this key for a short-lived JWT at a dedicated
`/auth/mcp/exchange` endpoint. The raw key is never persisted; only its
SHA-256 hash is stored — same pattern as RefreshToken.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUID, UUIDMixin


class MCPApiKey(Base, UUIDMixin, TimestampMixin):
    """
    Personal access key issued for the OneDocs MCP server.

    Attributes:
        id: Unique key identifier (UUID).
        user_id: User this key belongs to.
        key_hash: SHA-256 hex digest of the raw key (raw is never stored).
        key_prefix: First N chars of the raw key (e.g. "od_mcp_AbCd") —
            shown to the user in the management UI so they can identify
            which key is which without revealing the secret.
        name: User-supplied label (e.g. "Laptop Claude").
        expires_at: Optional hard expiry. Null = never expires.
        revoked_at: Soft-delete timestamp. Null = active.
        last_used_at: Last successful exchange timestamp.
        usage_count: Cumulative successful-exchange counter.
        user: User this key belongs to.
    """

    __tablename__ = "mcp_api_keys"

    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    key_prefix = Column(String(20), nullable=False)
    name = Column(String(100), nullable=False)
    expires_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)

    user = relationship("User", back_populates="mcp_api_keys")

    __table_args__ = (
        Index("idx_mcp_api_keys_user_id", "user_id"),
        Index("idx_mcp_api_keys_key_hash", "key_hash"),
    )

    def __repr__(self) -> str:
        return f"<MCPApiKey(id={self.id}, user_id={self.user_id}, name={self.name!r})>"

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and datetime.utcnow() > self.expires_at

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_active(self) -> bool:
        return not self.is_expired and not self.is_revoked
