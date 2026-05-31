"""
Muvekkil (Portal) model.

A muvekkil is the Portal — a container the host organization opens for a
single client. Belongs to exactly one organization (N→1, the isolation
foundation). Carries TCKN for individuals and VKN for corporate clients;
both are unique inside the org via partial unique indexes.
"""
import enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class MuvekkilUnvan(str, enum.Enum):
    """Muvekkil title: person or company."""
    KISI = "kisi"
    SIRKET = "sirket"


class Muvekkil(Base, UUIDMixin, TimestampMixin):
    """
    Muvekkil (Portal) — single-tenant container for one client.

    Attributes:
        id: Unique client identifier (UUID)
        organization_id: Owning organization (mandatory; isolation key)
        unvan: KISI (individual) or SIRKET (corporate)
        tckn: T.C. Kimlik Numarası — only for KISI clients (11 chars)
        vkn: Vergi Kimlik Numarası — only for SIRKET clients (10 chars)
        first_name: Client's first name (individual) or contact (corporate)
        last_name: Client's last name (individual) or contact (corporate)
        email/phone/address/city/country/notes/muvekkil_aciklama: contact info
        is_archived: Soft-archive flag (hides from default lists)
        archived_at: Timestamp of archival, NULL when active
        organization: Owning org (relationship)
        portal_members: Users (org-side + guest) attached to this portal
        iliskili_muvekkiller: Related clients (sub-entities)
    """

    __tablename__ = "muvekkiller"

    organization_id = Column(
        UUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

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

    # Real-world identity numbers. Validated at the API boundary; uniqueness
    # is enforced per organization via partial unique indexes
    # (uq_muvekkiller_org_tckn, uq_muvekkiller_org_vkn).
    tckn = Column(String(11), nullable=True)
    vkn = Column(String(10), nullable=True)

    # Basic information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True)

    # Address information
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)
    muvekkil_aciklama = Column(Text, nullable=True)

    # Archival (soft delete)
    is_archived = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    archived_at = Column(DateTime, nullable=True)

    # Relationships
    organization = relationship(
        "Organization", back_populates="muvekkiller", lazy="selectin"
    )

    portal_members = relationship(
        "PortalMember",
        back_populates="muvekkil",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
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
