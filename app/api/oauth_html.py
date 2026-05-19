"""Browser-facing OAuth 2.1 endpoints (HTML pages).

This module owns three URLs the user's browser will visit during the
OAuth dance:

- ``GET  /oauth/authorize`` — entry point. Validates params, then either
  shows the login form (no session) or the consent form (logged in).
- ``POST /oauth/login``     — credentials submitted; on success, sets a
  signed session cookie and bounces back to ``/oauth/authorize`` so the
  consent form renders.
- ``POST /oauth/consent``   — user clicked Allow/Deny. On Allow we mint a
  short-lived authorization code and redirect back to the client's
  ``redirect_uri``.

Everything in this module is HTML/redirect — never JSON. The JSON-API
half of the flow (token exchange, DCR) lives in ``app.api.v1.oauth``.
"""
from __future__ import annotations

import logging
import urllib.parse
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.oauth import generate_authorization_code
from app.core.oauth_session import (
    COOKIE_NAME,
    issue_session_cookie,
    read_session_cookie,
)
from app.crud import (
    oauth_authorization_code_crud,
    oauth_client_crud,
    user_crud,
)
from app.models.oauth_client import OAuthClient
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Scope catalogue — single source of truth for what's shown on the consent page.
# When you add a new scope, list it here AND in the DCR endpoint's whitelist.
# ---------------------------------------------------------------------------

SCOPE_CATALOGUE = {
    "mcp:search": {
        "label": "Hukuk dökümanlarında arama yapma",
        "description": (
            "Mevzuat, içtihat, AYM kararları, Rekabet ve Reklam Kurulu "
            "arşivlerinde sizin adınıza arama yapabilir; sonuçları "
            "uygulamanın size göstermesini sağlar."
        ),
    },
}


# ---------------------------------------------------------------------------
# Param plumbing — we shuttle the same set of OAuth params across login,
# consent, and authorize render. This dict-passing keeps Jinja templates
# free of `request.query_params` access.
# ---------------------------------------------------------------------------

_OAUTH_FORWARDED_PARAMS = (
    "response_type",
    "client_id",
    "redirect_uri",
    "code_challenge",
    "code_challenge_method",
    "scope",
    "state",
    "resource",
)


def _collect_oauth_params(source: dict[str, str]) -> dict[str, str]:
    return {k: source.get(k, "") for k in _OAUTH_FORWARDED_PARAMS if source.get(k)}


def _error_response(
    request: Request,
    *,
    error: str,
    error_description: str,
    status_code: int = 400,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "oauth/error.html",
        {"error": error, "error_description": error_description},
        status_code=status_code,
    )


def _error_redirect(
    redirect_uri: str,
    *,
    error: str,
    error_description: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    """RFC 6749 §4.1.2.1 — bounce errors back via redirect_uri."""
    params = {"error": error}
    if error_description:
        params["error_description"] = error_description
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        f"{redirect_uri}{sep}{urllib.parse.urlencode(params)}",
        status_code=303,
    )


def _validate_client_and_redirect(
    client: Optional[OAuthClient],
    redirect_uri: str,
) -> Optional[str]:
    """Return an error string or None if everything checks out."""
    if client is None:
        return "unknown_client"
    if redirect_uri not in client.redirect_uri_list:
        return "redirect_uri_mismatch"
    return None


def _set_session(response: Response, user_id) -> None:
    """HttpOnly signed cookie. Lax SameSite — POST redirects from claude.ai
    must still carry it (login redirects within auth.onedocs.ai, same-site)."""
    response.set_cookie(
        COOKIE_NAME,
        issue_session_cookie(user_id),
        max_age=settings.OAUTH_SESSION_COOKIE_TTL_SECONDS,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        path="/oauth",  # cookie scoped to OAuth pages, not the whole API
    )


# ---------------------------------------------------------------------------
# GET /oauth/authorize
# ---------------------------------------------------------------------------

