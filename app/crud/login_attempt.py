"""
CRUD + gate-evaluation helpers for LoginAttempt.

Append-only attempt logging plus the progressive brute-force policy
described in alembic revision loginatt_59e042e5. The login endpoint
calls `evaluate_gate(...)` before checking the password and
`record_attempt(...)` after producing a verdict.

Successful login (or password reset) implicitly resets the email window:
`_last_success_at()` returns the most recent success row, and every
windowed count uses that as a lower bound. The IP axis is not reset on
success — a suspicious IP stays suspicious even if one of its targeted
accounts authenticates.
"""
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.login_attempt import LoginAttempt


# Policy constants — overridable via env for staging tuning. Defaults match
# the policy table documented in the alembic migration.
LOGIN_GATE_CAPTCHA_THRESHOLD = int(os.getenv("LOGIN_GATE_CAPTCHA_THRESHOLD", "3"))
LOGIN_GATE_COOLDOWN_THRESHOLD = int(os.getenv("LOGIN_GATE_COOLDOWN_THRESHOLD", "6"))
LOGIN_GATE_LOCK_THRESHOLD = int(os.getenv("LOGIN_GATE_LOCK_THRESHOLD", "10"))

LOGIN_GATE_CAPTCHA_WINDOW_MINUTES = int(os.getenv("LOGIN_GATE_CAPTCHA_WINDOW_MINUTES", "15"))
LOGIN_GATE_COOLDOWN_WINDOW_MINUTES = int(os.getenv("LOGIN_GATE_COOLDOWN_WINDOW_MINUTES", "60"))
LOGIN_GATE_LOCK_WINDOW_HOURS = int(os.getenv("LOGIN_GATE_LOCK_WINDOW_HOURS", "24"))

LOGIN_GATE_COOLDOWN_DURATION_MINUTES = int(os.getenv("LOGIN_GATE_COOLDOWN_DURATION_MINUTES", "15"))
LOGIN_GATE_LOCK_DURATION_HOURS = int(os.getenv("LOGIN_GATE_LOCK_DURATION_HOURS", "24"))


class GateAction(str, Enum):
    ALLOW = "allow"
    CAPTCHA_REQUIRED = "captcha_required"
    COOLDOWN = "cooldown"
    LOCKED = "locked"


@dataclass
class GateDecision:
    action: GateAction
    failed_count: int = 0
    retry_after_seconds: Optional[int] = None
    locked_until: Optional[datetime] = None
    # Which axis triggered the gate ("email" | "ip" | None) — for logs.
    triggered_by: Optional[str] = None


def _normalize_email(email: str) -> str:
    return email.lower().strip()


async def record_attempt(
    db: AsyncSession,
    *,
    email: str,
    ip_address: Optional[str],
    success: bool,
    failure_reason: Optional[str] = None,
) -> LoginAttempt:
    """Append a single row. Commits in the caller's transaction."""
    attempt = LoginAttempt(
        email=_normalize_email(email),
        ip_address=ip_address,
        success=success,
        failure_reason=failure_reason,
    )
    db.add(attempt)
    await db.flush()
    return attempt


async def _last_success_at(db: AsyncSession, *, email: str) -> Optional[datetime]:
    stmt = (
        select(func.max(LoginAttempt.created_at))
        .where(
            and_(
                LoginAttempt.email == _normalize_email(email),
                LoginAttempt.success.is_(True),
            )
        )
    )
    result = await db.execute(stmt)
    return result.scalar()


