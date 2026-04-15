"""
CRUD operations for Muvekkil (Client).
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models.muvekkil import Muvekkil
from app.models.organization import Organization
from app.schemas.muvekkil import MuvekkillCreate, MuvekkillUpdate


class CRUDMuvekkil(CRUDBase[Muvekkil, MuvekkillCreate, MuvekkillUpdate]):
    """CRUD operations for Muvekkil."""

    async def get_by_email(
        self,
        db: AsyncSession,
        *,
        email: str
    ) -> Optional[Muvekkil]:
        """Get muvekkil by email."""
        result = await db.execute(
            select(Muvekkil).where(Muvekkil.email == email)
        )
        return result.scalar_one_or_none()

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

    async def get_with_relations(
        self,
        db: AsyncSession,
        *,
        id: UUID
    ) -> Optional[Muvekkil]:
        """Get muvekkil with related muvekkiller and organizations loaded."""
        result = await db.execute(
            select(Muvekkil)
            .options(
                selectinload(Muvekkil.iliskili_muvekkiller),
                selectinload(Muvekkil.organizations),
            )
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

    async def add_iliskili(
        self,
        db: AsyncSession,
        *,
        muvekkil: Muvekkil,
        iliskili: Muvekkil
    ) -> Muvekkil:
        """Add a directed relation muvekkil -> iliskili."""
        if muvekkil.id == iliskili.id:
            raise ValueError("Bir müvekkil kendisiyle ilişkilendirilemez")
        if iliskili not in muvekkil.iliskili_muvekkiller:
            muvekkil.iliskili_muvekkiller.append(iliskili)
            db.add(muvekkil)
            await db.commit()
            await db.refresh(muvekkil)
        return muvekkil

    async def remove_iliskili(
        self,
        db: AsyncSession,
        *,
        muvekkil: Muvekkil,
        iliskili: Muvekkil
    ) -> Muvekkil:
        """Remove a directed relation muvekkil -> iliskili."""
        if iliskili in muvekkil.iliskili_muvekkiller:
            muvekkil.iliskili_muvekkiller.remove(iliskili)
            db.add(muvekkil)
            await db.commit()
            await db.refresh(muvekkil)
        return muvekkil


muvekkil_crud = CRUDMuvekkil(Muvekkil)
