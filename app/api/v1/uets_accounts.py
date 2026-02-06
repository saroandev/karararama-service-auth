"""
UETS account management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_active_user
from app.crud.uets_account import uets_account_crud
from app.models import User
from app.schemas.uets_account import (
    UetsAccountCreate,
    UetsAccountResponse,
    UetsAccountListResponse,
    UetsAccountItem,
)

router = APIRouter()


@router.post(
    "/connect-account",
    response_model=UetsAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Connect a UETS account",
    description="Connect a new UETS account to the current user."
)
async def connect_uets_account(
    account_data: UetsAccountCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> UetsAccountResponse:
    """
    Connect a new UETS account.

    Args:
        account_data: UETS account name to connect
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created UETS account connection

    Raises:
        HTTPException 403: User has no organization
        HTTPException 409: Account already connected
    """
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcının bir organizasyona atanması gerekiyor"
        )

    uets_account = await uets_account_crud.create(
        db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        uets_account_name=account_data.uets_account_name
    )

    if uets_account is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu UETS hesabı zaten bağlı"
        )

    return UetsAccountResponse(
        org_id=uets_account.org_id,
        user_id=uets_account.user_id,
        uets_account_name=uets_account.uets_account_name,
        created_at=uets_account.created_at
    )


@router.get(
    "/connected-accounts",
    response_model=UetsAccountListResponse,
    summary="List connected UETS accounts",
    description="List all UETS accounts connected to the current user."
)
async def list_connected_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> UetsAccountListResponse:
    """
    List all connected UETS accounts for the current user.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of connected UETS accounts

    Raises:
        HTTPException 403: User has no organization
    """
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcının bir organizasyona atanması gerekiyor"
        )

    accounts = await uets_account_crud.get_by_user(
        db,
        org_id=current_user.organization_id,
        user_id=current_user.id
    )

    return UetsAccountListResponse(
        accounts=[
            UetsAccountItem(
                uets_account_name=account.uets_account_name,
                created_at=account.created_at
            )
            for account in accounts
        ]
    )


class DeleteResponse(BaseModel):
    """Response schema for delete operations."""
    message: str


@router.delete(
    "/disconnect-account/{uets_account_name}",
    response_model=DeleteResponse,
    summary="Disconnect a UETS account",
    description="Disconnect a UETS account from the current user."
)
async def disconnect_uets_account(
    uets_account_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> DeleteResponse:
    """
    Disconnect a UETS account.

    Args:
        uets_account_name: UETS account name to disconnect
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message

    Raises:
        HTTPException 403: User has no organization
        HTTPException 404: Account not found
    """
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcının bir organizasyona atanması gerekiyor"
        )

    deleted = await uets_account_crud.delete(
        db,
        org_id=current_user.organization_id,
        user_id=current_user.id,
        uets_account_name=uets_account_name
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UETS hesabı bulunamadı"
        )

    return DeleteResponse(message=f"UETS hesabı '{uets_account_name}' başarıyla silindi")
