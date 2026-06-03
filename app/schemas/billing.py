"""
Pydantic schemas for billing endpoints.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Plan catalog
# ---------------------------------------------------------------------------


class PlanItem(BaseModel):
    id: str                          # "solo" | "team" | "elite" | "enterprise"
    name: str                        # display name
    min_users: int
    max_users: Optional[int]
    price_usd_per_user_monthly: int
    storage_gb_per_user: float
    contact_sales_only: bool


class PlanCatalogResponse(BaseModel):
    plans: List[PlanItem]
    exchange_rate_usd_try: float     # the rate offers are quoted with right now


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------


class CreateOrderRequest(BaseModel):
    plan: str = Field(..., description="solo | team | elite")
    billing_cycle: str = Field(..., description="yearly | sixmonth")
    seat_count: int = Field(..., ge=1)


class CreateOrderResponse(BaseModel):
    merchant_oid: str
    amount_kurus: int
    amount_usd: Decimal
    exchange_rate: Decimal
    plan: str
    billing_cycle: str
    seat_count: int
    user_email: str
    user_name: str

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Activation (PayTR callback proxy)
# ---------------------------------------------------------------------------


class ActivateRequest(BaseModel):
    merchant_oid: str
    hash: str
    status: str = Field(..., description="success | failed")
    total_amount: str = Field(..., description="kuruş, as PayTR sends it")
    failed_reason: Optional[str] = None
    paytr_response: Optional[dict] = None


class ActivateResponse(BaseModel):
    merchant_oid: str
    status: str


# ---------------------------------------------------------------------------
# Public order-status polling (no auth)
# ---------------------------------------------------------------------------


class PublicOrderStatusResponse(BaseModel):
    """Minimal payload returned from the public polling endpoint.

    Intentionally narrow — only the fields the frontend bridge needs to
    decide whether to redirect to /odeme/basarili. No user id, no amount,
    no PayTR response, so the unauthenticated endpoint stays low-risk.
    """
    merchant_oid: str
    status: str  # pending | success | failed | cancelled


# ---------------------------------------------------------------------------
# Subscription / payment listing
# ---------------------------------------------------------------------------


class SubscriptionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    plan: str
    billing_cycle: str
    seat_count: int
    storage_gb_per_user: Decimal
    started_at: datetime
    expires_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)


class PaymentResponse(BaseModel):
    id: UUID
    merchant_oid: str
    plan: str
    billing_cycle: str
    seat_count: int
    amount_kurus: int
    amount_usd: Decimal
    exchange_rate: Decimal
    currency: str
    status: str
    failed_reason: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