@router.get("/oauth/authorize", include_in_schema=False)
async def authorize_get(
    request: Request,
    response_type: str = "",
    client_id: str = "",
    redirect_uri: str = "",
    code_challenge: str = "",
    code_challenge_method: str = "",
    scope: str = "",
    state: str = "",
    resource: str = "",
    db: AsyncSession = Depends(get_db),
):
    # ---- Static validation: anything missing → error page (don't redirect,
    # we can't trust an unverified redirect_uri) ----
    if response_type != "code":
        return _error_response(
            request,
            error="unsupported_response_type",
            error_description="Only response_type=code is supported",
        )
    if not (client_id and redirect_uri and code_challenge and code_challenge_method):
        return _error_response(
            request,
            error="invalid_request",
            error_description="client_id, redirect_uri, code_challenge, code_challenge_method are required",
        )
    if code_challenge_method != "S256":
        return _error_response(
            request,
            error="invalid_request",
            error_description="code_challenge_method must be S256",
        )

    client = await oauth_client_crud.get_by_client_id(db, client_id)
    err = _validate_client_and_redirect(client, redirect_uri)
    if err:
        return _error_response(
            request,
            error=err,
            error_description=(
                "Unknown client_id" if err == "unknown_client"
                else "redirect_uri is not registered for this client"
            ),
        )

    # ---- Spec-compliant errors that DO redirect (we've validated client + uri) ----
    requested_scopes = set((scope or "").split()) or {"mcp:search"}
    allowed = client.scope_set
    if not requested_scopes.issubset(allowed):
        return _error_redirect(
            redirect_uri,
            error="invalid_scope",
            error_description=(
                "Requested scopes exceed client registration: "
                + ", ".join(sorted(requested_scopes - allowed))
            ),
            state=state,
        )

    expected_resource = settings.OAUTH_MCP_RESOURCE_URL
    if resource and resource != expected_resource:
        return _error_redirect(
            redirect_uri,
            error="invalid_target",
            error_description=f"resource must be {expected_resource}",
            state=state,
        )

    oauth_params = _collect_oauth_params(
        dict(request.query_params)
    )
    # Force resource into the forwarded params so login/consent POSTs carry it.
    oauth_params.setdefault("resource", expected_resource)

    # ---- Session check: logged in already? ----
    session_user_id = read_session_cookie(request.cookies.get(COOKIE_NAME))
    if session_user_id:
        user = await user_crud.get_with_roles(db, id=session_user_id)
        if user is not None and user.is_active:
            return await _render_consent(
                request, db=db,
                client=client,
                user=user,
                oauth_params=oauth_params,
                requested_scopes=requested_scopes,
            )

    # Not logged in → render login form
    return templates.TemplateResponse(
        request,
        "oauth/login.html",
        {
            "client_name": client.client_name,
            "oauth_params": oauth_params,
            "email": "",
            "error": None,
        },
    )


# ---------------------------------------------------------------------------
# POST /oauth/login
# ---------------------------------------------------------------------------

