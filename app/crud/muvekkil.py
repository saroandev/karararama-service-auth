"""
CRUD for Muvekkil (Portal).

A muvekkil belongs to exactly one organization. Uniqueness on TCKN/VKN
is enforced inside an org by partial unique indexes; the helpers here
front-run the DB so we can return a friendly 400 instead of a 23505
violation. Email uniqueness within an org is also enforced at the API
boundary (no DB constraint — historical reason: clients can share an
email between portals at different orgs).
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models import Muvekkil
from app.schemas.muvekkil import MuvekkillCreate, MuvekkillUpdate


class CRUDMuvekkil(CRUDBase[Muvekkil, MuvekkillCreate, MuvekkillUpdate]):
    """CRUD operations for Muvekkil model."""

    async def create_for_organization(
        self,
        db: AsyncSession,
        *,
        obj_in: MuvekkillCreate,
        organization_id: UUID,
    ) -> Muvekkil:
        """Create a muvekkil pinned to `organization_id`. Schema-level
        validators have already enforced TCKN/VKN vs unvan invariants."""
        payload = obj_in.model_dump(exclude_unset=False)
        db_obj = Muvekkil(organization_id=organization_id, **payload)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get(self, db: AsyncSession, *, id: UUID) -> Optional[Muvekkil]:
        stmt = select(Muvekkil).where(Muvekkil.id == id)
        return (await db.execute(stmt)).scalar_one_or_none()

    async def get_in_organization(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        organization_id: UUID,
    ) -> Optional[Muvekkil]:
        """Fetch only if it belongs to the given org — common
        access-check pattern lifted into one query."""
        stmt = select(Muvekkil).where(
            Muvekkil.id == id, Muvekkil.organization_id == organization_id
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    def _search_predicate(self, search: str):
        like = f"%{search}%"
        digits = "".join(c for c in search if c.isdigit())
        conditions = [
            Muvekkil.first_name.ilike(like),
            Muvekkil.last_name.ilike(like),
            Muvekkil.email.ilike(like),
        ]
        if digits:
            conditions.extend([Muvekkil.tckn == digits, Muvekkil.vkn == digits])
        return or_(*conditions)

    async def list_by_organization(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        include_archived: bool = False,
    ) -> List[Muvekkil]:
        stmt = select(Muvekkil).where(Muvekkil.organization_id == organization_id)
        if not include_archived:
            stmt = stmt.where(Muvekkil.is_archived.is_(False))
        if search:
            stmt = stmt.where(self._search_predicate(search))
        stmt = stmt.order_by(Muvekkil.created_at.desc()).offset(skip).limit(limit)
        return list((await db.execute(stmt)).scalars().all())

    async def count_by_organization(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        search: Optional[str] = None,
        include_archived: bool = False,
    ) -> int:
        stmt = select(func.count(Muvekkil.id)).where(
            Muvekkil.organization_id == organization_id
        )
        if not include_archived:
            stmt = stmt.where(Muvekkil.is_archived.is_(False))
        if search:
            stmt = stmt.where(self._search_predicate(search))
        return int((await db.execute(stmt)).scalar() or 0)

    # ------------------------------------------------------------------
    # Identity uniqueness checks (front-run the DB partial indexes)
    # ------------------------------------------------------------------

    async def tckn_taken(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        tckn: str,
        exclude_muvekkil_id: Optional[UUID] = None,
    ) -> bool:
        conds = [Muvekkil.organization_id == organization_id, Muvekkil.tckn == tckn]
        if exclude_muvekkil_id is not None:
            conds.append(Muvekkil.id != exclude_muvekkil_id)
        return (await db.execute(select(Muvekkil.id).where(and_(*conds)).limit(1))).first() is not None

    async def vkn_taken(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        vkn: str,
        exclude_muvekkil_id: Optional[UUID] = None,
    ) -> bool:
        conds = [Muvekkil.organization_id == organization_id, Muvekkil.vkn == vkn]
        if exclude_muvekkil_id is not None:
            conds.append(Muvekkil.id != exclude_muvekkil_id)
        return (await db.execute(select(Muvekkil.id).where(and_(*conds)).limit(1))).first() is not None

    async def email_taken_in_organization(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        email: str,
        exclude_muvekkil_id: Optional[UUID] = None,
    ) -> bool:
        conds = [
            Muvekkil.organization_id == organization_id,
            Muvekkil.email == email,
        ]
        if exclude_muvekkil_id is not None:
            conds.append(Muvekkil.id != exclude_muvekkil_id)
        return (await db.execute(select(Muvekkil.id).where(and_(*conds)).limit(1))).first() is not None

    # ------------------------------------------------------------------
    # Archive / unarchive (soft delete)
    # ------------------------------------------------------------------

    async def archive(self, db: AsyncSession, *, muvekkil: Muvekkil) -> Muvekkil:
        muvekkil.is_archived = True
        muvekkil.archived_at = datetime.utcnow()
        db.add(muvekkil)
        await db.flush()
        await db.refresh(muvekkil)
        return muvekkil

    async def unarchive(self, db: AsyncSession, *, muvekkil: Muvekkil) -> Muvekkil:
        muvekkil.is_archived = False
        muvekkil.archived_at = None
        db.add(muvekkil)
        await db.flush()
        await db.refresh(muvekkil)
        return muvekkil


muvekkil_crud = CRUDMuvekkil(Muvekkil)
