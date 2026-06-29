"""
Organization management endpoints.
"""
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.crud import organization_crud, user_crud, role_crud, invitation_crud, muvekkil_crud, organization_member_crud
from app.models import OrganizationMember, User, Organization, Invitation, InvitationStatus, RefreshToken
from app.models.user import user_roles as user_roles_table
from app.schemas import (
    OrganizationBrandingResponse,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationWithStats,
    OrganizationMemberResponse,
    PendingInvitationResponse,
    OrganizationMembersResponse,
    UserResponse,
    InvitationBatchCreate,
    InvitationResponse,
    MuvekkillResponse,
)
from app.api.deps import get_current_active_user, require_permission, require_role
from app.core.plans import WHITELABEL_PLANS
from app.core.security import JWTPayload
from app.core.subdomain import SlugError, validate_slug
from app.services.email import ROLE_DISPLAY_NAMES

router = APIRouter()


class ChangeMemberRoleRequest(BaseModel):
    """Payload for PATCH /organizations/me/members/{email}/role."""
    role: str


@router.get(
    "/by-slug/{slug}",
    response_model=OrganizationBrandingResponse,
    summary="Whitelabel branding lookup by subdomain slug",
)
async def get_organization_branding_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Public (no-auth) branding lookup used by the FE on whitelabel domains.

    The FE on `<slug>.onedocs.ai` calls this on boot to paint the login
    page with the org's logo/color before the visitor authenticates.

    Returns 404 for unknown or inactive organizations. Only branding-safe
    fields are exposed (see OrganizationBrandingResponse); sensitive fields
    like owner, plan, member count are deliberately omitted.
    """
    # Lowercase + length-cap the lookup key — subdomains are case-insensitive
    # in DNS, so "OzayHukuk.onedocs.ai" must resolve to the same row.
    normalized = (slug or "").strip().lower()[:63]
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı",
        )

    organization = await organization_crud.get_by_slug(db, slug=normalized)
    # Whitelabel subdomain is an Elite/Enterprise feature. Organizations on
    # lower tiers still have a slug column for identification (assigned by
    # migration backfill), but it is intentionally unaddressable — return
    # 404 so the FE falls back to canonical app.onedocs.ai branding.
    if (
        not organization
        or not organization.is_active
        or organization.plan not in WHITELABEL_PLANS
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı",
        )

    return organization


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_in: OrganizationCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new organization (PUBLIC endpoint - no auth required).

    User is found by email. User becomes the owner of the new organization.
    A user can only own ONE organization.

    Args:
        org_in: Organization creation data (includes owner_email, name, type, size)
        db: Database session

    Returns:
        Created organization

    Raises:
        HTTPException: If user not found, user already owns an organization, or email not verified
    """
    # Find user by email
    user = await user_crud.get_by_email(db, email=org_in.owner_email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu email adresiyle kayıtlı kullanıcı bulunamadı"
        )

    # Check if user already owns an organization
    stmt = select(Organization).where(Organization.owner_id == user.id)
    result = await db.execute(stmt)
    existing_org = result.scalar_one_or_none()

    if existing_org:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Zaten sahip olduğunuz bir organizasyon var."
        )

    # Whitelabel slug is provisioned at plan upgrade time (see
    # services/whitelabel.py::ensure_whitelabel_slug), not at org creation.
    # Free-trial / solo / team orgs intentionally start with slug=NULL so
    # they don't claim a tenant subdomain they aren't entitled to use.
    # Callers who *must* set a slug up front (admin tooling, migration
    # scripts) may still pass one explicitly — we validate and persist it
    # as-is, regardless of plan.
    slug = None
    if org_in.slug:
        try:
            requested_slug = validate_slug(org_in.slug.strip().lower())
        except SlugError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        if await organization_crud.get_by_slug(db, slug=requested_slug):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu subdomain zaten kullanımda",
            )
        slug = requested_slug

    # Create organization
    organization = Organization(
        name=org_in.name,
        slug=slug,
        owner_id=user.id,
        organization_type=org_in.organization_type,
        organization_size=org_in.organization_size,
    )
    db.add(organization)
    await db.flush()

    from app.crud import organization_member_crud

    await organization_member_crud.create(
        db,
        user_id=user.id,
        organization_id=organization.id,
        role="owner",
        is_primary=True,
    )

    user.organization_id = organization.id
    db.add(user)

    owner_role = await role_crud.get_by_name(db, name="owner")
    if not owner_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Owner role bulunamadı. Lütfen database seed işlemini çalıştırın."
        )

    await user_crud.add_role(
        db,
        user=user,
        role=owner_role,
        organization_id=organization.id,
    )
    await db.commit()
    await db.refresh(organization)
    return organization


