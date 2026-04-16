"""
Muvekkil (Client) model for managing clients across organizations.
"""
import enum

from sqlalchemy import Column, String, Text, Table, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class MuvekkilUnvan(str, enum.Enum):
    """Muvekkil title: person or company."""
    KISI = "kisi"
    SIRKET = "sirket"


# Association table for many-to-many relationship between muvekkiller and organizations
muvekkil_organizations = Table(
    "muvekkil_organizations",
    Base.metadata,
    Column("muvekkil_id", UUID(), ForeignKey("muvekkiller.id", ondelete="CASCADE"), primary_key=True),
    Column("organization_id", UUID(), ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
)



class Muvekkil(Base, UUIDMixin, TimestampMixin):
    """
    Muvekkil (Client) model for multi-organization client management.

    A client can belong to multiple organizations (many-to-many).

    Attributes:
        id: Unique client identifier (UUID)
        unvan: Whether the client is a person (kisi) or a company (sirket)
        first_name: Client's first name
        last_name: Client's last name
        email: Client's email address (optional)
        phone: Client's phone number (optional)
        address: Street address
        city: City
        country: Country
        notes: Additional notes about the client
        muvekkil_aciklama: Free-form description about the client
        organizations: List of organizations this client belongs to
        iliskili_muvekkiller: Related clients assigned to this muvekkil
    """

    __tablename__ = "muvekkiller"

    # Classification
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

    # Basic Information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True)

    # Address Information
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)
    muvekkil_aciklama = Column(Text, nullable=True)

    # Relationships
    organizations = relationship(
        "Organization",
        secondary=muvekkil_organizations,
        back_populates="muvekkiller",
        lazy="selectin"
    )

    iliskili_muvekkiller = relationship(
        "IliskiliMuvekkil",
        back_populates="muvekkil",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Muvekkil(id={self.id}, name={self.full_name})>"

    @property
    def full_name(self) -> str:
        """Return client's full name."""
        return f"{self.first_name} {self.last_name}"
