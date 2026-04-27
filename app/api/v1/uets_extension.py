"""
UETS Browser Extension endpoints.

These endpoints exist alongside the regular /uets/* routes because the
extension cannot mutate the user's JWT to switch organizations. Instead it:
  1) calls /uets-extension/list-organizations to discover every org the
     authenticated user is a member of (regardless of the JWT's active org),
  2) calls /uets-extension/list-uets-accounts?organization_id=... to list
     accounts for a chosen org, gated by membership.

The /uets/connected-accounts endpoint is kept JWT-active-org-scoped for the
in-app UI; it is not equivalent to these extension endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_jwt_payload
from app.core.database import get_db
from app.core.security import JWTPayload
from app.crud import organization_member_crud
from app.crud.uets_account import uets_account_crud
from app.schemas.uets_account import UetsAccountItem, UetsAccountListResponse

router = APIRouter()


class ExtensionOrganizationItem(BaseModel):
    """One organization the caller belongs to, with the caller's role in it."""
    id: UUID
    name: str
    role: str


class ExtensionOrganizationListResponse(BaseModel):
    organizations: List[ExtensionOrganizationItem] = Field(default_factory=list)


@router.get(
    "/list-organizations",
    response_model=ExtensionOrganizationListResponse,
    summary="List caller's organizations (extension)",
    description=(
        "Return every organization the authenticated user is a member of. "
        "Independent of the JWT's active organization claim."
    ),
)
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    payload: JWTPayload = Depends(get_jwt_payload),
) -> ExtensionOrganizationListResponse:
    memberships = await organization_member_crud.get_user_memberships(
        db, user_id=UUID(payload.sub)
    )

    return ExtensionOrganizationListResponse(
        organizations=[
            ExtensionOrganizationItem(
                id=m.organization.id,
                name=m.organization.name,
                role=m.role,
            )
            for m in memberships
            if m.organization is not None
        ]
    )


@router.get(
    "/list-uets-accounts",
    response_model=UetsAccountListResponse,
    summary="List UETS accounts of a specific organization (extension)",
    description=(
        "Return all UETS accounts connected within the given organization. "
        "Caller must be a member of that organization."
    ),
)
async def list_uets_accounts(
    organization_id: UUID = Query(..., description="Target organization ID"),
    db: AsyncSession = Depends(get_db),
    payload: JWTPayload = Depends(get_jwt_payload),
) -> UetsAccountListResponse:
    membership = await organization_member_crud.get_membership(
        db, user_id=UUID(payload.sub), organization_id=organization_id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu organizasyonun üyesi değilsiniz",
        )

    accounts = await uets_account_crud.get_by_org(db, org_id=organization_id)

    return UetsAccountListResponse(
        accounts=[
            UetsAccountItem(
                uets_account_name=account.uets_account_name,
                created_at=account.created_at,
            )
            for account in accounts
        ]
    )
