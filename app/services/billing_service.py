"""
Billing service: order creation + PayTR-callback activation.

The flow is split in two so the frontend never sees raw money math:

    frontend → POST /billing/orders   → creates Payment(pending), returns merchant_oid + amount_kurus
    PayTR     → POST /billing/activate → flips Payment to success and creates Subscription

`activate` is idempotent on `merchant_oid` so PayTR retries are safe.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from base64 import b64encode
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import (
    BILLING_CYCLES,
    PAID_PLANS,
    PLAN_CATALOG,
    calculate_total_usd,
    validate_seat_count,
)
from app.models import Organization, Payment, Subscription, User
from app.services.exchange_rate import get_usd_try_rate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------


def _generate_merchant_oid(user_id: UUID) -> str:
    """PayTR merchant_oid: alphanumeric, ≤64 chars. Includes user id prefix for traceability."""
    ts = int(datetime.utcnow().timestamp())
    short_id = str(user_id).replace("-", "")[:12]
    suffix = secrets.token_hex(4)
    return f"OD{ts}{short_id}{suffix}"


async def create_order(
    db: AsyncSession,
    *,
    user: User,
    plan: str,
    billing_cycle: str,
    seat_count: int,
) -> Payment:
    """Validate inputs, snapshot prices, and persist a pending Payment row."""
    if plan not in PLAN_CATALOG:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown plan: {plan}")
    if PLAN_CATALOG[plan]["contact_sales_only"]:
        # Team/Elite/Enterprise satislari sales ekibi yurutuyor; self-service
        # PayTR akisi sadece Solo'ya acik.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{PLAN_CATALOG[plan]['name']} paketi satis ekibi tarafindan satilir; lutfen iletisime gecin.",
        )
    if billing_cycle not in BILLING_CYCLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown billing cycle: {billing_cycle}")
    if not validate_seat_count(plan, seat_count):
        definition = PLAN_CATALOG[plan]
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"seat_count must be between {definition['min_users']} and {definition['max_users']} for {plan}",
        )

    definition = PLAN_CATALOG[plan]
    # Live USD→TRY rate (with fallback chain). Source recorded in logs.
    live_rate, rate_source = get_usd_try_rate()
    rate = Decimal(str(live_rate))
    total_usd = Decimal(str(calculate_total_usd(plan, seat_count, billing_cycle)))
    total_try = (total_usd * rate).quantize(Decimal("0.01"))
    amount_kurus = int(total_try * 100)

    # Test override — replaces the kuruş amount but keeps the USD/rate snapshot
    # honest so accounting still shows what would have been charged at full price.
    if (
        settings.BILLING_TEST_OVERRIDE_AMOUNT_KURUS > 0
        and settings.BILLING_TEST_OVERRIDE_PLAN == plan
    ):
        logger.warning(
            "BILLING TEST OVERRIDE active: plan=%s seats=%s cycle=%s original=%s kuruş → %s kuruş",
            plan,
            seat_count,
            billing_cycle,
            amount_kurus,
            settings.BILLING_TEST_OVERRIDE_AMOUNT_KURUS,
        )
        amount_kurus = settings.BILLING_TEST_OVERRIDE_AMOUNT_KURUS

    logger.info(
        "Order: plan=%s seats=%s cycle=%s usd=%s rate=%s(%s) kuruş=%s",
        plan, seat_count, billing_cycle, total_usd, rate, rate_source, amount_kurus,
    )

    payment = Payment(
        user_id=user.id,
        organization_id=user.organization_id,
        merchant_oid=_generate_merchant_oid(user.id),
        plan=plan,
        billing_cycle=billing_cycle,
        seat_count=seat_count,
        storage_gb_per_user=Decimal(str(definition["storage_gb_per_user"])),
        amount_kurus=amount_kurus,
        amount_usd=total_usd,
        exchange_rate=rate,
        currency="TRY",
        status="pending",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    return payment


# ---------------------------------------------------------------------------
# PayTR callback verification + activation
# ---------------------------------------------------------------------------


def verify_paytr_callback_hash(merchant_oid: str, status_value: str, total_amount: str, received_hash: str) -> bool:
    """Verify the PayTR callback hash:

        hash = base64( HMAC_SHA256( merchant_oid + salt + status + total_amount,  merchant_key ) )

    Returns False if any secret is missing.
    """
    if not settings.PAYTR_MERCHANT_KEY or not settings.PAYTR_MERCHANT_SALT:
        logger.warning("PayTR secrets are not configured; cannot verify callback")
        return False

    message = f"{merchant_oid}{settings.PAYTR_MERCHANT_SALT}{status_value}{total_amount}".encode()
    digest = hmac.new(
        settings.PAYTR_MERCHANT_KEY.encode(),
        message,
        hashlib.sha256,
    ).digest()
    expected = b64encode(digest).decode()
    return hmac.compare_digest(expected, received_hash)


async def _get_active_subscription(db: AsyncSession, organization_id: UUID) -> Optional[Subscription]:
    stmt = (
        select(Subscription)
        .where(Subscription.organization_id == organization_id)
        .where(Subscription.status == "active")
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def activate_subscription(
    db: AsyncSession,
    *,
    merchant_oid: str,
    received_hash: str,
    status_value: str,
    total_amount: str,
    paytr_response: Optional[dict] = None,
    failed_reason: Optional[str] = None,
) -> Payment:
    """Apply a PayTR callback to the matching Payment row, idempotently.

    Success path:
      - mark payment success + completed_at
      - cancel any existing active Subscription for the org
      - create a new Subscription
      - bump the Organization's plan/seat/storage/expiry
    Failure path:
      - mark payment failed with reason

    Idempotency: re-running on an already-`success` payment is a no-op (the
    second activate call from PayTR retry must not double-charge or fail).
    """
    if not verify_paytr_callback_hash(merchant_oid, status_value, total_amount, received_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PayTR hash verification failed")

    stmt = select(Payment).where(Payment.merchant_oid == merchant_oid)
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Order not found: {merchant_oid}")

    # Idempotency: already terminal → return as-is
    if payment.status in ("success", "failed"):
        return payment

    # Money check (PayTR sends total_amount in kuruş as a string)
    try:
        callback_amount = int(total_amount)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid total_amount")
    if callback_amount != payment.amount_kurus:
        payment.status = "failed"
        payment.failed_reason = f"Amount mismatch: expected {payment.amount_kurus}, got {callback_amount}"
        payment.paytr_response = paytr_response
        await db.commit()
        await db.refresh(payment)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Amount mismatch")

    payment.paytr_response = paytr_response
    payment.completed_at = datetime.utcnow()

    if status_value != "success":
        payment.status = "failed"
        payment.failed_reason = failed_reason or f"PayTR reported status={status_value}"
        await db.commit()
        await db.refresh(payment)
        return payment

    # --- success branch -----------------------------------------------------
    org_id = payment.organization_id
    if org_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Payment has no organization linked")
    org = await db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organization not found")

    now = datetime.utcnow()
    months = BILLING_CYCLES[payment.billing_cycle]
    expires_at = now + timedelta(days=30 * months)

    # Cancel any existing active subscription for this org
    existing = await _get_active_subscription(db, org_id)
    if existing is not None:
        existing.status = "cancelled"

    sub = Subscription(
        organization_id=org_id,
        payment_id=payment.id,
        plan=payment.plan,
        billing_cycle=payment.billing_cycle,
        seat_count=payment.seat_count,
        storage_gb_per_user=payment.storage_gb_per_user,
        started_at=now,
        expires_at=expires_at,
        status="active",
    )
    db.add(sub)

    org.plan = payment.plan
    org.plan_started_at = now
    org.plan_expires_at = expires_at
    org.billing_cycle = payment.billing_cycle
    org.seat_count = payment.seat_count
    org.storage_gb_per_user = payment.storage_gb_per_user

    # If this upgrade puts the org on a whitelabel plan, mint a slug now
    # so <slug>.onedocs.ai works immediately. No-op for plans that don't
    # include the feature, and idempotent if the org already has a slug
    # (e.g. carried over from a previous Elite period before downgrade).
    from app.services.whitelabel import ensure_whitelabel_slug
    await ensure_whitelabel_slug(db, org=org)

    payment.status = "success"

    await db.commit()
    await db.refresh(payment)
    return payment


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


async def get_active_subscription_for_user(db: AsyncSession, user: User) -> Optional[Subscription]:
    if user.organization_id is None:
        return None
    return await _get_active_subscription(db, user.organization_id)


def is_paid_plan(plan: str) -> bool:
    return plan in PAID_PLANS
