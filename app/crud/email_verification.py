"""
CRUD operations for EmailVerification model.
"""
import os
import random
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_verification import EmailVerification


# Configuration from environment
EMAIL_CODE_LENGTH = int(os.getenv("BACKEND_EMAIL_CODE_LENGTH", "6"))
EMAIL_CODE_EXPIRES_MINUTES = int(os.getenv("BACKEND_EMAIL_CODE_EXPIRES_IN", "30"))
EMAIL_RESEND_COOLDOWN_SECONDS = int(os.getenv("EMAIL_RESEND_COOLDOWN_SECONDS", "60"))
MAX_VERIFICATION_ATTEMPTS = 5


def generate_verification_code() -> str:
    """
    Generate a random 6-digit verification code.

    Returns:
        6-digit numeric string
    """
    code_length = EMAIL_CODE_LENGTH
    min_value = 10 ** (code_length - 1)
    max_value = (10 ** code_length) - 1
    return str(random.randint(min_value, max_value))


async def create_verification_code(
    db: AsyncSession,
    *,
    user_id: UUID,
    email: str
) -> EmailVerification:
    """
    Create a new verification code for a user.

    Args:
        db: Database session
        user_id: User ID
        email: Email address

    Returns:
        Created EmailVerification record
    """
    code = generate_verification_code()
    expires_at = datetime.utcnow() + timedelta(minutes=EMAIL_CODE_EXPIRES_MINUTES)

    verification = EmailVerification(
        user_id=user_id,
        email=email,
        code=code,
        expires_at=expires_at,
        is_used=False,
        attempts=0
    )

    db.add(verification)
    await db.commit()
    await db.refresh(verification)

    return verification


async def get_latest_code(
    db: AsyncSession,
    *,
    email: str
) -> Optional[EmailVerification]:
    """
    Get the most recent verification code for an email.

    Args:
        db: Database session
        email: Email address

    Returns:
        Latest EmailVerification record or None
    """
    stmt = (
        select(EmailVerification)
        .where(EmailVerification.email == email)
        .order_by(desc(EmailVerification.created_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_code_and_email(
    db: AsyncSession,
    *,
    email: str,
    code: str
) -> Optional[EmailVerification]:
    """
    Get verification record by email and code.

    Args:
        db: Database session
        email: Email address
        code: Verification code

    Returns:
        EmailVerification record or None
    """
    stmt = (
        select(EmailVerification)
        .where(
            and_(
                EmailVerification.email == email,
                EmailVerification.code == code
            )
        )
        .order_by(desc(EmailVerification.created_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def validate_code(
    db: AsyncSession,
    *,
    email: str,
    code: str
) -> tuple[bool, str, Optional[EmailVerification]]:
    """
    Validate a verification code.

    Args:
        db: Database session
        email: Email address
        code: Verification code

    Returns:
        Tuple of (is_valid, error_message, verification_record)
    """
    verification = await get_by_code_and_email(db, email=email, code=code)

    if not verification:
        return False, "Geçersiz doğrulama kodu", None

    # Check if already used
    if verification.is_used:
        return False, "Bu kod daha önce kullanılmış", verification

    # Check expiry
    if datetime.utcnow() > verification.expires_at:
        return False, "Kod süresi dolmuş. Lütfen yeni kod isteyin", verification

    # Check max attempts
    if verification.attempts >= MAX_VERIFICATION_ATTEMPTS:
        return False, "Maksimum deneme sayısı aşıldı. Lütfen yeni kod isteyin", verification

    return True, "", verification


async def mark_as_used(
    db: AsyncSession,
    *,
    verification: EmailVerification
) -> EmailVerification:
    """
    Mark a verification code as used.

    Args:
        db: Database session
        verification: EmailVerification record

    Returns:
        Updated EmailVerification record
    """
    verification.is_used = True
    db.add(verification)
    await db.commit()
    await db.refresh(verification)
    return verification


async def increment_attempts(
    db: AsyncSession,
    *,
    verification: EmailVerification
) -> EmailVerification:
    """
    Increment failed verification attempts.

    Args:
        db: Database session
        verification: EmailVerification record

    Returns:
        Updated EmailVerification record
    """
    verification.attempts += 1
    db.add(verification)
    await db.commit()
    await db.refresh(verification)
    return verification


async def check_resend_cooldown(
    db: AsyncSession,
    *,
    email: str
) -> tuple[bool, int]:
    """
    Check if user can request a new verification code (60s cooldown).

    Args:
        db: Database session
        email: Email address

    Returns:
        Tuple of (can_resend, seconds_remaining)
    """
    latest_code = await get_latest_code(db, email=email)

    if not latest_code:
        return True, 0

    time_since_creation = datetime.utcnow() - latest_code.created_at
    seconds_elapsed = int(time_since_creation.total_seconds())

    if seconds_elapsed >= EMAIL_RESEND_COOLDOWN_SECONDS:
        return True, 0

    seconds_remaining = EMAIL_RESEND_COOLDOWN_SECONDS - seconds_elapsed
    return False, seconds_remaining


async def invalidate_old_codes(
    db: AsyncSession,
    *,
    email: str
) -> None:
    """
    Mark all old codes for an email as used (when generating new code).

    Args:
        db: Database session
        email: Email address
    """
    stmt = (
        select(EmailVerification)
        .where(
            and_(
                EmailVerification.email == email,
                EmailVerification.is_used == False
            )
        )
    )
    result = await db.execute(stmt)
    old_codes = result.scalars().all()

    for code in old_codes:
        code.is_used = True
        db.add(code)

    await db.commit()
