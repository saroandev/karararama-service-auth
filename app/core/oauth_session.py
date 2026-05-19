"""Browser session for the OAuth login/consent UI.

Only relevant for the human-facing /oauth/* HTML pages. Plain login JWTs
(``/api/v1/auth/login``) keep using bearer tokens in localStorage — this
module does not touch them.

Implementation: signed (not encrypted) cookie carrying just ``user_id``
and an issue time. itsdangerous validates signature + max-age. No
server-side state, no Redis dependency, naturally bounded TTL.

Cookie scope: this auth-svc origin only (HttpOnly, SameSite=Lax, Secure
in production). The signing key is ``OAUTH_SESSION_COOKIE_SECRET``,
falling back to ``JWT_SECRET_KEY`` so deployments don't have to mint a
new secret on day one.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID as PyUUID

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings

# Cookie name kept short to avoid bumping up against header size limits when
# combined with the JWT cookie session we use elsewhere.
COOKIE_NAME = "od_oauth_sess"
COOKIE_SALT = "oauth-login-session"


def _signer() -> URLSafeTimedSerializer:
    secret = settings.OAUTH_SESSION_COOKIE_SECRET or settings.JWT_SECRET_KEY
    if not secret:
        # Defensive: we can't sign without a key. Surface during boot, not
        # at first request.
        raise RuntimeError(
            "Either OAUTH_SESSION_COOKIE_SECRET or JWT_SECRET_KEY must be set"
        )
    return URLSafeTimedSerializer(secret, salt=COOKIE_SALT)


def issue_session_cookie(user_id: PyUUID | str) -> str:
    """Serialize ``user_id`` into a signed cookie value (no expiry baked in;
    expiry is checked at read time via ``max_age``)."""
    return _signer().dumps({"user_id": str(user_id)})


def read_session_cookie(raw_value: Optional[str]) -> Optional[str]:
    """Validate the signed cookie and return ``user_id`` as a string.

    Returns ``None`` if the cookie is missing, malformed, expired, or
    signed with a different secret. Callers should treat ``None`` as
    "user is not logged in" and render the login form.
    """
    if not raw_value:
        return None
    try:
        payload = _signer().loads(
            raw_value,
            max_age=settings.OAUTH_SESSION_COOKIE_TTL_SECONDS,
        )
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    user_id = payload.get("user_id")
    return user_id if isinstance(user_id, str) and user_id else None
