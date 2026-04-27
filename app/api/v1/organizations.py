"""
Organization management endpoints.
"""
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.crud import organization_crud, user_crud, role_crud, invitation_crud, muvekkil_crud, organization_member_crud
from app.models import OrganizationMember, User, Organization, Invitation, InvitationStatus, RefreshToken
from app.models.user import user_roles as user_roles_table
from app.schemas import (
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
from app.core.security import JWTPayload
from app.services.email import ROLE_DISPLAY_NAMES

router = APIRouter()


class ChangeMemberRoleRequest(BaseModel):
    """Payload for PATCH /organizations/me/members/{email}/role."""
    role: str


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

    # Create organization
    organization = Organization(
        name=org_in.name,
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

    # Get pending invitations
    stmt = (
        select(Invitation)
        .where(
            Invitation.organization_id == current_user.organization_id,
            Invitation.status == InvitationStatus.PENDING
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

    # Create invitations
    created_invitations = []
    for email in invite_in.emails:
        # Check if email already has pending invitation
        existing_invitation = await invitation_crud.get_by_email_and_org(
            db,
            email=email,
            organization_id=current_user.organization_id
        )

        if existing_invitation:
            # Skip if already pending, otherwise create new one
            if existing_invitation.status == InvitationStatus.PENDING:
                print(f"⚠️  Email {email} zaten bekleyen bir davete sahip, atlanıyor...")
                continue

        # Create invitation
        invitation = await invitation_crud.create_with_token(
            db,
            email=email,
            organization_id=current_user.organization_id,
            invited_by_user_id=current_user.id,
            role=invite_in.role,
            expires_in_days=7
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
                expires_in_days=7
            )

            if email_sent:
                print(f"✅ Invitation email sent to {email} as {invite_in.role}")
            else:
                print(f"⚠️  Invitation created but email failed to send to {email}")

        except Exception as e:
            # Don't fail the invitation creation if email fails
            print(f"⚠️  Invitation created but email error for {email}: {str(e)}")

    if not created_invitations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tüm emailler zaten davet edilmiş durumda"
        )

    return created_invitations


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

    target = await user_crud.get(db, id=user_id)
    if not target:
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
    # actually sent to the DB before the next SELECT, otherwise the deleted
    # membership comes back via identity map and the subsequent db.add(m)
    # re-attaches it, silently undoing the delete.
    await db.flush()

    # 3) Re-point users.organization_id: the user's primary org becomes the
    # one they own (if any); otherwise NULL. Mirror is_primary on memberships.
    remaining_stmt = select(OrganizationMember).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.organization_id != organization_id,
    )
    remaining = (await db.execute(remaining_stmt)).scalars().all()

    new_primary = next((m for m in remaining if m.role == "owner"), None)
    for m in remaining:
        m.is_primary = (new_primary is not None and m.id == new_primary.id)
        db.add(m)

    target.organization_id = new_primary.organization_id if new_primary else None
    db.add(target)

    # 4) Revoke refresh tokens so the next access-token expiry forces logout.
    refresh_stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )
    refresh_tokens = (await db.execute(refresh_stmt)).scalars().all()
    now = datetime.utcnow()
    for tok in refresh_tokens:
        tok.revoked_at = now
        db.add(tok)

    await db.commit()

    return {
        "message": "Kullanıcı organizasyondan çıkarıldı",
        "user_id": str(user_id),
        "email": target.email,
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
