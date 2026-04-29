"""
CRUD operations for IliskiliMuvekkil (Related Client).
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.iliskili_muvekkil import IliskiliMuvekkil
from app.models.muvekkil import MuvekkilUnvan
from app.models.organization import Organization
from app.schemas.iliskili_muvekkil import IliskiliMuvekkillCreate, IliskiliMuvekkillUpdate


class CRUDIliskiliMuvekkil(CRUDBase[IliskiliMuvekkil, IliskiliMuvekkillCreate, IliskiliMuvekkillUpdate]):

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: IliskiliMuvekkillCreate,
        organization_id: UUID,
    ) -> IliskiliMuvekkil:
        data = obj_in.model_dump(exclude={"organization_id"})
        data["organization_id"] = organization_id
        db_obj = IliskiliMuvekkil(**data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def get_unassigned_by_org(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[IliskiliMuvekkil]:
        result = await db.execute(
            select(IliskiliMuvekkil)
            .where(
                IliskiliMuvekkil.organization_id == organization_id,
                IliskiliMuvekkil.muvekkil_id.is_(None),
            )
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_muvekkil(
        self,
        db: AsyncSession,
        *,
        muvekkil_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[IliskiliMuvekkil]:
        result = await db.execute(
            select(IliskiliMuvekkil)
            .where(IliskiliMuvekkil.muvekkil_id == muvekkil_id)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def assign(
        self,
        db: AsyncSession,
        *,
        iliskili: IliskiliMuvekkil,
        muvekkil_id: UUID,
    ) -> IliskiliMuvekkil:
        iliskili.muvekkil_id = muvekkil_id
        db.add(iliskili)
        await db.commit()
        await db.refresh(iliskili)
        return iliskili

    async def unassign(
        self,
        db: AsyncSession,
        *,
        iliskili: IliskiliMuvekkil,
    ) -> IliskiliMuvekkil:
        iliskili.muvekkil_id = None
        db.add(iliskili)
        await db.commit()
        await db.refresh(iliskili)
        return iliskili

    async def name_exists_in_org(
        self,
        db: AsyncSession,
        *,
        unvan: MuvekkilUnvan,
        first_name: str,
        last_name: str,
        organization_id: UUID,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        """
        Case-insensitive duplicate check on (unvan, first_name, last_name)
        scoped to a single organization. Mirrors the unique index added by
        the j0k1l2m3n4o5 migration.
        """
        query = (
            select(IliskiliMuvekkil.id)
            .where(
                IliskiliMuvekkil.organization_id == organization_id,
                IliskiliMuvekkil.unvan == unvan,
                func.lower(IliskiliMuvekkil.first_name) == first_name.lower(),
                func.lower(IliskiliMuvekkil.last_name) == last_name.lower(),
            )
        )
        if exclude_id is not None:
            query = query.where(IliskiliMuvekkil.id != exclude_id)
        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def email_exists_in_org(
        self,
        db: AsyncSession,
        *,
        email: str,
        organization_id: UUID,
        exclude_id: Optional[UUID] = None,
    ) -> bool:
        query = (
            select(IliskiliMuvekkil.id)
            .where(
                IliskiliMuvekkil.email == email,
                IliskiliMuvekkil.organization_id == organization_id,
            )
        )
        if exclude_id is not None:
            query = query.where(IliskiliMuvekkil.id != exclude_id)
        result = await db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None


iliskili_muvekkil_crud = CRUDIliskiliMuvekkil(IliskiliMuvekkil)
