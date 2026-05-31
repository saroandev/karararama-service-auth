"""
CRUD + helpers for OtpCode (Guest user email codes).

Codes are 6-digit, generated with the system random source. We never
store the plaintext anywhere — only SHA-256(code). Verification
constant-time compares the hash.
"""
from datetime import datetime, timedelta
from hashlib import sha256
from secrets import choice
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.otp_code import OtpCode


# Policy constants — single source of truth for the verify path.
OTP_TTL = timedelta(hours=1)
RATE_LIMIT_WINDOW = timedelta(hours=1)
RATE_LIMIT_MAX_REQUESTS = 5     # max OTP requests per email per window
MAX_ATTEMPTS_PER_CODE = 5       # max wrong-guess attempts before a code is dead
CODE_LENGTH = 6


def _generate_code() -> str:
    """Cryptographically-random 6-digit code, leading zeros preserved."""
    return "".join(choice("0123456789") for _ in range(CODE_LENGTH))


def _hash_code(code: str) -> str:
    """SHA-256 hex digest of the code — what we store and compare."""
    return sha256(code.encode("utf-8")).hexdigest()


class CRUDOtpCode:
    """CRUD operations for OtpCode."""

    # ------------------------------------------------------------------
    # Issue
    # ------------------------------------------------------------------

    async def count_recent_requests(
        self, db: AsyncSession, *, email: str
    ) -> int:
        """Count how many OTP rows we created for this email in the
        rate-limit window — both consumed and unconsumed count."""
        since = datetime.utcnow() - RATE_LIMIT_WINDOW
        stmt = select(func.count(OtpCode.id)).where(
            OtpCode.email == email,
            OtpCode.created_at >= since,
        )
        return int((await db.execute(stmt)).scalar() or 0)

    async def issue(
        self,
        db: AsyncSession,
        *,
        email: str,
        organization_id: Optional[UUID] = None,
        requested_ip: Optional[str] = None,
        requested_user_agent: Optional[str] = None,
    ) -> tuple[OtpCode, str]:
        """Create a new code row and return (row, plaintext_code).

        The plaintext is returned exactly once — the caller is expected
        to immediately hand it off to the email sender. Anything else
        (logs, response bodies) is a security regression.
        """
        # Mark any prior unconsumed codes for this email as consumed so
        # the new one is the only valid target. Stops the "two codes
        # sent in quick succession, attacker uses the older one" race.
        await db.execute(
            OtpCode.__table__.update()
            .where(
                OtpCode.email == email,
                OtpCode.consumed_at.is_(None),
                OtpCode.expires_at > datetime.utcnow(),
            )
            .values(consumed_at=datetime.utcnow())
        )

        plaintext = _generate_code()
        row = OtpCode(
            email=email,
            code_hash=_hash_code(plaintext),
            organization_id=organization_id,
            expires_at=datetime.utcnow() + OTP_TTL,
            requested_ip=requested_ip,
            requested_user_agent=requested_user_agent,
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)
        return row, plaintext

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    async def get_active_for_email(
        self, db: AsyncSession, *, email: str
    ) -> Optional[OtpCode]:
        """Most recent unconsumed unexpired OTP row for this email."""
        stmt = (
            select(OtpCode)
            .where(
                OtpCode.email == email,
                OtpCode.consumed_at.is_(None),
                OtpCode.expires_at > datetime.utcnow(),
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    async def verify(
        self, db: AsyncSession, *, email: str, code: str
    ) -> tuple[bool, Optional[OtpCode], Optional[str]]:
        """Try to consume an OTP code.

        Returns (success, row, error_reason). `error_reason` is one of
            None / "no_active_code" / "too_many_attempts" / "wrong_code"
        for the caller to map onto error messages without leaking which
        specific failure occurred (we tell the user a generic message).
        """
        row = await self.get_active_for_email(db, email=email)
        if row is None:
            return False, None, "no_active_code"
        if row.attempts >= MAX_ATTEMPTS_PER_CODE:
            return False, row, "too_many_attempts"
        if row.code_hash != _hash_code(code):
            row.attempts += 1
            db.add(row)
            await db.flush()
            return False, row, "wrong_code"
        row.consumed_at = datetime.utcnow()
        db.add(row)
        await db.flush()
        return True, row, None


otp_code_crud = CRUDOtpCode()
