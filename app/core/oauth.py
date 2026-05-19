"""OAuth 2.1 utilities: PKCE, secret generation, OAuth JWT minting.

Kept separate from `app.core.security` so the OAuth flow can evolve
without churning the well-tested login JWT helpers. Reuses
`build_user_token_payload` so the access token claims look identical to
a /auth/login token; we only *add* OAuth-specific fields
(iss, aud, scope, client_id, jti) on top.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from jose import jwt

from app.core.config import settings


# ---------------------------------------------------------------------------
# Identifiers / secrets
# ---------------------------------------------------------------------------

# `od_oauth_` prefix lets ops grep logs and instantly see "this is an OAuth
# client id minted by us" — same convention as `od_mcp_` for API keys.
OAUTH_CLIENT_ID_PREFIX = "od_oauth_"

# Length tuned to give ~128 bits of entropy after hex encoding. 32 hex chars
# = 16 random bytes ≈ 128 bits.
_CLIENT_ID_HEX_CHARS = 32
_AUTH_CODE_BYTES = 32  # 256 bits — generous, plain text lives <60s anyway
_REFRESH_TOKEN_BYTES = 32


def generate_client_id() -> str:
    """`od_oauth_<32 hex>`. Public client identifier, returned in DCR."""
    return f"{OAUTH_CLIENT_ID_PREFIX}{secrets.token_hex(_CLIENT_ID_HEX_CHARS // 2)}"


def generate_authorization_code() -> str:
    """URL-safe random string. Only its SHA-256 hash is persisted."""
    return secrets.token_urlsafe(_AUTH_CODE_BYTES)


def generate_refresh_token() -> str:
    """URL-safe random string. Only its SHA-256 hash is persisted."""
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


# ---------------------------------------------------------------------------
# PKCE (RFC 7636) — S256 method only
# ---------------------------------------------------------------------------

def verify_pkce_s256(*, code_verifier: str, code_challenge: str) -> bool:
    """Return True iff base64url(SHA256(code_verifier)) == code_challenge.

    RFC 7636 §4.6:
        code_challenge = BASE64URL-ENCODE(SHA256(ASCII(code_verifier)))

    We tolerate the missing padding ("=") that is standard for base64url
    in URLs; the encoded SHA-256 hash is always 43 chars without padding.
    """
    if not code_verifier or not code_challenge:
        return False
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    # Compare against the challenge with any trailing "=" stripped — clients
    # in the wild aren't fully consistent.
    return secrets.compare_digest(expected, code_challenge.rstrip("="))


# ---------------------------------------------------------------------------
# Access token (OAuth JWT)
# ---------------------------------------------------------------------------

def build_oauth_access_token(
    *,
    base_payload: dict[str, Any],
    client_id: str,
    scope: str,
    resource: str,
    issuer: str,
    ttl_seconds: int,
) -> tuple[str, int]:
    """Mint an OAuth-flavoured access token.

    `base_payload` should be the dict returned by
    `app.services.token_service.build_user_token_payload` so the token
    carries the full plan/permissions/quota claims a login token would.
    We add the OAuth-specific bits on top and re-sign.

    Returns ``(jwt_string, expires_in_seconds)``.
    """
    now = datetime.utcnow()
    expire = now + timedelta(seconds=ttl_seconds)

    payload: dict[str, Any] = dict(base_payload)
    payload.update(
        {
            "iss": issuer,
            "aud": resource,
            "iat": now,
            "exp": expire,
            "jti": str(uuid.uuid4()),
            "scope": scope,
            "client_id": client_id,
            "type": "access",
        }
    )

    encoded = jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded, ttl_seconds
