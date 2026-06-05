"""
Billing API: plan catalog, order creation, PayTR activation, account status.
"""
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.config import settings
from app.core.database import get_db
from app.core.plans import (
    ARCHIVE_ADDON_GB,
    ARCHIVE_ADDON_PRICE_TRY,
    PLAN_CATALOG,
    VAT_PERCENT,
)
from app.models import Payment, User
from app.schemas.billing import (
    ActivateRequest,
    ActivateResponse,
    AddonItem,
    CreateOrderRequest,
    CreateOrderResponse,
    PaymentResponse,
    PlanCatalogResponse,
    PlanItem,
    PublicOrderStatusResponse,
    SubscriptionResponse,
    ValidateDiscountRequest,
    ValidateDiscountResponse,
)
from app.services import billing_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Public: plan catalog
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=PlanCatalogResponse, summary="Plan catalog")
async def list_plans() -> PlanCatalogResponse:
    """Frontend reads this when rendering the pricing page.

    Yıllık TRY fiyatları (KDV hariç) doner. Frontend KDV hesabını da yine
    backend'in verdiği `vat_percent` ile yapar; total backend'de hesaplanır
    (ödeme sırasında /billing/orders).
    """
    items: List[PlanItem] = []
    for plan_id, definition in PLAN_CATALOG.items():
        items.append(
            PlanItem(
                id=plan_id,
                name=definition["name"],
                min_users=definition["min_users"],
                max_users=definition["max_users"],
                price_try_per_user_yearly=definition["price_try_per_user_yearly"],
                storage_gb_per_user=definition["storage_gb_per_user"],
                contact_sales_only=definition["contact_sales_only"],
            )
        )
    addons = [
        AddonItem(
            id="archive_100gb",
            name=f"{ARCHIVE_ADDON_GB} GB Arşiv Paketi",
            gb=ARCHIVE_ADDON_GB,
            price_try_yearly=ARCHIVE_ADDON_PRICE_TRY,
        ),
    ]
    return PlanCatalogResponse(plans=items, addons=addons, vat_percent=VAT_PERCENT)


# ---------------------------------------------------------------------------
# Public: discount code validation (preview)
# ---------------------------------------------------------------------------


@router.post(
    "/discount-codes/validate",
    response_model=ValidateDiscountResponse,
    summary="Indirim kodu validate + onizleme",
)
async def validate_discount(
    request: ValidateDiscountRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ValidateDiscountResponse:
    """Önizleme — kod geçerli mi + uygulanırsa hangi tutarlar çıkıyor.

    `/billing/orders` çağrısında kodu tekrar göndermek gerekir; bu endpoint
    sadece kullanıcıya gerçek hesap önizlemesi sunar. Hata durumları:
      404 — kod yok veya geçersiz (expired/disabled/limit dolu)
      409 — kullanıcı bu kodu zaten kullanmış
    """
    code_row, breakdown = await billing_service.validate_discount_for_user(
        db,
        code=request.code,
        user=user,
        plan=request.plan,
        seat_count=request.seat_count,
        addon_archive_gb=request.addon_archive_gb,
    )
    return ValidateDiscountResponse(
        code=code_row.code,
        percent_off=code_row.percent_off,
        subtotal_kurus=breakdown["subtotal_kurus"],
        discount_amount_kurus=breakdown["discount_amount_kurus"],
        net_after_discount_kurus=breakdown["net_after_discount_kurus"],
        vat_kurus=breakdown["vat_kurus"],
        total_kurus=breakdown["total_kurus"],
    )


# ---------------------------------------------------------------------------
# Authenticated: create order
# ---------------------------------------------------------------------------


@router.post(
    "/orders",
    response_model=CreateOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a pending PayTR order",
)
async def create_order(
    request: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> CreateOrderResponse:
    """Returns the merchant_oid and TRY amount the frontend should send to PayTR."""
    payment = await billing_service.create_order(
        db,
        user=user,
        plan=request.plan,
        billing_cycle=request.billing_cycle,
        seat_count=request.seat_count,
        addon_archive_gb=request.addon_archive_gb,
        discount_code=request.discount_code,
        billing_info=request.billing_info,
    )
    full_name = " ".join(filter(None, [user.first_name, user.last_name])) or user.email
    # subtotal = amount + discount - vat  (her sey kuruş)  → tutarsızlık önlemek için Payment alanlarından çıkar.
    subtotal_kurus = (
        payment.amount_kurus
        - (payment.vat_kurus or 0)
        + (payment.discount_amount_kurus or 0)
    )
    return CreateOrderResponse(
        merchant_oid=payment.merchant_oid,
        amount_kurus=payment.amount_kurus,
        plan=payment.plan,
        billing_cycle=payment.billing_cycle,
        seat_count=payment.seat_count,
        user_email=user.email,
        user_name=full_name,
        subtotal_kurus=subtotal_kurus,
        discount_amount_kurus=payment.discount_amount_kurus or 0,
        discount_percent=payment.discount_percent,
        vat_kurus=payment.vat_kurus or 0,
        addon_archive_gb=payment.addon_archive_gb or 0,
    )


# ---------------------------------------------------------------------------
# Internal: PayTR callback bridge
# ---------------------------------------------------------------------------


def _require_internal_token(x_internal_token: str | None) -> None:
    """Reject unless the shared secret matches."""
    expected = settings.INTERNAL_API_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="INTERNAL_API_TOKEN is not configured",
        )
    if not x_internal_token or x_internal_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token",
        )


@router.post(
    "/activate",
    response_model=ActivateResponse,
    summary="Activate / finalize a subscription from PayTR callback",
)
async def activate(
    request: ActivateRequest,
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
    db: AsyncSession = Depends(get_db),
) -> ActivateResponse:
    _require_internal_token(x_internal_token)

    payment = await billing_service.activate_subscription(
        db,
        merchant_oid=request.merchant_oid,
        received_hash=request.hash,
        status_value=request.status,
        total_amount=request.total_amount,
        paytr_response=request.paytr_response,
        failed_reason=request.failed_reason,
    )
    return ActivateResponse(merchant_oid=payment.merchant_oid, status=payment.status)


# ---------------------------------------------------------------------------
# Public: order status polling (no auth) — onedocs.com bridge polling icin
# ---------------------------------------------------------------------------


@router.get(
    "/orders/{merchant_oid}/status",
    response_model=PublicOrderStatusResponse,
    summary="Public order status (no auth) — onedocs.com bridge polling icin",
)
async def public_order_status(
    merchant_oid: str,
    db: AsyncSession = Depends(get_db),
) -> PublicOrderStatusResponse:
    stmt = select(Payment).where(Payment.merchant_oid == merchant_oid)
    payment = (await db.execute(stmt)).scalar_one_or_none()
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return PublicOrderStatusResponse(merchant_oid=payment.merchant_oid, status=payment.status)


# ---------------------------------------------------------------------------
# Authenticated: read endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=SubscriptionResponse | None,
    summary="Get active subscription for the caller's organization",
)
async def my_subscription(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> SubscriptionResponse | None:
    sub = await billing_service.get_active_subscription_for_user(db, user)
    if sub is None:
        return None
    return SubscriptionResponse.model_validate(sub)


@router.get(
    "/orders",
    response_model=List[PaymentResponse],
    summary="List the caller's order history",
)
async def my_orders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> List[PaymentResponse]:
    stmt = (
        select(Payment)
        .where(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
    )
    result = await db.execute(stmt)
    return [PaymentResponse.model_validate(p) for p in result.scalars().all()]
