"""OAuthClient — RFC 7591 Dynamic Client Registration storage.

One row per OAuth-aware client that registered against our authorization
server (e.g. each Claude.ai connector instance).

Public clients only — token_endpoint_auth_method defaults to 'none' and
client secrets are never issued. PKCE (S256) is required on every
authorize request.
"""
from sqlalchemy import Boolean, Column, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class OAuthClient(Base, UUIDMixin, TimestampMixin):
    """OAuth 2.1 client registered via DCR.

    Attributes:
        client_id: Public identifier returned to the registering client.
            Format ``od_oauth_<32 hex>``. Indexed and unique.
        client_name: Human-readable label (e.g. "Claude").
        client_uri: Optional homepage URL.
        logo_uri: Optional logo URL (shown on the consent screen).
        redirect_uris: JSON array of allowed redirect URIs. /oauth/authorize
            rejects any redirect_uri not in this list.
        token_endpoint_auth_method: 'none' (public client, no client_secret).
        grant_types: Allowed grant types, typically
            ``["authorization_code", "refresh_token"]``.
        response_types: Allowed response types, typically ``["code"]``.
        scope: Space-separated scopes this client may request.
        is_active: Soft-delete flag (admin can disable a client).
    """

    __tablename__ = "oauth_clients"

    client_id = Column(String(80), nullable=False, unique=True, index=True)
    client_name = Column(String(255), nullable=False)
    client_uri = Column(String(500), nullable=True)
    logo_uri = Column(String(500), nullable=True)
    redirect_uris = Column(JSONB, nullable=False)
    token_endpoint_auth_method = Column(
        String(32), nullable=False, default="none"
    )
    grant_types = Column(JSONB, nullable=False)
    response_types = Column(JSONB, nullable=False)
    scope = Column(String(500), nullable=False, default="mcp:search")
    is_active = Column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (
        Index("ix_oauth_clients_client_id", "client_id", unique=True),
        Index("ix_oauth_clients_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return (
            f"<OAuthClient(client_id={self.client_id!r}, "
            f"name={self.client_name!r}, active={self.is_active})>"
        )

    @property
    def redirect_uri_list(self) -> list[str]:
        """Type-safe accessor for the JSONB array."""
        return list(self.redirect_uris or [])

    @property
    def grant_type_list(self) -> list[str]:
        return list(self.grant_types or [])

    @property
    def response_type_list(self) -> list[str]:
        return list(self.response_types or [])

    @property
    def scope_set(self) -> set[str]:
        return set((self.scope or "").split())
