"""
Portal members + portal-scoped invitations.

Routes mounted under /api/v1/muvekkiller/{muvekkil_id}/...:
  - GET  /members          — list active members + pending invites
  - POST /members          — add an existing user with a role
  - PATCH /members/{user_id} — change role / activate / deactivate
  - DELETE /members/{user_id} — deactivate (soft remove)
  - POST /invitations      — send portal-scoped invite by email
  - POST /invitations/{invitation_id}/revoke — cancel a pending invite

All write paths require PortalRole.MANAGER (or superuser, or org
owner/admin for the bootstrap case — see app/api/portal_deps.py).
Read paths are open to any active portal member.
"""
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.portal_deps import (
    PortalContext,
    require_portal_role,
)
from app.core.config import settings
from app.core.database import get_db
from app.crud import (
    invitation_crud,
    portal_member_crud,
    user_crud,
)
from app.models import (
    Invitation,
    InvitationStatus,
    PortalRole,
    User,
)
from app.schemas import (
    PortalMemberCreate,
    PortalMemberInviteRequest,
    PortalMemberResponse,
    PortalMemberUpdate,
    PortalMembersListResponse,
    PortalPendingInvite,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


@router.get(
    "/{muvekkil_id}/members",
    response_model=PortalMembersListResponse,
    summary="List active portal members + pending invitations",
)
async def list_portal_members(
    muvekkil_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: PortalContext = Depends(
        require_portal_role(
            PortalRole.MANAGER,
            PortalRole.RESPONSIBLE,
            PortalRole.USER,
            PortalRole.GUEST,
        )
    ),
):
    members = await portal_member_crud.list_by_portal(
        db, muvekkil_id=ctx.portal.id, active_only=True
    )

    # Pending (non-expired, status=PENDING) portal-scoped invites only.
    stmt = (
        select(Invitation)
        .where(
            Invitation.muvekkil_id == ctx.portal.id,
            Invitation.status == InvitationStatus.PENDING,
            Invitation.expires_at > datetime.utcnow(),
        )
    )
    pending = list((await db.execute(stmt)).scalars().all())

    return PortalMembersListResponse(
        members=[PortalMemberResponse.model_validate(m) for m in members],
        pending_invitations=[
            PortalPendingInvite(
                id=inv.id,
                email=inv.email,
                portal_role=inv.portal_role or "",
                invited_by_user_id=inv.invited_by_user_id,
                expires_at=inv.expires_at,
                created_at=inv.created_at,
            )
            for inv in pending
        ],
        total_members=len(members),
        total_pending=len(pending),
    )


# ---------------------------------------------------------------------------
# Add existing user
# ---------------------------------------------------------------------------


@router.post(
    "/{muvekkil_id}/members",
    response_model=PortalMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an existing user to the portal",
)
async def add_portal_member(
    muvekkil_id: UUID,
    body: PortalMemberCreate,
    db: AsyncSession = Depends(get_db),
    ctx: PortalContext = Depends(require_portal_role(PortalRole.MANAGER)),
):
    """Pin an existing user account to this portal with the requested role.

    Use the invite endpoint for unknown emails — that flow provisions a
    Guest user account on accept.
    """
    target = await user_crud.get(db, id=body.user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kullanıcı bulunamadı"
        )

    # A guest user can only ever hold the GUEST role; manager/responsible/
    # user are firm-side roles that imply org membership invariants the
    # guest_user account doesn't satisfy.
    if target.user_type == "guest" and body.portal_role != PortalRole.GUEST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Misafir kullanıcılara sadece guest rolü atanabilir",
        )

    member = await portal_member_crud.create(
        db,
        muvekkil_id=ctx.portal.id,
        user_id=target.id,
        portal_role=body.portal_role.value,
        invited_by_user_id=ctx.current_user.id,
    )
    await db.commit()
    refreshed = await portal_member_crud.get(db, id=member.id)
    return refreshed


# ---------------------------------------------------------------------------
# Update / remove
# ---------------------------------------------------------------------------


@router.patch(
    "/{muvekkil_id}/members/{user_id}",
    response_model=PortalMemberResponse,
    summary="Update a portal member's role or active flag",
)
async def update_portal_member(
    muvekkil_id: UUID,
    user_id: UUID,
    body: PortalMemberUpdate,
    db: AsyncSession = Depends(get_db),
    ctx: PortalContext = Depends(require_portal_role(PortalRole.MANAGER)),
):
    membership = await portal_member_crud.get_membership(
        db, muvekkil_id=ctx.portal.id, user_id=user_id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu portalda üyelik bulunamadı",
        )

    # Manager cannot demote themselves — locks the portal out otherwise.
    if (
        membership.user_id == ctx.current_user.id
        and membership.portal_role == PortalRole.MANAGER.value
        and body.portal_role is not None
        and body.portal_role != PortalRole.MANAGER
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kendi yönetici rolünüzü düşüremezsiniz",
        )

    await portal_member_crud.update(
        db,
        member=membership,
        portal_role=body.portal_role.value if body.portal_role else None,
        is_active=body.is_active,
    )
    await db.commit()
    return await portal_member_crud.get(db, id=membership.id)


