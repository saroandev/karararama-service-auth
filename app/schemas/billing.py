"""
Pydantic schemas for billing endpoints.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Plan catalog
# ---------------------------------------------------------------------------


class PlanItem(BaseModel):
    id: str                                  # "solo" | "team" | "elite" | "enterprise"
    name: str
    min_users: int
    max_users: Optional[int]
    # Yıllık TRY (KDV hariç) — frontend bunu gösterir, hesabı backend yapar.
    price_try_per_user_yearly: int
    storage_gb_per_user: float
    contact_sales_only: bool


class AddonItem(BaseModel):
    id: Literal["archive_100gb"]
    name: str
    gb: int
    price_try_yearly: int                    # KDV hariç


class PlanCatalogResponse(BaseModel):
    plans: List[PlanItem]
    addons: List[AddonItem]
    vat_percent: int                         # 20 — frontend KDV hesabı gösterirken kullanır


# ---------------------------------------------------------------------------
# Billing info (e-fatura için)
# ---------------------------------------------------------------------------


class BillingInfoPayload(BaseModel):
    """CreateOrderRequest içine gömülen fatura bilgisi.

    `kind` "bireysel" ise ad_soyad + tckn zorunlu;
    "kurumsal" ise firma + vergi_no + vergi_dairesi zorunlu.
    """
    kind: Literal["bireysel", "kurumsal"]
    ad_soyad: Optional[str] = None
    tckn: Optional[str] = None
    firma: Optional[str] = None
    vergi_no: Optional[str] = None
    vergi_dairesi: Optional[str] = None
    email: EmailStr
    telefon: str = Field(..., min_length=10, max_length=30)
    adres: str = Field(..., min_length=5, max_length=1000)

    @field_validator("tckn")
    @classmethod
    def _digits_only_tckn(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) != 11:
            raise ValueError("TCKN 11 hane olmalı")
        return digits


# ---------------------------------------------------------------------------
# Order creation
# ---------------------------------------------------------------------------


class CreateOrderRequest(BaseModel):
    plan: str = Field(..., description="solo | team | elite")
    billing_cycle: Literal["yearly"] = "yearly"
    seat_count: int = Field(..., ge=1)
    # Yeni alanlar — hepsi opsiyonel; sadece kullanıcı seçerse gelir.
    addon_archive_gb: bool = False
    discount_code: Optional[str] = None
    billing_info: Optional[BillingInfoPayload] = None


class CreateOrderResponse(BaseModel):
    merchant_oid: str
    amount_kurus: int                        # KDV dahil, PayTR'a gönderilecek tutar
    plan: str
    billing_cycle: str
    seat_count: int
    user_email: str
    user_name: str

    # Tüketicinin doğrulayabilmesi için kırılım:
    subtotal_kurus: int                      # paket + addon (indirim öncesi, KDV hariç)
    discount_amount_kurus: int               # 0 ise indirim uygulanmadı
    discount_percent: Optional[int]
    vat_kurus: int                           # KDV tutarı
    addon_archive_gb: int                    # 0 veya 100

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Discount code validation (public preview)
# ---------------------------------------------------------------------------


class ValidateDiscountRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=40)
    plan: str
    seat_count: int = Field(..., ge=1)
    addon_archive_gb: bool = False


class ValidateDiscountResponse(BaseModel):
    code: str
    percent_off: int
    # Önizleme: kullanıcı hangi tutarın indirimini görecek.
    subtotal_kurus: int                      # KDV hariç ara toplam
    discount_amount_kurus: int               # subtotal * percent / 100
    net_after_discount_kurus: int            # subtotal - discount
    vat_kurus: int
    total_kurus: int                         # KDV dahil son tutar


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
    addon_archive_gb: int
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
    addon_archive_gb: int
    amount_kurus: int
    discount_code: Optional[str]
    discount_percent: Optional[int]
    discount_amount_kurus: int
    vat_kurus: int
    currency: str
    status: str
    failed_reason: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
