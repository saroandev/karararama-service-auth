"""
Muvekkiller (Clients) management endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud import muvekkil_crud, organization_crud
from app.crud.iliskili_muvekkil import iliskili_muvekkil_crud
from app.models import User
from app.schemas import (
    MuvekkillCreate,
    MuvekkillUpdate,
    MuvekkillResponse,
    MuvekkillWithOrganizations,
    OrganizationResponse,
)
from app.schemas.iliskili_muvekkil import IliskiliMuvekkillResponse
from app.api.deps import get_current_active_user, require_role

router = APIRouter()


@router.post("/", response_model=MuvekkillWithOrganizations, status_code=status.HTTP_201_CREATED)
async def create_muvekkil(
    muvekkil_in: MuvekkillCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """
    Create new muvekkil and attach it to the caller's organization (admin only).

    - Admin: müvekkil her zaman admin'in kendi organizasyonuna bağlanır; body'de
      organization_id verilirse admin'in org'u ile aynı olmalıdır.
    - Superuser: body'de organization_id zorunludur; verilen organizasyona bağlanır.

    Raises:
        HTTPException: If email already exists or organization is invalid.
    """
    user_roles = [role.name.lower() for role in current_user.roles]
    is_superuser = "superuser" in user_roles

    if is_superuser:
        if not muvekkil_in.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Superuser müvekkil oluştururken organization_id zorunludur"
            )
        target_org_id = muvekkil_in.organization_id
    else:
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Organizasyonunuz tanımlı değil"
            )
        if (
            muvekkil_in.organization_id
            and muvekkil_in.organization_id != current_user.organization_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sadece kendi organizasyonunuza müvekkil ekleyebilirsiniz"
            )
        target_org_id = current_user.organization_id

    organization = await organization_crud.get(db, id=target_org_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    # Email uniqueness is scoped to the target organization
    if muvekkil_in.email:
        already_used = await muvekkil_crud.email_exists_in_organizations(
            db,
            email=muvekkil_in.email,
            organization_ids=[target_org_id],
        )
        if already_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu e-posta adresi bu organizasyonda zaten kayıtlı"
            )

    muvekkil = await muvekkil_crud.create(
        db, obj_in=muvekkil_in, organization=organization
    )
    return muvekkil


@router.get("/", response_model=List[MuvekkillResponse])
async def list_muvekkiller(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """
    List muvekkiller (admin only).

    Superuser can see all muvekkiller.
    Admin can only see muvekkiller from their organization.
    """
    # Check if user is superuser
    user_roles = [role.name.lower() for role in current_user.roles]

    if "superuser" in user_roles:
        # Superuser can see all muvekkiller
        muvekkiller = await muvekkil_crud.get_multi(db, skip=skip, limit=limit)
    else:
        # Admin can only see their organization's muvekkiller
        if not current_user.organization_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organizasyonunuz tanımlı değil"
            )

        muvekkiller = await muvekkil_crud.get_by_organization(
            db,
            organization_id=current_user.organization_id,
            skip=skip,
            limit=limit
        )

    return muvekkiller


@router.get("/{muvekkil_id}", response_model=MuvekkillWithOrganizations)
async def get_muvekkil(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """
    Get muvekkil by ID with organizations (admin only).

    Superuser can see any muvekkil.
    Admin can only see muvekkiller from their organization.
    """
    muvekkil = await muvekkil_crud.get_with_organizations(db, id=muvekkil_id)
    if not muvekkil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Müvekkil bulunamadı"
        )

    # Check if user has access to this muvekkil
    user_roles = [role.name.lower() for role in current_user.roles]
    if "superuser" not in user_roles:
        # Admin can only access muvekkiller from their organization
        org_ids = [org.id for org in muvekkil.organizations]
        if current_user.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu müvekkile erişim yetkiniz yok"
            )

    return muvekkil


@router.put("/{muvekkil_id}", response_model=MuvekkillResponse)
async def update_muvekkil(
    muvekkil_id: UUID,
    muvekkil_in: MuvekkillUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """
    Update muvekkil (admin only).

    Superuser can update any muvekkil.
    Admin can only update muvekkiller from their organization.
    """
    muvekkil = await muvekkil_crud.get_with_organizations(db, id=muvekkil_id)
    if not muvekkil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Müvekkil bulunamadı"
        )

    # Check if user has access to this muvekkil
    user_roles = [role.name.lower() for role in current_user.roles]
    if "superuser" not in user_roles:
        # Admin can only update muvekkiller from their organization
        org_ids = [org.id for org in muvekkil.organizations]
        if current_user.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu müvekkili güncelleme yetkiniz yok"
            )

    # Email uniqueness is scoped to the muvekkil's organizations
    if muvekkil_in.email and muvekkil_in.email != muvekkil.email:
        already_used = await muvekkil_crud.email_exists_in_organizations(
            db,
            email=muvekkil_in.email,
            organization_ids=[org.id for org in muvekkil.organizations],
            exclude_muvekkil_id=muvekkil.id,
        )
        if already_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu e-posta adresi bu organizasyonda zaten kayıtlı"
            )

    updated = await muvekkil_crud.update(db, db_obj=muvekkil, obj_in=muvekkil_in)
    return updated


@router.delete("/{muvekkil_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_muvekkil(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """
    Delete muvekkil (admin only).

    Superuser can delete any muvekkil.
    Admin can only delete muvekkiller from their organization.
    """
    muvekkil = await muvekkil_crud.get_with_organizations(db, id=muvekkil_id)
    if not muvekkil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Müvekkil bulunamadı"
        )

    # Check if user has access to this muvekkil
    user_roles = [role.name.lower() for role in current_user.roles]
    if "superuser" not in user_roles:
        # Admin can only delete muvekkiller from their organization
        org_ids = [org.id for org in muvekkil.organizations]
        if current_user.organization_id not in org_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu müvekkili silme yetkiniz yok"
            )

    await muvekkil_crud.delete(db, id=muvekkil_id)


@router.post(
    "/{muvekkil_id}/organizations/{organization_id}",
    response_model=MuvekkillWithOrganizations
)
async def add_organization_to_muvekkil(
    muvekkil_id: UUID,
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """
    Add organization to muvekkil (admin only).

    Raises:
        HTTPException: If muvekkil or organization not found
    """
    muvekkil = await muvekkil_crud.get_with_organizations(db, id=muvekkil_id)
    if not muvekkil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Müvekkil bulunamadı"
        )

    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    # Check if admin can manage this organization
    user_roles = [role.name.lower() for role in current_user.roles]
    if "superuser" not in user_roles:
        # Regular admin can only add to their own organization
        if str(current_user.organization_id) != str(organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sadece kendi organizasyonunuza müvekkil ekleyebilirsiniz"
            )

    updated = await muvekkil_crud.add_organization(
        db,
        muvekkil=muvekkil,
        organization=organization
    )
    return updated


@router.delete(
    "/{muvekkil_id}/organizations/{organization_id}",
    response_model=MuvekkillWithOrganizations
)
async def remove_organization_from_muvekkil(
    muvekkil_id: UUID,
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """
    Remove organization from muvekkil (admin only).

    Raises:
        HTTPException: If muvekkil or organization not found
    """
    muvekkil = await muvekkil_crud.get_with_organizations(db, id=muvekkil_id)
    if not muvekkil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Müvekkil bulunamadı"
        )

    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    # Check if admin can manage this organization
    user_roles = [role.name.lower() for role in current_user.roles]
    if "superuser" not in user_roles:
        # Regular admin can only remove from their own organization
        if str(current_user.organization_id) != str(organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sadece kendi organizasyonunuzdan müvekkil çıkarabilirsiniz"
            )

    updated = await muvekkil_crud.remove_organization(
        db,
        muvekkil=muvekkil,
        organization=organization
    )
    return updated


@router.get(
    "/{muvekkil_id}/organizations",
    response_model=List[OrganizationResponse]
)
async def get_muvekkil_organizations(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """
    Get all organizations for a muvekkil (admin only).

    Raises:
        HTTPException: If muvekkil not found
    """
    muvekkil = await muvekkil_crud.get_with_organizations(db, id=muvekkil_id)
    if not muvekkil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Müvekkil bulunamadı"
        )
    return muvekkil.organizations


def _check_muvekkil_org_access(
    muvekkil,
    current_user: User,
    forbidden_detail: str,
) -> None:
    """Raise 403 if the admin user has no organization access to muvekkil."""
    user_roles = [role.name.lower() for role in current_user.roles]
    if "superuser" in user_roles:
        return
    org_ids = [org.id for org in muvekkil.organizations]
    if current_user.organization_id not in org_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=forbidden_detail,
        )


@router.get(
    "/{muvekkil_id}/iliskili-muvekkiller",
    response_model=List[IliskiliMuvekkillResponse],
)
async def list_assigned_iliskili_muvekkiller(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "superuser"]))
):
    """List iliskili muvekkiller assigned to this muvekkil."""
    muvekkil = await muvekkil_crud.get_with_organizations(db, id=muvekkil_id)
    if not muvekkil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Müvekkil bulunamadı",
        )

    _check_muvekkil_org_access(
        muvekkil, current_user, "Bu müvekkile erişim yetkiniz yok"
    )

    results = await iliskili_muvekkil_crud.get_by_muvekkil(db, muvekkil_id=muvekkil_id)
    return results