@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's organization.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Organization details

    Raises:
        HTTPException: If organization not found
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcının organizasyonu yok"
        )

    organization = await organization_crud.get(db, id=current_user.organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    return organization


@router.get("/me/members", response_model=OrganizationMembersResponse)
async def get_organization_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all members of current user's organization, including pending invitations.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of organization members and pending invitations

    Raises:
        HTTPException: If user doesn't have organization
    """
    from app.services.email import ROLE_DISPLAY_NAMES

    # Check if user has organization
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcının organizasyonu yok"
        )

    # Get organization
    organization = await organization_crud.get(db, id=current_user.organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    # Get all members in the organization from organization_members table
    from app.crud import organization_member_crud
    from app.models import OrganizationMember

    stmt = (
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == current_user.organization_id)
        .options(selectinload(OrganizationMember.user))
    )
    result = await db.execute(stmt)
    memberships = result.scalars().all()

    # Build member list with organization-specific roles
    members = []
    for membership in memberships:
        user = membership.user

        # Role comes from organization_members table
        role_display = ROLE_DISPLAY_NAMES.get(membership.role, membership.role.title())

        members.append(OrganizationMemberResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role=membership.role,
            role_display_name=role_display,
            is_owner=str(user.id) == str(organization.owner_id),
            is_verified=user.is_verified,
            joined_at=membership.joined_at  # Use membership join date, not user creation date
        ))

    # Get pending invitations (only those still within their validity window;
    # status flips to EXPIRED lazily — expired-but-still-PENDING rows are
    # filtered out here so the UI never sees them).
    stmt = (
        select(Invitation)
        .where(
            Invitation.organization_id == current_user.organization_id,
            Invitation.status == InvitationStatus.PENDING,
            Invitation.expires_at > datetime.utcnow(),
        )
    )
    result = await db.execute(stmt)
    pending_invites = result.scalars().all()

    # Build pending invitations list
    pending_invitations = []
    for invite in pending_invites:
        # Get inviter info
        inviter = await user_crud.get(db, id=invite.invited_by_user_id)
        inviter_name = f"{inviter.first_name} {inviter.last_name}".strip() if inviter else "Unknown"

        role_display = ROLE_DISPLAY_NAMES.get(invite.role, invite.role.title())

        pending_invitations.append(PendingInvitationResponse(
            id=invite.id,
            email=invite.email,
            role=invite.role,
            role_display_name=role_display,
            invited_by_name=inviter_name,
            invited_by_email=inviter.email if inviter else "",
            expires_at=invite.expires_at,
            created_at=invite.created_at
        ))

    return OrganizationMembersResponse(
        members=members,
        pending_invitations=pending_invitations,
        total_members=len(members),
        total_pending=len(pending_invitations)
    )


@router.get("/me/storage")
async def get_my_organization_storage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Aktif organizasyonun toplam depolama kapasitesini (GB) döner.

    total_storage_gb = seat_count * storage_gb_per_user. Plan değerleri
    henüz set edilmediyse (free trial vb.) total_storage_gb null döner.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcının organizasyonu yok",
        )

    organization = await organization_crud.get(db, id=current_user.organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı",
        )

    if organization.seat_count is None or organization.storage_gb_per_user is None:
        total_storage_gb = None
    else:
        total_storage_gb = float(organization.storage_gb_per_user) * organization.seat_count

    return {"total_storage_gb": total_storage_gb}


@router.get("/me/stats", response_model=OrganizationWithStats)
async def get_my_organization_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
):
    """
    Get current user's organization with statistics (admin only).

    Args:
        db: Database session
        current_user: Current admin user

    Returns:
        Organization with stats

    Raises:
        HTTPException: If organization not found or not admin
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcının organizasyonu yok"
        )

    organization = await organization_crud.get(db, id=current_user.organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    # Get stats
    stats = await organization_crud.get_organization_stats(db, organization_id=organization.id)

    return OrganizationWithStats(
        **organization.__dict__,
        total_members=stats["total_members"],
        total_queries=stats["total_queries"],
        total_documents=stats["total_documents"]
    )


@router.get("/me/members", response_model=List[UserResponse])
async def get_my_organization_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all members of current user's organization.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of organization members

    Raises:
        HTTPException: If organization not found
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcının organizasyonu yok"
        )

    members = await organization_crud.get_members(db, organization_id=current_user.organization_id)
    return members