@router.post("/oauth/login", include_in_schema=False)
async def login_post(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    response_type: str = Form(""),
    client_id: str = Form(""),
    redirect_uri: str = Form(""),
    code_challenge: str = Form(""),
    code_challenge_method: str = Form(""),
    scope: str = Form(""),
    state: str = Form(""),
    resource: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    # Re-validate the client first; never set a cookie based on an
    # unverified redirect_uri.
    client = await oauth_client_crud.get_by_client_id(db, client_id)
    if client is None or redirect_uri not in client.redirect_uri_list:
        return _error_response(
            request,
            error="invalid_client",
            error_description="client_id / redirect_uri mismatch",
        )

    user = await user_crud.authenticate(db, email=email, password=password)
    oauth_params = {
        "response_type": response_type,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "scope": scope,
        "state": state,
        "resource": resource or settings.OAUTH_MCP_RESOURCE_URL,
    }
    oauth_params = {k: v for k, v in oauth_params.items() if v}

    if user is None or not user.is_active:
        return templates.TemplateResponse(
            request,
            "oauth/login.html",
            {
                "client_name": client.client_name,
                "oauth_params": oauth_params,
                "email": email,
                "error": "E-posta veya şifre hatalı.",
            },
            status_code=401,
        )

    logger.info(
        "oauth.login.success client_id=%s user_id=%s", client_id, user.id
    )

    # Set session cookie and redirect to /oauth/authorize → consent renders.
    redirect = RedirectResponse(
        f"/oauth/authorize?{urllib.parse.urlencode(oauth_params)}",
        status_code=303,
    )
    _set_session(redirect, user.id)
    return redirect


# ---------------------------------------------------------------------------
# POST /oauth/consent
# ---------------------------------------------------------------------------

@router.post("/oauth/consent", include_in_schema=False)
async def consent_post(
    request: Request,
    decision: str = Form(...),
    response_type: str = Form(""),
    client_id: str = Form(""),
    redirect_uri: str = Form(""),
    code_challenge: str = Form(""),
    code_challenge_method: str = Form(""),
    scope: str = Form(""),
    state: str = Form(""),
    resource: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    client = await oauth_client_crud.get_by_client_id(db, client_id)
    if client is None or redirect_uri not in client.redirect_uri_list:
        return _error_response(
            request,
            error="invalid_client",
            error_description="client_id / redirect_uri mismatch",
        )

    session_user_id = read_session_cookie(request.cookies.get(COOKIE_NAME))
    if not session_user_id:
        # Session expired between authorize render and consent submit.
        # Bounce back through /oauth/authorize so login form renders.
        params = {
            "response_type": response_type, "client_id": client_id,
            "redirect_uri": redirect_uri, "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method, "scope": scope,
            "state": state, "resource": resource or settings.OAUTH_MCP_RESOURCE_URL,
        }
        params = {k: v for k, v in params.items() if v}
        return RedirectResponse(
            f"/oauth/authorize?{urllib.parse.urlencode(params)}",
            status_code=303,
        )

    if decision == "deny":
        logger.info(
            "oauth.consent.deny client_id=%s user_id=%s", client_id, session_user_id
        )
        return _error_redirect(
            redirect_uri,
            error="access_denied",
            error_description="User denied the authorization request",
            state=state,
        )

    if decision != "allow":
        return _error_response(
            request,
            error="invalid_request",
            error_description="decision must be 'allow' or 'deny'",
        )

    # ---- Mint authorization code ----
    granted_scope = scope or "mcp:search"
    bound_resource = resource or settings.OAUTH_MCP_RESOURCE_URL
    plain_code = generate_authorization_code()
    await oauth_authorization_code_crud.mint(
        db,
        plain_code=plain_code,
        client_id=client_id,
        user_id=session_user_id,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        scope=granted_scope,
        resource=bound_resource,
        ttl_seconds=settings.OAUTH_AUTHORIZATION_CODE_TTL_SECONDS,
    )

    logger.info(
        "oauth.consent.allow client_id=%s user_id=%s scope=%s",
        client_id, session_user_id, granted_scope,
    )

    params = {"code": plain_code}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        f"{redirect_uri}{sep}{urllib.parse.urlencode(params)}",
        status_code=303,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _render_consent(
    request: Request,
    *,
    db: AsyncSession,
    client: OAuthClient,
    user: User,
    oauth_params: dict[str, str],
    requested_scopes: set[str],
) -> HTMLResponse:
    scopes = [
        {
            "name": s,
            "label": SCOPE_CATALOGUE[s]["label"],
            "description": SCOPE_CATALOGUE[s]["description"],
        }
        for s in sorted(requested_scopes)
        if s in SCOPE_CATALOGUE
    ]
    return templates.TemplateResponse(
        request,
        "oauth/consent.html",
        {
            "client_name": client.client_name,
            "scopes": scopes,
            "oauth_params": oauth_params,
            "user_email": user.email,
        },
    )
