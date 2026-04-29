"""
İlişkili Müvekkiller (Related Clients) management endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud import muvekkil_crud, organization_crud
from app.crud.iliskili_muvekkil import iliskili_muvekkil_crud
from app.models import User
from app.schemas.iliskili_muvekkil import (
    IliskiliMuvekkillCreate,
    IliskiliMuvekkillUpdate,
    IliskiliMuvekkillResponse,
    IliskiliMuvekkillAssign,
)
from app.api.deps import get_current_active_user

router = APIRouter()


def _resolve_org_id(current_user: User, param_org_id: UUID | None) -> UUID:
    """Determine target organization: admin uses own, superuser requires query param."""
    user_roles = [role.name.lower() for role in current_user.roles]
    is_superuser = "superuser" in user_roles

    if is_superuser:
        if not param_org_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Superuser için organization_id zorunludur",
            )
        return param_org_id

    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organizasyonunuz tanımlı değil",
        )
    if param_org_id and param_org_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sadece kendi organizasyonunuza kayıt ekleyebilirsiniz",
        )
    return current_user.organization_id


def _check_org_access(current_user: User, organization_id: UUID) -> None:
    user_roles = [role.name.lower() for role in current_user.roles]
    if "superuser" in user_roles:
        return
    if current_user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu kaydı görüntüleme yetkiniz yok",
        )


@router.post("/", response_model=IliskiliMuvekkillResponse, status_code=status.HTTP_201_CREATED)
async def create_iliskili_muvekkil(
    data_in: IliskiliMuvekkillCreate,
    organization_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Create a new iliskili muvekkil (related client)."""
    target_org_id = _resolve_org_id(current_user, organization_id)

    org = await organization_crud.get(db, id=target_org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organizasyon bulunamadı")

    if data_in.email:
        exists = await iliskili_muvekkil_crud.email_exists_in_org(
            db, email=data_in.email, organization_id=target_org_id,
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu e-posta adresi bu organizasyonda zaten kayıtlı",
            )

    name_exists = await iliskili_muvekkil_crud.name_exists_in_org(
        db,
        unvan=data_in.unvan,
        first_name=data_in.first_name,
        last_name=data_in.last_name,
        organization_id=target_org_id,
    )
    if name_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu unvan ve ad-soyad ile bir ilişkili müvekkil zaten kayıtlı",
        )

    created = await iliskili_muvekkil_crud.create(db, obj_in=data_in, organization_id=target_org_id)
    return created


@router.get("/", response_model=List[IliskiliMuvekkillResponse])
async def list_iliskili_muvekkiller(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List unassigned iliskili muvekkiller for the caller's organization."""
    user_roles = [role.name.lower() for role in current_user.roles]

    if "superuser" in user_roles:
        results = await iliskili_muvekkil_crud.get_multi(db, skip=skip, limit=limit)
        return [r for r in results if r.muvekkil_id is None]

    if not current_user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organizasyonunuz tanımlı değil")

    return await iliskili_muvekkil_crud.get_unassigned_by_org(
        db, organization_id=current_user.organization_id, skip=skip, limit=limit,
    )


@router.get("/{iliskili_id}", response_model=IliskiliMuvekkillResponse)
async def get_iliskili_muvekkil(
    iliskili_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get a single iliskili muvekkil by ID."""
    record = await iliskili_muvekkil_crud.get(db, id=iliskili_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlişkili müvekkil bulunamadı")
    _check_org_access(current_user, record.organization_id)
    return record


@router.put("/{iliskili_id}", response_model=IliskiliMuvekkillResponse)
async def update_iliskili_muvekkil(
    iliskili_id: UUID,
    data_in: IliskiliMuvekkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update an iliskili muvekkil."""
    record = await iliskili_muvekkil_crud.get(db, id=iliskili_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlişkili müvekkil bulunamadı")
    _check_org_access(current_user, record.organization_id)

    if data_in.email and data_in.email != record.email:
        exists = await iliskili_muvekkil_crud.email_exists_in_org(
            db, email=data_in.email, organization_id=record.organization_id, exclude_id=record.id,
        )
        if exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu e-posta adresi bu organizasyonda zaten kayıtlı",
            )

    new_unvan = data_in.unvan if data_in.unvan is not None else record.unvan
    new_first = data_in.first_name if data_in.first_name is not None else record.first_name
    new_last = data_in.last_name if data_in.last_name is not None else record.last_name
    name_changed = (
        new_unvan != record.unvan
        or new_first.lower() != record.first_name.lower()
        or new_last.lower() != record.last_name.lower()
    )
    if name_changed:
        name_exists = await iliskili_muvekkil_crud.name_exists_in_org(
            db,
            unvan=new_unvan,
            first_name=new_first,
            last_name=new_last,
            organization_id=record.organization_id,
            exclude_id=record.id,
        )
        if name_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu unvan ve ad-soyad ile bir ilişkili müvekkil zaten kayıtlı",
            )

    updated = await iliskili_muvekkil_crud.update(db, db_obj=record, obj_in=data_in)
    return updated


@router.delete("/{iliskili_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_iliskili_muvekkil(
    iliskili_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Delete an iliskili muvekkil."""
    record = await iliskili_muvekkil_crud.get(db, id=iliskili_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlişkili müvekkil bulunamadı")
    _check_org_access(current_user, record.organization_id)
    await iliskili_muvekkil_crud.delete(db, id=iliskili_id)


@router.post("/{iliskili_id}/ata", response_model=IliskiliMuvekkillResponse)
async def assign_iliskili_muvekkil(
    iliskili_id: UUID,
    body: IliskiliMuvekkillAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Assign an iliskili muvekkil to a muvekkil."""
    record = await iliskili_muvekkil_crud.get(db, id=iliskili_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlişkili müvekkil bulunamadı")
    _check_org_access(current_user, record.organization_id)

    if record.muvekkil_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu ilişkili müvekkil zaten bir müvekkile atanmış",
        )

    muvekkil = await muvekkil_crud.get(db, id=body.muvekkil_id)
    if not muvekkil:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Müvekkil bulunamadı")

    return await iliskili_muvekkil_crud.assign(db, iliskili=record, muvekkil_id=body.muvekkil_id)


@router.delete("/{iliskili_id}/ata", response_model=IliskiliMuvekkillResponse)
async def unassign_iliskili_muvekkil(
    iliskili_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Unassign an iliskili muvekkil (return to pool)."""
    record = await iliskili_muvekkil_crud.get(db, id=iliskili_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İlişkili müvekkil bulunamadı")
    _check_org_access(current_user, record.organization_id)

    if record.muvekkil_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu ilişkili müvekkil zaten atanmamış",
        )

    return await iliskili_muvekkil_crud.unassign(db, iliskili=record)
