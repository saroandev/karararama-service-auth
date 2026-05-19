"""OAuthAuthorizationCode — short-lived PKCE-bound authorization codes.

Emitted by /oauth/authorize after the user consents, redeemed once at
/oauth/token. Lifetime: 60 seconds. After redemption the row's
``used_at`` is set; any reuse attempt fails (defense against code
replay even if the redirect leaks).

We persist only a SHA-256 hash of the code so a DB leak yields nothing
useful — the plain code is in the user's browser URL bar for ~1 second
between the authorize redirect and the token POST.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String

from app.core.database import Base
from app.models.base import UUID, UUIDMixin


class OAuthAuthorizationCode(Base, UUIDMixin):
    """One short-lived authorization code.

    Attributes:
        code_hash: SHA-256 hex digest of the plain code.
        client_id: The OAuth client that requested this code.
        user_id: The user who consented (FK to users.id, CASCADE on delete).
        redirect_uri: Must match the one used at /oauth/token exactly.
        code_challenge: PKCE — base64url(SHA-256(code_verifier)).
        code_challenge_method: Always "S256" (we don't support "plain").
        scope: Space-separated scopes granted by the user.
        resource: RFC 8707 resource indicator — must equal the MCP URI.
        expires_at: 60 seconds after creation.
        used_at: Set when the code is redeemed (single-use enforcement).
    """

    __tablename__ = "oauth_authorization_codes"

    code_hash = Column(String(64), nullable=False, unique=True, index=True)
    client_id = Column(String(80), nullable=False)
    user_id = Column(
        UUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    redirect_uri = Column(String(500), nullable=False)
    code_challenge = Column(String(128), nullable=False)
    code_challenge_method = Column(String(8), nullable=False, default="S256")
    scope = Column(String(500), nullable=False)
    resource = Column(String(500), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_oauth_auth_codes_hash", "code_hash", unique=True),
        Index("ix_oauth_auth_codes_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<OAuthAuthorizationCode(id={self.id}, client_id={self.client_id!r}, "
            f"user_id={self.user_id}, used={self.used_at is not None})>"
        )

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_redeemable(self) -> bool:
        return not self.is_used and not self.is_expired
