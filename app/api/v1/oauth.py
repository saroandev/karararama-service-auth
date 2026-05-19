"""OAuth 2.1 + Dynamic Client Registration endpoints.

This module owns the **JSON-API** half of the OAuth flow:

- ``POST /api/v1/oauth/register`` — RFC 7591 Dynamic Client Registration
- ``POST /api/v1/oauth/token``    — authorization_code + refresh_token grants

The browser-facing half (``/oauth/authorize``, ``/oauth/login``,
``/oauth/consent``, ``/.well-known/oauth-authorization-server``) lives in
``app.api.oauth_html`` so it can render HTML templates without polluting
this router.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.oauth import (
    build_oauth_access_token,
    generate_authorization_code,  # noqa: F401  (re-export for tests)
    generate_client_id,
    generate_refresh_token,
    verify_pkce_s256,
)
from app.crud import (
    oauth_authorization_code_crud,
    oauth_client_crud,
    oauth_refresh_token_crud,
    user_crud,
)
from app.schemas.oauth import (
    ClientRegistrationRequest,
    ClientRegistrationResponse,
    OAuthError,
    TokenResponse,
)
from app.services.token_service import build_user_token_payload

logger = logging.getLogger(__name__)
router = APIRouter()


def _oauth_error(
    *,
    error: str,
    error_description: str | None = None,
    status_code: int = status.HTTP_400_BAD_REQUEST,
) -> JSONResponse:
    """RFC 6749 §5.2 error response, with the right HTTP status.

    OAuth errors are wire-shape sensitive — clients parse the JSON body
    looking for ``error`` and ``error_description``. Don't wrap these in
    FastAPI's default ``{"detail": ...}`` envelope.
    """
    payload = OAuthError(error=error, error_description=error_description).model_dump(
        exclude_none=True
    )
    headers = {}
    if error == "invalid_client":
        headers["WWW-Authenticate"] = 'Bearer error="invalid_client"'
    return JSONResponse(content=payload, status_code=status_code, headers=headers)


# ---------------------------------------------------------------------------
# Dynamic Client Registration (RFC 7591)
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=ClientRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="OAuth 2.1 Dynamic Client Registration (RFC 7591)",
)
async def register_client(
    payload: ClientRegistrationRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientRegistrationResponse:
    """Register a new OAuth client. No auth required (public DCR).

    Each call mints a fresh ``client_id``. Claude.ai is expected to call
    this once the first time a user adds the connector; subsequent
    connections reuse the same ``client_id``.
    """
    # Whitelist scopes. For v1 we only support `mcp:search`; reject
    # anything else early so clients get a clear error.
    requested_scopes = set(payload.scope.split())
    allowed_scopes = {"mcp:search"}
    illegal = requested_scopes - allowed_scopes
    if illegal:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported scope(s): {', '.join(sorted(illegal))}",
        )

    client_id = generate_client_id()
    row = await oauth_client_crud.create(
        db,
        client_id=client_id,
        client_name=payload.client_name,
        client_uri=str(payload.client_uri) if payload.client_uri else None,
        logo_uri=str(payload.logo_uri) if payload.logo_uri else None,
        redirect_uris=[str(u) for u in payload.redirect_uris],
        grant_types=list(payload.grant_types),
        response_types=list(payload.response_types),
        scope=payload.scope,
        token_endpoint_auth_method=payload.token_endpoint_auth_method,
    )

    logger.info(
        "oauth.dcr.register client_id=%s name=%r redirect_count=%d",
        row.client_id,
        row.client_name,
        len(row.redirect_uri_list),
    )

    return ClientRegistrationResponse(
        client_id=row.client_id,
        client_id_issued_at=int(time.mktime(row.created_at.timetuple())),
        client_name=row.client_name,
        client_uri=row.client_uri,
        logo_uri=row.logo_uri,
        redirect_uris=row.redirect_uri_list,
        grant_types=row.grant_type_list,
        response_types=row.response_type_list,
        token_endpoint_auth_method=row.token_endpoint_auth_method,
        scope=row.scope,
    )


# ---------------------------------------------------------------------------
# Token endpoint (RFC 6749 §4.1.3 authorization_code + §6 refresh_token)
# ---------------------------------------------------------------------------

@router.post(
    "/token",
    summary="OAuth 2.1 token endpoint (authorization_code + refresh_token)",
)
async def token_endpoint(
    request: Request,
    grant_type: str = Form(...),
    # authorization_code grant
    code: Optional[str] = Form(None),
    redirect_uri: Optional[str] = Form(None),
    code_verifier: Optional[str] = Form(None),
    # both grants
    client_id: Optional[str] = Form(None),
    resource: Optional[str] = Form(None),
    # refresh_token grant
    refresh_token: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    if grant_type == "authorization_code":
        return await _grant_authorization_code(
            db=db,
            code=code,
            redirect_uri=redirect_uri,
            client_id=client_id,
            code_verifier=code_verifier,
            resource=resource,
        )
    if grant_type == "refresh_token":
        return await _grant_refresh_token(
            db=db,
            refresh_token=refresh_token,
            client_id=client_id,
        )
    return _oauth_error(
        error="unsupported_grant_type",
        error_description=f"grant_type={grant_type!r} not supported",
    )


async def _grant_authorization_code(
    *,
    db: AsyncSession,
    code: Optional[str],
    redirect_uri: Optional[str],
    client_id: Optional[str],
    code_verifier: Optional[str],
    resource: Optional[str],
) -> JSONResponse:
    if not (code and redirect_uri and client_id and code_verifier):
        return _oauth_error(
            error="invalid_request",
            error_description=(
                "code, redirect_uri, client_id and code_verifier are required"
            ),
        )

    client = await oauth_client_crud.get_by_client_id(db, client_id)
    if client is None:
        return _oauth_error(
            error="invalid_client",
            error_description="unknown or inactive client_id",
            status_code=401,
        )

    auth_code = await oauth_authorization_code_crud.consume(db, code)
    if auth_code is None:
        return _oauth_error(
            error="invalid_grant",
            error_description="authorization code is invalid, expired, or already used",
        )

    if auth_code.client_id != client.client_id:
        return _oauth_error(
            error="invalid_grant",
            error_description="authorization code was issued to a different client",
        )

    if auth_code.redirect_uri != redirect_uri:
        return _oauth_error(
            error="invalid_grant",
            error_description="redirect_uri must match the original authorize request",
        )

    if not verify_pkce_s256(
        code_verifier=code_verifier,
        code_challenge=auth_code.code_challenge,
    ):
        return _oauth_error(
            error="invalid_grant",
            error_description="PKCE verification failed",
        )

    # Resource indicator (RFC 8707) — same normalization as /oauth/authorize
    # to handle clients that re-add the trailing slash on this leg of the flow.
    requested_resource = (resource or auth_code.resource).rstrip("/")
    if requested_resource != auth_code.resource.rstrip("/"):
        return _oauth_error(
            error="invalid_grant",
            error_description="resource must match the original authorize request",
        )

    return await _emit_tokens(
        db=db,
        client_id=client.client_id,
        user_id=auth_code.user_id,
        scope=auth_code.scope,
        resource=auth_code.resource,
    )


async def _grant_refresh_token(
    *,
    db: AsyncSession,
    refresh_token: Optional[str],
    client_id: Optional[str],
) -> JSONResponse:
    if not (refresh_token and client_id):
        return _oauth_error(
            error="invalid_request",
            error_description="refresh_token and client_id are required",
        )

    client = await oauth_client_crud.get_by_client_id(db, client_id)
    if client is None:
        return _oauth_error(
            error="invalid_client",
            error_description="unknown or inactive client_id",
            status_code=401,
        )

    old_row = await oauth_refresh_token_crud.get_by_plain(db, refresh_token)
    if old_row is None or not old_row.is_active:
        return _oauth_error(
            error="invalid_grant",
            error_description="refresh token is invalid, revoked, or expired",
        )

    if old_row.client_id != client.client_id:
        return _oauth_error(
            error="invalid_grant",
            error_description="refresh token was issued to a different client",
        )

    return await _emit_tokens(
        db=db,
        client_id=client.client_id,
        user_id=old_row.user_id,
        scope=old_row.scope,
        resource=old_row.resource,
        rotating_from=old_row,
    )


async def _emit_tokens(
    *,
    db: AsyncSession,
    client_id: str,
    user_id,
    scope: str,
    resource: str,
    rotating_from=None,
) -> JSONResponse:
    """Mint an access + refresh token pair. Handles refresh rotation."""
    user = await user_crud.get_with_roles(db, id=user_id)
    if user is None or not user.is_active:
        return _oauth_error(
            error="invalid_grant",
            error_description="associated user is inactive or removed",
        )

    base_payload = await build_user_token_payload(db, user)
    access_token, ttl = build_oauth_access_token(
        base_payload=base_payload,
        client_id=client_id,
        scope=scope,
        resource=resource,
        issuer=settings.OAUTH_ISSUER_URL,
        ttl_seconds=settings.OAUTH_ACCESS_TOKEN_TTL_SECONDS,
    )

    plain_refresh = generate_refresh_token()
    if rotating_from is None:
        await oauth_refresh_token_crud.mint(
            db,
            plain_token=plain_refresh,
            client_id=client_id,
            user_id=user_id,
            scope=scope,
            resource=resource,
            ttl_days=settings.OAUTH_REFRESH_TOKEN_TTL_DAYS,
        )
    else:
        await oauth_refresh_token_crud.rotate(
            db, old_row=rotating_from, new_plain_token=plain_refresh
        )

    logger.info(
        "oauth.token.issue client_id=%s user_id=%s scope=%s rotated=%s",
        client_id,
        user_id,
        scope,
        rotating_from is not None,
    )

    return JSONResponse(
        TokenResponse(
            access_token=access_token,
            token_type="Bearer",
            expires_in=ttl,
            refresh_token=plain_refresh,
            scope=scope,
        ).model_dump()
    )
