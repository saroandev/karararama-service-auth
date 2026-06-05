"""
Payment / order model for PayTR subscription transactions.

Each row represents an attempted purchase. `merchant_oid` is the unique
ID sent to PayTR; the row starts as `pending` and transitions to `success`
or `failed` once the PayTR callback is processed.
"""
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUID, UUIDMixin


class Payment(Base, UUIDMixin, TimestampMixin):
    """Payment record for a PayTR transaction.

    `merchant_oid` is what we send to PayTR (and what they send back in the
    callback). It is unique and indexed so we can look up the order in O(1).
    """

    __tablename__ = "payments"

    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(UUID(), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)

    merchant_oid = Column(String(64), unique=True, nullable=False, index=True)

    # Plan details captured at order creation (snapshot)
    plan = Column(String(50), nullable=False)
    billing_cycle = Column(String(20), nullable=False)  # yearly
    seat_count = Column(Integer, nullable=False)
    storage_gb_per_user = Column(Numeric(6, 2), nullable=False)

    # Add-on archive (100 GB tek seçenek). seat_count'tan bağımsız sabit tutar.
    addon_archive_gb = Column(Integer, nullable=False, default=0, server_default="0")

    # İndirim snapshot — order anındaki halini saklarız, kod sonradan silinse
    # bile burada görünür.
    discount_code = Column(String(40), nullable=True)
    discount_percent = Column(Integer, nullable=True)
    discount_amount_kurus = Column(BigInteger, nullable=False, default=0, server_default="0")

    # KDV (yüzde plans.VAT_PERCENT) ayrı sütunda — fatura/muhasebe için.
    vat_kurus = Column(BigInteger, nullable=False, default=0, server_default="0")

    # Fatura bilgisi snapshot (BillingInfo.to_snapshot()). Sonradan bilgi
    # değişse bile bu satırdaki kayıt değişmez.
    billing_info_snapshot = Column(JSONB, nullable=True)

    # Money snapshot
    amount_kurus = Column(BigInteger, nullable=False)         # what PayTR was charged (TRY * 100, VAT dahil)
    # Legacy alanlar: 2026'dan önce USD üzerinden hesap yapılıyordu. Yeni
    # akışta `null` kalır; bırakıldı çünkü geçmiş ödemelerin değeri korunmalı.
    amount_usd = Column(Numeric(10, 2), nullable=True)
    exchange_rate = Column(Numeric(10, 4), nullable=True)
    currency = Column(String(8), nullable=False, default="TRY")

    # Lifecycle
    status = Column(String(20), nullable=False, default="pending", index=True)  # pending|success|failed|cancelled
    paytr_response = Column(JSONB, nullable=True)
    failed_reason = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id], lazy="select")
    organization = relationship("Organization", foreign_keys=[organization_id], lazy="select")
    subscription = relationship(
        "Subscription",
        back_populates="payment",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_payments_user_status", "user_id", "status"),
        Index("ix_payments_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Payment(merchant_oid={self.merchant_oid}, status={self.status})>"
