"""
Guest user OTP login.

Two endpoints:
- POST /auth/guest/request-otp  — sends a 6-digit code to the email
- POST /auth/guest/verify-otp   — exchanges the code for a JWT

The verify endpoint issues a real access/refresh token pair so the same
client code that consumes /auth/login can consume this — the JWT shape
is identical, with portals[] populated for portal-member users.

We do not pre-check whether the email exists at request-otp time: doing
so leaks "is this user registered" to anyone who can POST. Verify is the
gate that returns 401 when no user matches the email.
"""
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import jwt_handler, password_handler
from app.crud import (
    organization_crud,
    otp_code_crud,
    refresh_token_crud,
    user_crud,
)
from app.crud.otp_code import RATE_LIMIT_MAX_REQUESTS
from app.models import User
from app.schemas.auth import TokenResponse
from app.services import send_otp_email
from app.services.token_service import build_user_token_payload

router = APIRouter()


class RequestOtpBody(BaseModel):
    email: EmailStr


class RequestOtpResponse(BaseModel):
    message: str
    expires_in_minutes: int = 60


class VerifyOtpBody(BaseModel):
    email: EmailStr
    code: str


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


@router.post(
    "/request-otp",
    response_model=RequestOtpResponse,
    summary="Send a one-time login code to an email",
)
async def request_otp(
    body: RequestOtpBody,
    request: Request,
    x_org_slug: Optional[str] = Header(default=None, alias="X-Org-Slug"),
    db: AsyncSession = Depends(get_db),
):
    """Generic-message endpoint by design — we always claim the code was
    sent so the response can't be used as an account-existence oracle.

    Rate-limit: max RATE_LIMIT_MAX_REQUESTS per email per hour. Past the
    limit we return success but skip the actual send.
    """
    email = body.email.lower().strip()

    organization_id = None
    organization_name = None
    if x_org_slug:
        org = await organization_crud.get_by_slug(db, slug=x_org_slug.lower())
        if org is not None and org.is_active:
            organization_id = org.id
            organization_name = org.name

    recent = await otp_code_crud.count_recent_requests(db, email=email)
    if recent >= RATE_LIMIT_MAX_REQUESTS:
        # Silent drop — generic response masks rate-limit existence.
        return RequestOtpResponse(message="Kod e-postanıza gönderildi.")

    row, plaintext = await otp_code_crud.issue(
        db,
        email=email,
        organization_id=organization_id,
        requested_ip=(request.client.host if request.client else None),
        requested_user_agent=request.headers.get("user-agent"),
    )
    await db.commit()

    # Best-effort send — failure does not flip the response.
    try:
        await send_otp_email(
            email=email, code=plaintext, organization_name=organization_name
        )
    except Exception as exc:  # pragma: no cover — side-effect
        print(f"⚠️ OTP email send failed for {email}: {exc}")

    return RequestOtpResponse(message="Kod e-postanıza gönderildi.")


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


def _generic_invalid() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kod geçersiz veya süresi dolmuş",
    )


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    summary="Exchange an OTP code for a JWT token pair",
)
async def verify_otp(
    body: VerifyOtpBody,
    db: AsyncSession = Depends(get_db),
):
    email = body.email.lower().strip()
    code = "".join(c for c in body.code if c.isdigit())
    if len(code) < 4:
        # Format guard — too short can't be a valid code.
        raise _generic_invalid()

    ok, _row, _reason = await otp_code_crud.verify(db, email=email, code=code)
    await db.commit()
    if not ok:
        raise _generic_invalid()

    user = await user_crud.get_by_email(db, email=email)
    if user is None:
        # OTP succeeded but no account exists — verify is the gate, not
        # request-otp, so we tell the client the same generic message.
        raise _generic_invalid()
    if not user.is_active:
        raise _generic_invalid()

    # OTP login implies the user has confirmed control of the email; if
    # they were unverified (e.g. legacy account) flip the flag now.
    if not user.is_verified:
        user.is_verified = True
        db.add(user)

    # Refresh roles eagerly so the token payload sees them.
    user = await user_crud.get_with_roles(db, id=user.id)
    await user_crud.update_last_login(db, user=user)

    token_data = await build_user_token_payload(db, user)
    access_token = jwt_handler.create_access_token(token_data)
    refresh_token = jwt_handler.create_refresh_token({"sub": str(user.id)})
    await refresh_token_crud.create(
        db=db, user_id=user.id, token=refresh_token, device_info=None
    )
    await db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        needs_onboarding=user.organization_id is None,
    )


# ---------------------------------------------------------------------------
# Helpers reused by invitation-accept (kept here so the secret-generation
# rules live next to the OTP code)
# ---------------------------------------------------------------------------


def generate_guest_user_password() -> str:
    """Random unguessable password for Guest user rows.

    Guest users log in via OTP, never password. We still need a value
    for users.password_hash (NOT NULL); generating something tokens.urlsafe
    sized makes sure no one can brute-force their way in if the column is
    ever queried directly. Length comfortably above bcrypt's 72-byte cap.
    """
    return secrets.token_urlsafe(48)


def hash_guest_password(plain: str) -> str:
    return password_handler.hash_password(plain)