@router.delete(
    "/{muvekkil_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-remove a member (deactivates row, preserves history)",
)
async def remove_portal_member(
    muvekkil_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: PortalContext = Depends(require_portal_role(PortalRole.MANAGER)),
):
    if user_id == ctx.current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kendinizi portaldan çıkaramazsınız",
        )
    membership = await portal_member_crud.get_membership(
        db, muvekkil_id=ctx.portal.id, user_id=user_id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu portalda üyelik bulunamadı",
        )
    await portal_member_crud.deactivate(db, member=membership)
    await db.commit()


# ---------------------------------------------------------------------------
# Invitations (portal-scoped)
# ---------------------------------------------------------------------------


@router.post(
    "/{muvekkil_id}/invitations",
    response_model=PortalPendingInvite,
    status_code=status.HTTP_201_CREATED,
    summary="Invite someone (by email) to the portal",
)
async def invite_to_portal(
    muvekkil_id: UUID,
    body: PortalMemberInviteRequest,
    db: AsyncSession = Depends(get_db),
    ctx: PortalContext = Depends(require_portal_role(PortalRole.MANAGER)),
):
    """Send a portal-scoped invitation. The accept flow (see
    app/api/v1/invitations.py) attaches the resulting user — either an
    existing account by email or a freshly-provisioned Guest user — to
    portal_members with the requested role."""
    portal_role_value = (
        body.portal_role.value
        if isinstance(body.portal_role, PortalRole)
        else str(body.portal_role)
    )

    # Reject obvious duplicates: if the user already exists and is an
    # active portal member, no point inviting.
    existing_user = await user_crud.get_by_email(db, email=body.email)
    if existing_user is not None:
        existing_membership = await portal_member_crud.get_membership(
            db, muvekkil_id=ctx.portal.id, user_id=existing_user.id
        )
        if existing_membership is not None and existing_membership.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu kişi zaten portalda aktif üye",
            )

    # Pending portal invite for the same email on same portal? Block.
    stmt = select(Invitation).where(
        Invitation.muvekkil_id == ctx.portal.id,
        Invitation.email == body.email,
        Invitation.status == InvitationStatus.PENDING,
        Invitation.expires_at > datetime.utcnow(),
    )
    if (await db.execute(stmt)).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu e-posta için zaten bekleyen bir davet var",
        )

    invitation = await invitation_crud.create_with_token(
        db,
        email=body.email,
        organization_id=ctx.portal.organization_id,
        invited_by_user_id=ctx.current_user.id,
        role="member",                 # fallback if accept is org-scoped
        muvekkil_id=ctx.portal.id,
        portal_role=portal_role_value,
        expires_in_days=settings.INVITATION_EXPIRE_DAYS,
    )

    # Email delivery is best-effort — failure does not roll back the
    # invitation row. The token can still be redeemed manually.
    try:
        from app.services import send_invitation_email
        inviter_name = (
            f"{ctx.current_user.first_name} {ctx.current_user.last_name}".strip()
            or ctx.current_user.email.split("@")[0]
        )
        await send_invitation_email(
            email=body.email,
            inviter_name=inviter_name,
            organization_name=ctx.portal.organization.name
            if ctx.portal.organization
            else "OneDocs",
            organization_type="law_firm",
            role=portal_role_value,
            invitation_token=str(invitation.token),
            expires_at=invitation.expires_at.strftime("%d.%m.%Y %H:%M"),
            expires_in_days=settings.INVITATION_EXPIRE_DAYS,
        )
    except Exception as exc:  # pragma: no cover — email path is side-effect
        print(f"⚠️ portal invite email failed for {body.email}: {exc}")

    return PortalPendingInvite(
        id=invitation.id,
        email=invitation.email,
        portal_role=invitation.portal_role or "",
        invited_by_user_id=invitation.invited_by_user_id,
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
    )


@router.post(
    "/{muvekkil_id}/invitations/{invitation_id}/revoke",
    status_code=status.HTTP_200_OK,
    summary="Revoke a pending portal invitation",
)
async def revoke_portal_invitation(
    muvekkil_id: UUID,
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    ctx: PortalContext = Depends(require_portal_role(PortalRole.MANAGER)),
):
    invitation = await invitation_crud.get(db, id=invitation_id)
    if (
        invitation is None
        or invitation.muvekkil_id != ctx.portal.id
        or invitation.status != InvitationStatus.PENDING
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Davet bulunamadı"
        )
    if invitation.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Davet zaten süresi dolmuş",
        )
    await invitation_crud.mark_revoked(db, invitation=invitation)
    return {"message": "Davet geri alındı", "invitation_id": str(invitation.id)}
