"""
IliskiliMuvekkil (Related Client) model.
"""
from sqlalchemy import Column, String, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID
from app.models.muvekkil import MuvekkilUnvan


class IliskiliMuvekkil(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "iliskili_muvekkiller"

    unvan = Column(
        SQLEnum(
            MuvekkilUnvan,
            values_callable=lambda x: [e.value for e in x],
            native_enum=False,
        ),
        nullable=False,
        default=MuvekkilUnvan.KISI,
        server_default=MuvekkilUnvan.KISI.value,
    )

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True)

    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)

    notes = Column(Text, nullable=True)
    muvekkil_aciklama = Column(Text, nullable=True)

    organization_id = Column(
        UUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    muvekkil_id = Column(
        UUID(), ForeignKey("muvekkiller.id", ondelete="CASCADE"), nullable=True, index=True,
    )

    organization = relationship("Organization", lazy="selectin")
    muvekkil = relationship(
        "Muvekkil", back_populates="iliskili_muvekkiller", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<IliskiliMuvekkil(id={self.id}, name={self.first_name} {self.last_name})>"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"
