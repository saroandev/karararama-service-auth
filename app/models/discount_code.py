"""
İndirim kodları (kampanya / promosyon kodları).

`max_uses` global limit; ek olarak `DiscountCodeUse` tablosu sayesinde
"her kullanıcı bu kodu yalnızca 1 kez kullanabilir" kuralı uygulanır.
"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUID, UUIDMixin


class DiscountCode(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "discount_codes"

    # Müşteri girer; case-insensitive saklamak için DB'de upper-case zorluyoruz.
    code = Column(String(40), unique=True, nullable=False, index=True)

    # 1-100 arası tam yüzde (0.5 gibi ondalık desteklemiyoruz; ileride lazım
    # olursa Numeric'e geçilebilir).
    percent_off = Column(Integer, nullable=False)

    is_active = Column(Boolean, nullable=False, default=True, index=True)
    valid_until = Column(DateTime, nullable=True)        # None = süresiz
    max_uses = Column(Integer, nullable=True)            # None = global limit yok
    times_used = Column(Integer, nullable=False, default=0)

    uses = relationship("DiscountCodeUse", back_populates="discount_code", cascade="all, delete-orphan", lazy="select")

    def __repr__(self) -> str:
        return f"<DiscountCode(code={self.code}, percent_off={self.percent_off})>"


class DiscountCodeUse(Base, UUIDMixin, TimestampMixin):
    """Her kullanıcı bir kodu yalnızca 1 kez kullanabilir — bu unique pair
    kuralı sağlar. Aynı zamanda hangi user'ın hangi kodu hangi payment'la
    kullandığının audit trail'i.
    """
    __tablename__ = "discount_code_uses"

    discount_code_id = Column(UUID(), ForeignKey("discount_codes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_id = Column(UUID(), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True)

    discount_code = relationship("DiscountCode", back_populates="uses", foreign_keys=[discount_code_id], lazy="select")
    user = relationship("User", foreign_keys=[user_id], lazy="select")
    payment = relationship("Payment", foreign_keys=[payment_id], lazy="select")

    __table_args__ = (
        # Aynı user aynı kodu birden çok kez kullanamaz.
        UniqueConstraint("discount_code_id", "user_id", name="uq_discount_code_user"),
    )

    def __repr__(self) -> str:
        return f"<DiscountCodeUse(code_id={self.discount_code_id}, user_id={self.user_id})>"
