"""
UYAP account management endpoints.

UYAP accounts live at the organization level (unlike UETS accounts, which
are scoped per-user-per-org). Names must be unique within an organization
but any member of the org can add/list/remove them. The active organization
and acting user are taken from the JWT.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_jwt_payload, require_permission
from app.core.security import JWTPayload
from app.crud import organization_member_crud
from app.crud.uyap_account import uyap_account_crud
from app.schemas.uyap_account import (
    UyapAccountCreate,
    UyapAccountResponse,
    UyapAccountListResponse,
    UyapAccountItem,
)

router = APIRouter()


@router.post(
    "/connect-account",
    response_model=UyapAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a UYAP account",
    description="Add a new UYAP account to the caller's active organization."
)
async def connect_uyap_account(
    account_data: UyapAccountCreate,
    organization_id: Optional[UUID] = Query(
        None,
        description=(
            "Target organization. When omitted, the caller's active "
            "organization from the JWT is used. The caller must be a member "
            "of the given organization."
        ),
    ),
    db: AsyncSession = Depends(get_db),
    payload: JWTPayload = Depends(require_permission("uyap-account", "connect")),
) -> UyapAccountResponse:
    """
    Add a UYAP account to an organization. The target org defaults to the
    caller's *active* organization from the JWT, but an explicit
    ``organization_id`` may be passed to act on another org the caller belongs
    to (e.g. without switching their active org). The acting user is always
    taken from the JWT.
    """
    target_org_id = organization_id or (
        UUID(payload.organization_id) if payload.organization_id else None
    )
    if target_org_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcının bir organizasyona atanması gerekiyor"
        )

    # When acting on an org other than the JWT's active one, verify membership
    # so a caller cannot add accounts to organizations they don't belong to.
    if str(target_org_id) != payload.organization_id:
        membership = await organization_member_crud.get_membership(
            db, user_id=UUID(payload.sub), organization_id=target_org_id
        )
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu organizasyonun üyesi değilsiniz"
            )

    uyap_account = await uyap_account_crud.create(
        db,
        org_id=target_org_id,
        uyap_account_name=account_data.uyap_account_name,
        created_by_user_id=UUID(payload.sub),
    )

    if uyap_account is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu isimde bir UYAP hesabı bu organizasyonda zaten mevcut"
        )

    return UyapAccountResponse(
        org_id=uyap_account.org_id,
        uyap_account_name=uyap_account.uyap_account_name,
        created_by_user_id=uyap_account.created_by_user_id,
        created_at=uyap_account.created_at,
    )


@router.get(
    "/connected-accounts",
    response_model=UyapAccountListResponse,
    summary="List connected UYAP accounts",
    description="List all UYAP accounts connected within the caller's active organization."
)
async def list_connected_accounts(
    db: AsyncSession = Depends(get_db),
    payload: JWTPayload = Depends(get_jwt_payload),
) -> UyapAccountListResponse:
    """
    List every UYAP account connected within the caller's *active*
    organization. Active org is taken from the JWT's `organization_id` claim
    so the list reflects whichever organization the caller has switched to.
    """
    if not payload.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcının bir organizasyona atanması gerekiyor"
        )

    accounts = await uyap_account_crud.get_by_org(
        db, org_id=UUID(payload.organization_id)
    )

    return UyapAccountListResponse(
        accounts=[
            UyapAccountItem(
                uyap_account_name=account.uyap_account_name,
                created_by_user_id=account.created_by_user_id,
                created_at=account.created_at,
            )
            for account in accounts
        ]
    )


class DeleteResponse(BaseModel):
    """Response schema for delete operations."""
    message: str


@router.delete(
    "/disconnect-account/{uyap_account_name}",
    response_model=DeleteResponse,
    summary="Disconnect a UYAP account",
    description="Remove a UYAP account from the caller's active organization."
)
async def disconnect_uyap_account(
    uyap_account_name: str,
    db: AsyncSession = Depends(get_db),
    payload: JWTPayload = Depends(require_permission("uyap-account", "disconnect")),
) -> DeleteResponse:
    """
    Delete a UYAP account from the caller's active organization. Any member
    of the org with the `uyap-account:disconnect` permission can remove any
    account in that org.
    """
    if not payload.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcının bir organizasyona atanması gerekiyor"
        )

    deleted = await uyap_account_crud.delete(
        db,
        org_id=UUID(payload.organization_id),
        uyap_account_name=uyap_account_name,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UYAP hesabı bulunamadı"
        )

    return DeleteResponse(message=f"UYAP hesabı '{uyap_account_name}' başarıyla silindi")
