"""
Billing info — organizasyonun e-fatura/proforma bilgileri.

Her organizasyonun 0 veya 1 kayıtlı BillingInfo'su olabilir (org_id unique).
Yeni bir Payment oluşurken bilginin **anlık snapshot'ı** Payment'a
JSONB olarak da yazılır; bu yüzden BillingInfo sonradan güncellense bile
geçmiş ödemelerin fatura bilgisi değişmez (audit / e-arşiv için kritik).
"""
from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUID, UUIDMixin


class BillingInfo(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "billing_infos"

    organization_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # "bireysel" | "kurumsal"
    kind = Column(String(20), nullable=False)

    # Bireysel alanlar
    ad_soyad = Column(String(255), nullable=True)
    tckn = Column(String(11), nullable=True)

    # Kurumsal alanlar
    firma = Column(String(255), nullable=True)
    vergi_no = Column(String(20), nullable=True)
    vergi_dairesi = Column(String(120), nullable=True)

    # Ortak
    email = Column(String(255), nullable=False)
    telefon = Column(String(30), nullable=False)
    adres = Column(Text, nullable=False)

    organization = relationship("Organization", foreign_keys=[organization_id], lazy="select")

    def to_snapshot(self) -> dict:
        """Payment.billing_info_snapshot için kopyalanabilir dict."""
        return {
            "kind": self.kind,
            "ad_soyad": self.ad_soyad,
            "tckn": self.tckn,
            "firma": self.firma,
            "vergi_no": self.vergi_no,
            "vergi_dairesi": self.vergi_dairesi,
            "email": self.email,
            "telefon": self.telefon,
            "adres": self.adres,
        }

    def __repr__(self) -> str:
        return f"<BillingInfo(org={self.organization_id}, kind={self.kind})>"
