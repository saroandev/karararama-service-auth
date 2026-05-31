"""
Muvekkiller (Portals) management endpoints.

A muvekkil = a Portal. Belongs to exactly one organization and lives
inside the caller's active org's data — there is no cross-org muvekkil
access (except superuser).
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.crud import muvekkil_crud
from app.crud.iliskili_muvekkil import iliskili_muvekkil_crud
from app.models import Muvekkil, MuvekkilUnvan, User
from app.schemas import (
    MuvekkillCreate,
    MuvekkillListResponse,
    MuvekkillResponse,
    MuvekkillUpdate,
)
from app.schemas.iliskili_muvekkil import IliskiliMuvekkillResponse

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_superuser(user: User) -> bool:
    return any(role.name.lower() == "superuser" for role in user.roles)


def _require_active_organization(user: User) -> UUID:
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aktif bir organizasyonunuz yok",
        )
    return user.organization_id


async def _get_portal_or_404(
    db: AsyncSession, *, muvekkil_id: UUID, current_user: User
) -> Muvekkil:
    """Fetch the muvekkil and enforce that the caller can see it.

    Superuser sees everything; other users see only their own org's
    muvekkiller. Returns the resolved row; raises 404 (not 403) when
    the muvekkil is outside the caller's org so callers can't probe
    other orgs' UUIDs.
    """
    muvekkil = await muvekkil_crud.get(db, id=muvekkil_id)
    if not muvekkil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Müvekkil bulunamadı"
        )
    if _is_superuser(current_user):
        return muvekkil
    org_id = _require_active_organization(current_user)
    if muvekkil.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Müvekkil bulunamadı"
        )
    return muvekkil


async def _check_identity_duplicates(
    db: AsyncSession,
    *,
    organization_id: UUID,
    tckn: Optional[str],
    vkn: Optional[str],
    email: Optional[str],
    exclude_muvekkil_id: Optional[UUID] = None,
) -> None:
    if tckn and await muvekkil_crud.tckn_taken(
        db,
        organization_id=organization_id,
        tckn=tckn,
        exclude_muvekkil_id=exclude_muvekkil_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu TCKN ile kayıtlı başka bir müvekkil var",
        )
    if vkn and await muvekkil_crud.vkn_taken(
        db,
        organization_id=organization_id,
        vkn=vkn,
        exclude_muvekkil_id=exclude_muvekkil_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu VKN ile kayıtlı başka bir müvekkil var",
        )
    if email and await muvekkil_crud.email_taken_in_organization(
        db,
        organization_id=organization_id,
        email=email,
        exclude_muvekkil_id=exclude_muvekkil_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi bu organizasyonda zaten kayıtlı",
        )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.post(
    "/", response_model=MuvekkillResponse, status_code=status.HTTP_201_CREATED
)
async def create_muvekkil(
    muvekkil_in: MuvekkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new portal pinned to the caller's active organization.

    organization_id is implicit — there is no cross-org portal create
    (Superusers can still do it via DB or future admin tooling, but the
    user-facing endpoint enforces self-org isolation).
    """
    organization_id = _require_active_organization(current_user)
    await _check_identity_duplicates(
        db,
        organization_id=organization_id,
        tckn=muvekkil_in.tckn,
        vkn=muvekkil_in.vkn,
        email=muvekkil_in.email,
    )
    muvekkil = await muvekkil_crud.create_for_organization(
        db, obj_in=muvekkil_in, organization_id=organization_id
    )
    await db.commit()
    await db.refresh(muvekkil)
    return muvekkil


