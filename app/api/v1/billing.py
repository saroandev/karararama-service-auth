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
from app.core.plans import PLAN_CATALOG
from app.models import Payment, User
from app.schemas.billing import (
    ActivateRequest,
    ActivateResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    PaymentResponse,
    PlanCatalogResponse,
    PlanItem,
    PublicOrderStatusResponse,
    SubscriptionResponse,
)
from app.services import billing_service
from app.services.exchange_rate import get_usd_try_rate

router = APIRouter()


# ---------------------------------------------------------------------------
# Public: plan catalog
# ---------------------------------------------------------------------------


@router.get("/plans", response_model=PlanCatalogResponse, summary="Plan catalog")
async def list_plans() -> PlanCatalogResponse:
    """Frontend reads this when rendering the pricing page.

    The exchange rate is fetched live from TCMB (cached 15 min); see
    `app/services/exchange_rate.py` for fallback chain.
    """
    items: List[PlanItem] = []
    for plan_id, definition in PLAN_CATALOG.items():
        items.append(
            PlanItem(
                id=plan_id,
                name=definition["name"],
                min_users=definition["min_users"],
                max_users=definition["max_users"],
                price_usd_per_user_monthly=definition["price_usd_per_user_monthly"],
                storage_gb_per_user=definition["storage_gb_per_user"],
                contact_sales_only=definition["contact_sales_only"],
            )
        )
    rate, _source = get_usd_try_rate()
    return PlanCatalogResponse(plans=items, exchange_rate_usd_try=rate)


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
    )
    full_name = " ".join(filter(None, [user.first_name, user.last_name])) or user.email
    return CreateOrderResponse(
        merchant_oid=payment.merchant_oid,
        amount_kurus=payment.amount_kurus,
        amount_usd=payment.amount_usd,
        exchange_rate=payment.exchange_rate,
        plan=payment.plan,
        billing_cycle=payment.billing_cycle,
        seat_count=payment.seat_count,
        user_email=user.email,
        user_name=full_name,
    )


# ---------------------------------------------------------------------------
# Internal: PayTR callback bridge
# ---------------------------------------------------------------------------


def _require_internal_token(x_internal_token: str | None) -> None:
    """Reject unless the shared secret matches.

    We treat a missing-or-empty configured token as misconfiguration and fail
    closed, so a forgotten env var never accidentally turns off auth.
    """
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
    """Called by the frontend's PayTR callback proxy with the verified status.

    PayTR's hash is re-verified here against PAYTR_MERCHANT_KEY/SALT, so even
    if the frontend secret leaks the activation path is still authenticated.
    The X-Internal-Token header is an additional gate so random callers from
    the public internet cannot reach this endpoint directly.
    """
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
# Public: order status polling (no auth)
# ---------------------------------------------------------------------------
#
# Tarayıcı www.onedocs.com/odeme bridge sayfası buraya periyodik fetch atar
# (kullanıcının PayTR iframe'i otomatik yönlendirmediği durumlarda). Sadece
# merchant_oid'in durumunu döndürür; user_id / tutar / PayTR yanıtı gibi
# hassas alanlar response'a dahil değildir. merchant_oid'ler yeterince uzun
# ve rastgele olduğu için (ts + user_id_short + 8 hex) bilinmeyen bir
# merchant_oid'i tahmin etmek pratik olarak mümkün değil.


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
