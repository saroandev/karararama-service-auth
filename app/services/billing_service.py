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
from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.plans import (
    ARCHIVE_ADDON_GB,
    ARCHIVE_ADDON_PRICE_TRY,
    BILLING_CYCLES,
    PAID_PLANS,
    PLAN_CATALOG,
    VAT_PERCENT,
    calculate_plan_total_try,
    validate_seat_count,
)
from app.models import (
    BillingInfo,
    DiscountCode,
    DiscountCodeUse,
    Organization,
    Payment,
    Subscription,
    User,
)
from app.schemas.billing import BillingInfoPayload

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing math (saf — DB'ye dokunmaz, schema validate de eder)
# ---------------------------------------------------------------------------


def _compute_breakdown(
    *,
    plan: str,
    seat_count: int,
    addon_archive_gb: bool,
    discount_percent: Optional[int],
) -> dict:
    """Returns kuruş cinsinden fiyat kırılımı.

    Tüm tutarlar kuruş (TRY * 100). discount_percent None ise indirim yok.
    """
    plan_total_try = calculate_plan_total_try(plan, seat_count)
    addon_total_try = ARCHIVE_ADDON_PRICE_TRY if addon_archive_gb else 0
    subtotal_try = plan_total_try + addon_total_try

    if discount_percent and discount_percent > 0:
        discount_try = (subtotal_try * discount_percent) // 100
    else:
        discount_try = 0

    net_try = subtotal_try - discount_try
    vat_try = (net_try * VAT_PERCENT) // 100
    total_try = net_try + vat_try

    return {
        "subtotal_kurus": subtotal_try * 100,
        "discount_amount_kurus": discount_try * 100,
        "net_after_discount_kurus": net_try * 100,
        "vat_kurus": vat_try * 100,
        "total_kurus": total_try * 100,
    }


# ---------------------------------------------------------------------------
# Discount code helpers
# ---------------------------------------------------------------------------


def _normalize_code(code: str) -> str:
    return code.strip().upper()


async def _load_discount(db: AsyncSession, *, code: str) -> Optional[DiscountCode]:
    """Active+valid+within-max-uses ise kodu döner, değilse None.

    User-already-used kontrolü ayrı; bu fonksiyon sadece global durumu bakar.
    """
    stmt = select(DiscountCode).where(DiscountCode.code == _normalize_code(code))
    code_row = (await db.execute(stmt)).scalar_one_or_none()
    if code_row is None or not code_row.is_active:
        return None
    if code_row.valid_until is not None and code_row.valid_until < datetime.utcnow():
        return None
    if code_row.max_uses is not None and code_row.times_used >= code_row.max_uses:
        return None
    return code_row


async def _user_already_used(db: AsyncSession, *, code_id: UUID, user_id: UUID) -> bool:
    stmt = (
        select(DiscountCodeUse)
        .where(DiscountCodeUse.discount_code_id == code_id)
        .where(DiscountCodeUse.user_id == user_id)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def validate_discount_for_user(
    db: AsyncSession,
    *,
    code: str,
    user: User,
    plan: str,
    seat_count: int,
    addon_archive_gb: bool,
) -> Tuple[DiscountCode, dict]:
    """Returns (discount_code_row, breakdown).

    HTTPException atar (404 kod yok, 409 zaten kullanılmış, 410 dolmuş);
    çağıran ya try/except ile karşılar ya da hatayı doğrudan response'a yansıtır.
    """
    code_row = await _load_discount(db, code=code)
    if code_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "İndirim kodu geçerli değil")
    if await _user_already_used(db, code_id=code_row.id, user_id=user.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu indirim kodunu daha önce kullandınız")

    breakdown = _compute_breakdown(
        plan=plan,
        seat_count=seat_count,
        addon_archive_gb=addon_archive_gb,
        discount_percent=code_row.percent_off,
    )
    return code_row, breakdown


# ---------------------------------------------------------------------------
# Billing info upsert
# ---------------------------------------------------------------------------


async def _upsert_billing_info(
    db: AsyncSession,
    *,
    organization_id: UUID,
    payload: BillingInfoPayload,
) -> BillingInfo:
    """Org başına bir kayıt — yoksa oluştur, varsa güncelle."""
    existing = (await db.execute(
        select(BillingInfo).where(BillingInfo.organization_id == organization_id)
    )).scalar_one_or_none()

    fields = payload.model_dump()
    if existing is None:
        info = BillingInfo(organization_id=organization_id, **fields)
        db.add(info)
        await db.flush()
        return info

    for k, v in fields.items():
        setattr(existing, k, v)
    await db.flush()
    return existing


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
    addon_archive_gb: bool = False,
    discount_code: Optional[str] = None,
    billing_info: Optional[BillingInfoPayload] = None,
) -> Payment:
    """Validate inputs, compute the price, optionally upsert billing info, and
    persist a pending Payment row.
    """
    if plan not in PLAN_CATALOG:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown plan: {plan}")
    if PLAN_CATALOG[plan]["contact_sales_only"]:
        # Enterprise satışları satış ekibi yürütür; self-service akış kapalı.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{PLAN_CATALOG[plan]['name']} paketi satış ekibi tarafından satılır; lütfen iletişime geçin.",
        )
    if billing_cycle not in BILLING_CYCLES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown billing cycle: {billing_cycle}")
    if not validate_seat_count(plan, seat_count):
        definition = PLAN_CATALOG[plan]
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"seat_count must be between {definition['min_users']} and {definition['max_users']} for {plan}",
        )

    # Discount code — varsa validate et, snapshot bilgilerini hazırla.
    discount_row: Optional[DiscountCode] = None
    discount_percent: Optional[int] = None
    if discount_code:
        discount_row, _preview = await validate_discount_for_user(
            db,
            code=discount_code,
            user=user,
            plan=plan,
            seat_count=seat_count,
            addon_archive_gb=addon_archive_gb,
        )
        discount_percent = discount_row.percent_off

    breakdown = _compute_breakdown(
        plan=plan,
        seat_count=seat_count,
        addon_archive_gb=addon_archive_gb,
        discount_percent=discount_percent,
    )
    amount_kurus = breakdown["total_kurus"]

    # Test override — Solo plan için 1 TL gibi tutarla canlı PayTR akışını doğrularken
    # tutar yine de TRY/VAT snapshot'ında orijinal değerleriyle saklanır.
    if (
        settings.BILLING_TEST_OVERRIDE_AMOUNT_KURUS > 0
        and settings.BILLING_TEST_OVERRIDE_PLAN == plan
    ):
        logger.warning(
            "BILLING TEST OVERRIDE active: plan=%s seats=%s original=%s kuruş → %s kuruş",
            plan, seat_count, amount_kurus, settings.BILLING_TEST_OVERRIDE_AMOUNT_KURUS,
        )
        amount_kurus = settings.BILLING_TEST_OVERRIDE_AMOUNT_KURUS

    logger.info(
        "Order: plan=%s seats=%s subtotal=%s discount=%s vat=%s total=%s addon=%s code=%s",
        plan, seat_count,
        breakdown["subtotal_kurus"], breakdown["discount_amount_kurus"],
        breakdown["vat_kurus"], amount_kurus,
        addon_archive_gb, (discount_row.code if discount_row else None),
    )

    # Billing info upsert (varsa). Org'a kaydederiz, snapshot'ını da Payment'a yazarız.
    billing_snapshot = None
    if billing_info is not None and user.organization_id is not None:
        info_row = await _upsert_billing_info(
            db, organization_id=user.organization_id, payload=billing_info
        )
        billing_snapshot = info_row.to_snapshot()

    definition = PLAN_CATALOG[plan]
    payment = Payment(
        user_id=user.id,
        organization_id=user.organization_id,
        merchant_oid=_generate_merchant_oid(user.id),
        plan=plan,
        billing_cycle=billing_cycle,
        seat_count=seat_count,
        storage_gb_per_user=Decimal(str(definition["storage_gb_per_user"])),
        addon_archive_gb=(ARCHIVE_ADDON_GB if addon_archive_gb else 0),
        discount_code=(discount_row.code if discount_row else None),
        discount_percent=discount_percent,
        discount_amount_kurus=breakdown["discount_amount_kurus"],
        vat_kurus=breakdown["vat_kurus"],
        amount_kurus=amount_kurus,
        currency="TRY",
        billing_info_snapshot=billing_snapshot,
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

        hash = base64( HMAC_SHA256( merchant_oid + salt + status + total_amount, merchant_key ) )

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


async def _record_discount_use(
    db: AsyncSession,
    *,
    payment: Payment,
) -> None:
    """Activation sırasında: payment'a snapshot'lı kod varsa DB'de kullanım kaydı oluştur.

    Race condition: aynı user aynı kodla iki order açıp ikisini de başarıyla
    callback'lerse, unique constraint ikinciyi reddeder ve `times_used` ikinci
    kez artırılmaz. Bu durumda da Payment.success kalır (kullanıcı ödeme yaptı);
    sadece counter doğru olmaz — kabul edilebilir trade-off.
    """
    if not payment.discount_code:
        return
    code_row = (await db.execute(
        select(DiscountCode).where(DiscountCode.code == payment.discount_code)
    )).scalar_one_or_none()
    if code_row is None:
        return

    # Per-user idempotency: zaten kullandıysa skip (PayTR retry).
    existing_use = (await db.execute(
        select(DiscountCodeUse)
        .where(DiscountCodeUse.discount_code_id == code_row.id)
        .where(DiscountCodeUse.user_id == payment.user_id)
    )).scalar_one_or_none()
    if existing_use is not None:
        return

    db.add(DiscountCodeUse(
        discount_code_id=code_row.id,
        user_id=payment.user_id,
        payment_id=payment.id,
    ))
    code_row.times_used = (code_row.times_used or 0) + 1


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
    """Apply a PayTR callback to the matching Payment row, idempotently."""
    if not verify_paytr_callback_hash(merchant_oid, status_value, total_amount, received_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "PayTR hash verification failed")

    stmt = select(Payment).where(Payment.merchant_oid == merchant_oid)
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Order not found: {merchant_oid}")

    # Idempotency: already terminal → return as-is
    if payment.status in ("success", "failed"):
        return payment

    # Money check: PayTR callback'inde iki ayri alan var —
    #   * total_amount   = musterinin kartindan cekilen tutar (taksit vade
    #                       farki PayTR + banka tarafindan eklenir)
    #   * payment_amount = bizim get-token ile gonderdigimiz ve satici olarak
    #                       alacagimiz tutar — yani siparis tutari
    # Stored `payment.amount_kurus` get-token'a gonderilen ayni tutardir, o
    # yuzden karsilastirma payment_amount ile yapilmali. Eski sekilde
    # total_amount kullanmak taksit vade farki olan her odemede mismatch
    # uretiyordu (denizgunaycalik@gmail.com 2026-06-05 incident).
    # Eski callback'ler (FE eski surum, payment_amount yoksa) icin geriye
    # donuk total_amount fallback'i kaliyor.
    pa_raw = (paytr_response or {}).get("payment_amount") if paytr_response else None
    try:
        callback_amount = int(pa_raw) if pa_raw is not None else int(total_amount)
    except (TypeError, ValueError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payment_amount")
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
        addon_archive_gb=payment.addon_archive_gb or 0,
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

    # Whitelabel slug: Elite/Enterprise'a geçişte slug mint et.
    from app.services.whitelabel import ensure_whitelabel_slug
    await ensure_whitelabel_slug(db, org=org)

    # Indirim kullanım kaydı + sayaç
    await _record_discount_use(db, payment=payment)

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