@router.get("/", response_model=MuvekkillListResponse)
async def list_muvekkiller(
    skip: int = 0,
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, description="Ad/soyad/email/TCKN/VKN'de arama"),
    include_archived: bool = Query(False, description="Arşivlenmişleri de göster"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List portals in the caller's active organization."""
    organization_id = _require_active_organization(current_user)
    items = await muvekkil_crud.list_by_organization(
        db,
        organization_id=organization_id,
        skip=skip,
        limit=limit,
        search=search,
        include_archived=include_archived,
    )
    total = await muvekkil_crud.count_by_organization(
        db,
        organization_id=organization_id,
        search=search,
        include_archived=include_archived,
    )
    return MuvekkillListResponse(total=total, items=items)


@router.get("/{muvekkil_id}", response_model=MuvekkillResponse)
async def get_muvekkil(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return await _get_portal_or_404(
        db, muvekkil_id=muvekkil_id, current_user=current_user
    )


@router.put("/{muvekkil_id}", response_model=MuvekkillResponse)
async def update_muvekkil(
    muvekkil_id: UUID,
    muvekkil_in: MuvekkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Patch portal fields. The PUT verb here is historical — only the
    fields present in the body are updated (matches MuvekkillUpdate's
    all-optional shape)."""
    muvekkil = await _get_portal_or_404(
        db, muvekkil_id=muvekkil_id, current_user=current_user
    )

    # Resolve the post-update view of (unvan, tckn, vkn) so we can both
    # enforce the type invariant and run duplicate checks against the
    # final state, not stale values.
    new_unvan = muvekkil_in.unvan or muvekkil.unvan
    new_tckn = muvekkil_in.tckn if "tckn" in muvekkil_in.model_fields_set else muvekkil.tckn
    new_vkn = muvekkil_in.vkn if "vkn" in muvekkil_in.model_fields_set else muvekkil.vkn
    if new_unvan == MuvekkilUnvan.KISI and new_vkn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gerçek kişi müvekkilde VKN olamaz",
        )
    if new_unvan == MuvekkilUnvan.SIRKET and new_tckn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tüzel kişi müvekkilde TCKN olamaz",
        )

    await _check_identity_duplicates(
        db,
        organization_id=muvekkil.organization_id,
        tckn=new_tckn,
        vkn=new_vkn,
        email=muvekkil_in.email
        if "email" in muvekkil_in.model_fields_set
        else None,
        exclude_muvekkil_id=muvekkil.id,
    )

    payload = muvekkil_in.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(muvekkil, field, value)
    db.add(muvekkil)
    await db.commit()
    await db.refresh(muvekkil)
    return muvekkil


@router.delete("/{muvekkil_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_muvekkil(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Hard-delete a portal. Cascades drop portal_members and iliskili
    rows via ON DELETE CASCADE. Prefer the archive endpoint for soft
    delete in most flows."""
    muvekkil = await _get_portal_or_404(
        db, muvekkil_id=muvekkil_id, current_user=current_user
    )
    await db.delete(muvekkil)
    await db.commit()


@router.post("/{muvekkil_id}/archive", response_model=MuvekkillResponse)
async def archive_muvekkil(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Soft-archive a portal: hides from default list, preserves data."""
    muvekkil = await _get_portal_or_404(
        db, muvekkil_id=muvekkil_id, current_user=current_user
    )
    if muvekkil.is_archived:
        return muvekkil
    muvekkil = await muvekkil_crud.archive(db, muvekkil=muvekkil)
    await db.commit()
    await db.refresh(muvekkil)
    return muvekkil


@router.post("/{muvekkil_id}/unarchive", response_model=MuvekkillResponse)
async def unarchive_muvekkil(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    muvekkil = await _get_portal_or_404(
        db, muvekkil_id=muvekkil_id, current_user=current_user
    )
    if not muvekkil.is_archived:
        return muvekkil
    muvekkil = await muvekkil_crud.unarchive(db, muvekkil=muvekkil)
    await db.commit()
    await db.refresh(muvekkil)
    return muvekkil


# ---------------------------------------------------------------------------
# Iliskili muvekkiller (unchanged contract)
# ---------------------------------------------------------------------------


@router.get(
    "/{muvekkil_id}/iliskili-muvekkiller",
    response_model=List[IliskiliMuvekkillResponse],
)
async def list_assigned_iliskili_muvekkiller(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List iliskili muvekkiller assigned to this portal."""
    await _get_portal_or_404(
        db, muvekkil_id=muvekkil_id, current_user=current_user
    )
    return await iliskili_muvekkil_crud.get_by_muvekkil(db, muvekkil_id=muvekkil_id)