@router.post("/me/invite", response_model=List[InvitationResponse], status_code=status.HTTP_201_CREATED)
async def invite_users_to_organization(
    invite_in: InvitationBatchCreate,
    db: AsyncSession = Depends(get_db),
    _: JWTPayload = Depends(require_permission("organization", "invite")),
    current_user: User = Depends(get_current_active_user),
):
    """
    Invite users to current user's organization.

    Requires the `organization:invite` permission. Maximum 10 emails per batch.
    """
    # Check if user has an organization
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcının organizasyonu yok"
        )

    organization = await organization_crud.get(db, id=current_user.organization_id)

    # Seat enforcement — only paid plans set a seat_count. Free trial orgs
    # implicitly allow Solo (1 seat) and reject any invite; once Subscription
    # activates the cap will be the seat count purchased.
    if organization.seat_count is not None:
        # Existing memberships already account for active users
        current_member_count = await organization_crud.get_member_count(
            db, organization_id=current_user.organization_id
        )
        # Pending (non-expired) invitations also occupy a future seat
        pending_invites = await invitation_crud.list_pending_for_organization(
            db, organization_id=current_user.organization_id
        ) if hasattr(invitation_crud, "list_pending_for_organization") else []
        pending_count = sum(1 for inv in pending_invites if not inv.is_expired)
        new_invites = len(invite_in.emails)
        if current_member_count + pending_count + new_invites > organization.seat_count:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Plan koltuk limitine ulaştınız: "
                    f"{current_member_count + pending_count}/{organization.seat_count}. "
                    f"Daha fazla kullanıcı eklemek için planınızı yükseltin."
                ),
            )

    # Validate role (cannot invite as owner)
    if invite_in.role.lower() == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner rolüne davet gönderilemez. Bir organizasyonun sadece 1 sahibi olabilir."
        )

    # Check all emails exist in user table
    not_found_emails = []
    for email in invite_in.emails:
        existing_user = await user_crud.get_by_email(db, email=email)
        if not existing_user:
            not_found_emails.append(email)

    if not_found_emails:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sistemde böyle bir kullanıcı bulunmamaktadır."
        )

    # Pre-flight: classify each email against existing invitations so we either
    # fail fast on a true conflict or lazily flip stale PENDING rows to EXPIRED
    # before re-inviting.
    conflict_emails: List[str] = []
    expired_to_mark: List[Invitation] = []
    for email in invite_in.emails:
        existing_invitation = await invitation_crud.get_by_email_and_org(
            db,
            email=email,
            organization_id=current_user.organization_id,
        )
        if existing_invitation is None:
            continue
        if existing_invitation.is_expired:
            expired_to_mark.append(existing_invitation)
        else:
            conflict_emails.append(email)

    if conflict_emails:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Bu e-posta adres(ler)ine zaten aktif bir davet gönderilmiş: "
                f"{', '.join(conflict_emails)}"
            ),
        )

    # Flip stale PENDING rows to EXPIRED so the re-invite below is unblocked.
    for stale in expired_to_mark:
        await invitation_crud.mark_expired(db, invitation=stale)

    # Create invitations
    created_invitations = []
    for email in invite_in.emails:
        invitation = await invitation_crud.create_with_token(
            db,
            email=email,
            organization_id=current_user.organization_id,
            invited_by_user_id=current_user.id,
            role=invite_in.role,
            expires_in_days=settings.INVITATION_EXPIRE_DAYS,
        )

        created_invitations.append(invitation)

        # Send invitation email
        try:
            from app.services import send_invitation_email

            # Get inviter's full name
            inviter_name = f"{current_user.first_name} {current_user.last_name}".strip()
            if not inviter_name:
                inviter_name = current_user.email.split('@')[0]  # Fallback to email username

            # Format expires_at for email display
            expires_at_str = invitation.expires_at.strftime("%d.%m.%Y %H:%M")

            # Send email
            email_sent = await send_invitation_email(
                email=email,
                inviter_name=inviter_name,
                organization_name=organization.name,
                organization_type=organization.organization_type or "law_firm",
                role=invite_in.role,
                invitation_token=str(invitation.token),
                expires_at=expires_at_str,
                expires_in_days=settings.INVITATION_EXPIRE_DAYS,
            )

            if email_sent:
                print(f"✅ Invitation email sent to {email} as {invite_in.role}")
            else:
                print(f"⚠️  Invitation created but email failed to send to {email}")

        except Exception as e:
            # Don't fail the invitation creation if email fails
            print(f"⚠️  Invitation created but email error for {email}: {str(e)}")

    return created_invitations


