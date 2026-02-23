"""
CRUD operations for PasswordResetToken model.
"""
import os
import secrets
import hashlib
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.password_reset import PasswordResetToken


# Configuration from environment
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30"))
PASSWORD_RESET_RATE_LIMIT_REQUESTS = int(os.getenv("PASSWORD_RESET_RATE_LIMIT_REQUESTS", "3"))
PASSWORD_RESET_RATE_LIMIT_WINDOW_HOURS = int(os.getenv("PASSWORD_RESET_RATE_LIMIT_WINDOW_HOURS", "1"))


def generate_reset_token() -> str:
    """
    Generate a secure random reset token (URL-safe, 43 characters).

    Returns:
        URL-safe reset token string
    """
    return secrets.token_urlsafe(32)  # Generates 43-character string


def hash_token(token: str) -> str:
    """
    Hash a reset token using SHA256.

    Args:
        token: Raw reset token

    Returns:
        SHA256 hex digest (64 characters)
    """
    return hashlib.sha256(token.encode()).hexdigest()


async def create_reset_token(
    db: AsyncSession,
    *,
    user_id: UUID,
    ip_address: Optional[str] = None
) -> tuple[PasswordResetToken, str]:
    """
    Create a new password reset token for a user.

    Args:
        db: Database session
        user_id: User ID
        ip_address: Optional IP address of requester (for audit)

    Returns:
        Tuple of (PasswordResetToken record, raw_token)
        NOTE: raw_token is only returned here and never stored in DB
    """
    # Generate raw token
    raw_token = generate_reset_token()
    token_hash = hash_token(raw_token)

    expires_at = datetime.utcnow() + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    reset_token = PasswordResetToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_used=False,
        ip_address=ip_address
    )

    db.add(reset_token)
    await db.commit()
    await db.refresh(reset_token)

    return reset_token, raw_token


async def get_by_token(
    db: AsyncSession,
    *,
    token: str
) -> Optional[PasswordResetToken]:
    """
    Get password reset record by raw token.

    Args:
        db: Database session
        token: Raw reset token (not hashed)

    Returns:
        PasswordResetToken record or None
    """
    token_hash = hash_token(token)

    stmt = (
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .order_by(desc(PasswordResetToken.created_at))
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_valid_token(
    db: AsyncSession,
    *,
    token: str
) -> Optional[PasswordResetToken]:
    """
    Get valid (not expired, not used) password reset token.

    Args:
        db: Database session
        token: Raw reset token

    Returns:
        PasswordResetToken record if valid, None otherwise
    """
    reset_token = await get_by_token(db, token=token)

    if not reset_token:
        return None

    if reset_token.is_used or reset_token.is_expired:
        return None

    return reset_token


async def mark_as_used(
    db: AsyncSession,
    *,
    reset_token: PasswordResetToken
) -> PasswordResetToken:
    """
    Mark a password reset token as used.

    Args:
        db: Database session
        reset_token: PasswordResetToken record

    Returns:
        Updated PasswordResetToken record
    """
    reset_token.is_used = True
    reset_token.used_at = datetime.utcnow()
    db.add(reset_token)
    await db.commit()
    await db.refresh(reset_token)
    return reset_token


async def invalidate_user_tokens(
    db: AsyncSession,
    *,
    user_id: UUID
) -> int:
    """
    Invalidate all unused password reset tokens for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Number of tokens invalidated
    """
    stmt = (
        select(PasswordResetToken)
        .where(
            and_(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.is_used == False
            )
        )
    )
    result = await db.execute(stmt)
    tokens = result.scalars().all()

    count = 0
    for token in tokens:
        token.is_used = True
        token.used_at = datetime.utcnow()
        db.add(token)
        count += 1

    await db.commit()
    return count


async def check_rate_limit(
    db: AsyncSession,
    *,
    user_id: UUID
) -> tuple[bool, int, int]:
    """
    Check if user has exceeded password reset rate limit.
    Default: 3 requests per hour.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Tuple of (can_request, requests_count, requests_remaining)
    """
    window_start = datetime.utcnow() - timedelta(hours=PASSWORD_RESET_RATE_LIMIT_WINDOW_HOURS)

    stmt = (
        select(func.count(PasswordResetToken.id))
        .where(
            and_(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.created_at >= window_start
            )
        )
    )
    result = await db.execute(stmt)
    request_count = result.scalar() or 0

    can_request = request_count < PASSWORD_RESET_RATE_LIMIT_REQUESTS
    requests_remaining = max(0, PASSWORD_RESET_RATE_LIMIT_REQUESTS - request_count)

    return can_request, request_count, requests_remaining


async def cleanup_expired_tokens(
    db: AsyncSession,
    *,
    days_old: int = 7
) -> int:
    """
    Delete expired password reset tokens older than specified days.
    This is for background cleanup task.

    Args:
        db: Database session
        days_old: Delete tokens expired more than this many days ago

    Returns:
        Number of tokens deleted
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    stmt = (
        select(PasswordResetToken)
        .where(
            and_(
                PasswordResetToken.expires_at < cutoff_date,
                PasswordResetToken.is_used == True
            )
        )
    )
    result = await db.execute(stmt)
    tokens = result.scalars().all()

    count = len(tokens)
    for token in tokens:
        await db.delete(token)

    await db.commit()
    return count