async def _count_failures(
    db: AsyncSession,
    *,
    since: datetime,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> int:
    conditions = [
        LoginAttempt.success.is_(False),
        LoginAttempt.created_at >= since,
    ]
    if email is not None:
        conditions.append(LoginAttempt.email == _normalize_email(email))
    if ip_address is not None:
        conditions.append(LoginAttempt.ip_address == ip_address)
    stmt = select(func.count(LoginAttempt.id)).where(and_(*conditions))
    result = await db.execute(stmt)
    return result.scalar() or 0


async def evaluate_gate(
    db: AsyncSession,
    *,
    email: str,
    ip_address: Optional[str] = None,
) -> GateDecision:
    """
    Decide what (if any) gate the next login attempt must clear.

    Both axes are evaluated and the strictest outcome wins:
      LOCKED > COOLDOWN > CAPTCHA_REQUIRED > ALLOW

    Email axis: only failures after the last successful login count, so a
    user who legitimately logs in does not stay penalized for earlier
    fat-finger attempts. IP axis: not reset on success — a spraying IP
    stays suspicious across every account it tried.
    """
    now = datetime.utcnow()
    lock_window_start = now - timedelta(hours=LOGIN_GATE_LOCK_WINDOW_HOURS)
    cooldown_window_start = now - timedelta(minutes=LOGIN_GATE_COOLDOWN_WINDOW_MINUTES)
    captcha_window_start = now - timedelta(minutes=LOGIN_GATE_CAPTCHA_WINDOW_MINUTES)

    # Email axis — cap the lower bound by the last success (if any).
    last_success = await _last_success_at(db, email=email)
    email_lower_bound = (
        max(lock_window_start, last_success) if last_success else lock_window_start
    )

    email_24h = await _count_failures(db, email=email, since=email_lower_bound)
    email_1h = await _count_failures(
        db, email=email, since=max(email_lower_bound, cooldown_window_start)
    )
    email_15m = await _count_failures(
        db, email=email, since=max(email_lower_bound, captcha_window_start)
    )

    # IP axis — only meaningful if we actually captured an IP.
    ip_24h = ip_1h = ip_15m = 0
    if ip_address:
        ip_24h = await _count_failures(db, ip_address=ip_address, since=lock_window_start)
        ip_1h = await _count_failures(db, ip_address=ip_address, since=cooldown_window_start)
        ip_15m = await _count_failures(db, ip_address=ip_address, since=captcha_window_start)

    # Resolve strictest tier; remember which axis crossed it first.
    def _pick(email_count: int, ip_count: int) -> tuple[int, str]:
        return (email_count, "email") if email_count >= ip_count else (ip_count, "ip")

    lock_count, lock_axis = _pick(email_24h, ip_24h)
    if lock_count >= LOGIN_GATE_LOCK_THRESHOLD:
        return GateDecision(
            action=GateAction.LOCKED,
            failed_count=lock_count,
            locked_until=now + timedelta(hours=LOGIN_GATE_LOCK_DURATION_HOURS),
            triggered_by=lock_axis,
        )

    cooldown_count, cooldown_axis = _pick(email_1h, ip_1h)
    if cooldown_count >= LOGIN_GATE_COOLDOWN_THRESHOLD:
        return GateDecision(
            action=GateAction.COOLDOWN,
            failed_count=cooldown_count,
            retry_after_seconds=LOGIN_GATE_COOLDOWN_DURATION_MINUTES * 60,
            triggered_by=cooldown_axis,
        )

    captcha_count, captcha_axis = _pick(email_15m, ip_15m)
    if captcha_count >= LOGIN_GATE_CAPTCHA_THRESHOLD:
        return GateDecision(
            action=GateAction.CAPTCHA_REQUIRED,
            failed_count=captcha_count,
            triggered_by=captcha_axis,
        )

    return GateDecision(action=GateAction.ALLOW)


async def reset_email_window(
    db: AsyncSession,
    *,
    email: str,
    reason: str = "admin_unlock",
) -> None:
    """
    Reset the email axis by recording a synthetic success row. Subsequent
    `evaluate_gate` calls treat this timestamp as the window floor, so
    earlier failures stop counting. The IP axis is left alone on purpose.

    Used by:
      - /reset-password success path (mail-link self-service)
      - admin unlock endpoint
    """
    attempt = LoginAttempt(
        email=_normalize_email(email),
        ip_address=None,
        success=True,
        failure_reason=reason,
    )
    db.add(attempt)
    await db.flush()