@router.post("/me/invitations/{invitation_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_invitation(
    invitation_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: JWTPayload = Depends(require_permission("organization", "invite")),
    current_user: User = Depends(get_current_active_user),
):
    """
    Revoke a pending invitation in the caller's active organization.

    Scope: invitation must belong to current_user.organization_id and still be
    PENDING. Already-accepted, already-revoked, or expired invitations are
    rejected.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aktif bir organizasyonunuz yok",
        )

    invitation = await invitation_crud.get(db, id=invitation_id)
    if not invitation or invitation.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Davet bulunamadı",
        )

    if invitation.status != InvitationStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sadece bekleyen davetler geri alınabilir",
        )

    if invitation.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Davet zaten süresi dolmuş",
        )

    await invitation_crud.mark_revoked(db, invitation=invitation)

    return {
        "message": "Davet geri alındı",
        "invitation_id": str(invitation.id),
        "email": invitation.email,
    }


@router.patch("/me/members/{email}/role", response_model=OrganizationMemberResponse)
async def change_member_role(
    email: str,
    body: ChangeMemberRoleRequest,
    db: AsyncSession = Depends(get_db),
    _: JWTPayload = Depends(require_permission("organization", "change-member-role")),
    current_user: User = Depends(get_current_active_user),
):
    """
    Change a member's role inside the caller's active organization.

    Scope: operates on current_user.organization_id. Target is identified by
    email. Only roles marked ui_roles=true can be assigned; owner role is
    protected both as source and as target.
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aktif bir organizasyonunuz yok",
        )

    target = await user_crud.get_by_email(db, email=email)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı",
        )

    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kendi rolünüzü değiştiremezsiniz",
        )

    membership = await organization_member_crud.get_membership(
        db, user_id=target.id, organization_id=current_user.organization_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu kullanıcı organizasyonunuzda değil",
        )

    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organizasyon sahibinin rolü değiştirilemez",
        )

    new_role_name = body.role
    if new_role_name.lower() == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner rolü atanamaz",
        )

    new_role = await role_crud.get_by_name(db, name=new_role_name)
    if not new_role or not new_role.ui_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Geçersiz rol",
        )

    # Replace any existing role assignments for target in this org with the
    # new single role. All updates share one commit at the end.
    await db.execute(
        user_roles_table.delete().where(
            user_roles_table.c.user_id == target.id,
            user_roles_table.c.organization_id == current_user.organization_id,
        )
    )
    await user_crud.add_role(
        db,
        user=target,
        role=new_role,
        organization_id=current_user.organization_id,
    )
    await organization_member_crud.update_role(
        db,
        user_id=target.id,
        organization_id=current_user.organization_id,
        new_role=new_role_name,
        commit=False,
    )
    await db.commit()
    await db.refresh(membership)

    organization = await organization_crud.get(db, id=current_user.organization_id)

    return OrganizationMemberResponse(
        id=target.id,
        first_name=target.first_name,
        last_name=target.last_name,
        email=target.email,
        role=membership.role,
        role_display_name=ROLE_DISPLAY_NAMES.get(membership.role, membership.role.title()),
        is_owner=str(target.id) == str(organization.owner_id),
        is_verified=target.is_verified,
        joined_at=membership.joined_at,
    )


