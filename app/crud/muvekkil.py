"""
CRUD operations for Muvekkil (Client).
"""
from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.muvekkil import Muvekkil
from app.models.organization import Organization
from app.schemas.muvekkil import MuvekkillCreate, MuvekkillUpdate


class CRUDMuvekkil(CRUDBase[Muvekkil, MuvekkillCreate, MuvekkillUpdate]):
    """CRUD operations for Muvekkil."""

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: MuvekkillCreate,
        organization: Optional[Organization] = None,
    ) -> Muvekkil:
        """Create muvekkil and optionally attach an organization in one transaction."""
        data = obj_in.model_dump(exclude={"organization_id"})
        db_obj = Muvekkil(**data)
        if organization is not None:
            db_obj.organizations.append(organization)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def email_exists_in_organizations(
        self,
        db: AsyncSession,
        *,
        email: str,
        organization_ids: Sequence[UUID],
        exclude_muvekkil_id: Optional[UUID] = None,
    ) -> bool:
        """
        Check whether any muvekkil in the given organizations already uses this email.

        Email uniqueness is scoped per organization: the same email can belong to
        different muvekkiller as long as they are not in the same organization.
        """
        if not organization_ids:
            return False
        query = (
            select(Muvekkil.id)
            .join(Muvekkil.organizations)
            .where(
                Muvekkil.email == email,
                Organization.id.in_(list(organization_ids)),
            )
        )
        if exclude_muvekkil_id is not None:
            query = query.where(Muvekkil.id != exclude_muvekkil_id)
        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def name_exists_in_organizations(
        self,
        db: AsyncSession,
        *,
        first_name: str,
        last_name: str,
        organization_ids: Sequence[UUID],
        exclude_muvekkil_id: Optional[UUID] = None,
    ) -> bool:
        """
        Check whether a muvekkil with the same full name already exists in any
        of the given organizations.

        Matching is done on the normalized full name (first_name + last_name
        combined, case-insensitive, whitespace-collapsed) so the same person
        entered with a different first/last split is still detected as a
        duplicate. For example, all of these collide with an existing
        ("Ahmet", "Yılmaz") record in the same organization:
          - ("Ahmet Yılmaz", "")
          - ("", "Ahmet Yılmaz")
          - ("ahmet", "yılmaz")

        Case-folding is delegated to the database `lower()` on BOTH sides.
        Doing it with Python `str.lower()` on the input would break Turkish
        names: e.g. Python folds "İ" to "i̇" (i + combining dot) while the DB
        does not, so the two sides would never match for names containing
        "İ" (KURUYEMİŞ, TURİZM, ŞİRKETİ, ...).
        """
        if not organization_ids:
            return False

        # Collapse whitespace only; let the DB handle case-folding (see above).
        normalized = " ".join(f"{first_name} {last_name}".split())
        if not normalized:
            return False

        stored_full_name = func.lower(
            func.trim(Muvekkil.first_name + " " + Muvekkil.last_name)
        )
        query = (
            select(Muvekkil.id)
            .join(Muvekkil.organizations)
            .where(
                stored_full_name == func.lower(normalized),
                Organization.id.in_(list(organization_ids)),
            )
        )
        if exclude_muvekkil_id is not None:
            query = query.where(Muvekkil.id != exclude_muvekkil_id)
        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def get_with_organizations(
        self,
        db: AsyncSession,
        *,
        id: UUID
    ) -> Optional[Muvekkil]:
        """Get muvekkil with organizations loaded."""
        result = await db.execute(
            select(Muvekkil)
            .options(selectinload(Muvekkil.organizations))
            .where(Muvekkil.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_organization(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[Muvekkil]:
        """Get all muvekkiller for a specific organization."""
        result = await db.execute(
            select(Muvekkil)
            .join(Muvekkil.organizations)
            .where(Organization.id == organization_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_all(self, db: AsyncSession) -> int:
        result = await db.execute(select(func.count(Muvekkil.id)))
        return result.scalar_one()

    async def count_by_organization(self, db: AsyncSession, *, organization_id: UUID) -> int:
        result = await db.execute(
            select(func.count(Muvekkil.id))
            .join(Muvekkil.organizations)
            .where(Organization.id == organization_id)
        )
        return result.scalar_one()

    async def add_organization(
        self,
        db: AsyncSession,
        *,
        muvekkil: Muvekkil,
        organization: Organization
    ) -> Muvekkil:
        """Add organization to muvekkil."""
        if organization not in muvekkil.organizations:
            muvekkil.organizations.append(organization)
            db.add(muvekkil)
            await db.commit()
            await db.refresh(muvekkil)
        return muvekkil

    async def remove_organization(
        self,
        db: AsyncSession,
        *,
        muvekkil: Muvekkil,
        organization: Organization
    ) -> Muvekkil:
        """Remove organization from muvekkil."""
        if organization in muvekkil.organizations:
            muvekkil.organizations.remove(organization)
            db.add(muvekkil)
            await db.commit()
            await db.refresh(muvekkil)
        return muvekkil

muvekkil_crud = CRUDMuvekkil(Muvekkil)