@router.delete("/me/members/{user_id}")
async def remove_member_from_organization(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: JWTPayload = Depends(require_permission("organization", "remove-member")),
    current_user: User = Depends(get_current_active_user),
):
    """
    Remove a member from current user's active organization.

    Authorization is gated by the `organization:remove-member` permission
    (held by owner and org-admin). Invariants enforced regardless of permission:
      - Owner cannot be removed.
      - Caller cannot remove themselves (use leave-organization for that).

    The removal is atomic and cleans up:
      - user_roles entries scoped to this organization
      - the organization_members row
      - users.organization_id (re-pointed to an org the user owns, or NULL)
      - all refresh tokens for the removed user (forces re-login)
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcının organizasyonu yok",
        )

    organization_id = current_user.organization_id

    if str(user_id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kendinizi organizasyondan çıkaramazsınız",
        )

    membership = await organization_member_crud.get_membership(
        db, user_id=user_id, organization_id=organization_id
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bu organizasyonda bulunamadı",
        )

    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organizasyon sahibi çıkarılamaz",
        )

    # Pull just the email up front via a lightweight scalar query so we
    # don't load the User ORM instance (which would eager-load memberships
    # via selectin and trip cascade rules once we delete the membership).
    target_email = (
        await db.execute(select(User.email).where(User.id == user_id))
    ).scalar_one_or_none()
    if target_email is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı",
        )

    # 1) Drop role assignments scoped to this organization.
    await db.execute(
        user_roles_table.delete().where(
            user_roles_table.c.user_id == user_id,
            user_roles_table.c.organization_id == organization_id,
        )
    )

    # 2) Drop the membership row (no commit — caller owns the transaction).
    await organization_member_crud.remove_member(
        db,
        user_id=user_id,
        organization_id=organization_id,
        commit=False,
    )
    # autoflush is disabled on the session — flush so the pending DELETE is
    # actually sent to the DB before the SELECT below, otherwise the deleted
    # membership can come back via identity map.
    await db.flush()

    # 3) Re-point users.organization_id: the user's primary org becomes the
    # one they own (if any); otherwise NULL. Use core UPDATE statements so
    # we don't reattach ORM instances and trigger the User->memberships
    # delete-orphan cascade on the just-deleted membership.
    remaining_stmt = select(
        OrganizationMember.id,
        OrganizationMember.organization_id,
        OrganizationMember.role,
    ).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.organization_id != organization_id,
    )
    remaining = (await db.execute(remaining_stmt)).all()

    new_primary = next((row for row in remaining if row.role == "owner"), None)
    new_primary_org_id = new_primary.organization_id if new_primary else None

    # Clear is_primary for all remaining memberships, then set the chosen one.
    if remaining:
        await db.execute(
            update(OrganizationMember)
            .where(OrganizationMember.user_id == user_id)
            .values(is_primary=False)
        )
    if new_primary is not None:
        await db.execute(
            update(OrganizationMember)
            .where(OrganizationMember.id == new_primary.id)
            .values(is_primary=True)
        )

    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(organization_id=new_primary_org_id)
    )

    # 4) Revoke refresh tokens so the next access-token expiry forces logout.
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.utcnow())
    )

    await db.commit()

    return {
        "message": "Kullanıcı organizasyondan çıkarıldı",
        "user_id": str(user_id),
        "email": target_email,
    }


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get organization by ID.

    Args:
        organization_id: Organization ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Organization details

    Raises:
        HTTPException: If organization not found or access denied
    """
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    # Check if user has access to this organization
    if str(current_user.organization_id) != str(organization_id):
        # Only allow if user is admin
        user_roles = [role.name.lower() for role in current_user.roles]
        if "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu organizasyona erişim reddedildi"
            )

    return organization


@router.put("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: UUID,
    org_in: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Update organization.

    Args:
        organization_id: Organization ID
        org_in: Organization update data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated organization

    Raises:
        HTTPException: If organization not found or access denied
    """
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    # Check if user is the owner or admin
    user_roles = [role.name.lower() for role in current_user.roles]
    is_owner = str(organization.owner_id) == str(current_user.id)
    is_admin = "admin" in user_roles

    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sadece organizasyon sahibi veya admin güncelleyebilir"
        )

    # Slug change is destructive (rotates the whitelabel URL); validate as
    # strictly here as we do at create time. Skip validation when slug is
    # unchanged so PUTs that just touch name/logo don't trip on legacy
    # rows that haven't been backfilled yet.
    if org_in.slug is not None and org_in.slug != organization.slug:
        try:
            new_slug = validate_slug(org_in.slug.strip().lower())
        except SlugError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )
        existing = await organization_crud.get_by_slug(db, slug=new_slug)
        if existing and existing.id != organization.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu subdomain zaten kullanımda",
            )
        org_in.slug = new_slug

    updated_org = await organization_crud.update(db, db_obj=organization, obj_in=org_in)
    return updated_org


@router.get("/{organization_id}/muvekkiller", response_model=List[MuvekkillResponse])
async def get_organization_muvekkiller(
    organization_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get all muvekkiller for an organization.

    Raises:
        HTTPException: If organization not found or access denied
    """
    organization = await organization_crud.get(db, id=organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organizasyon bulunamadı"
        )

    # Check if user has access to this organization
    user_roles = [role.name.lower() for role in current_user.roles]
    if "superuser" not in user_roles:
        # Regular users can only view their own organization's muvekkiller
        if str(current_user.organization_id) != str(organization_id):
            if "admin" not in user_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Bu organizasyonun müvekkillerine erişim reddedildi"
                )

    muvekkiller = await muvekkil_crud.get_by_organization(
        db,
        organization_id=organization_id,
        skip=skip,
        limit=limit
    )
    return muvekkiller
