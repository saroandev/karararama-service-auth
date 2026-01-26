"""
Organization management endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.crud import organization_crud, user_crud, role_crud, invitation_crud
from app.models import User, Organization, Invitation, InvitationStatus
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
)
from app.api.deps import get_current_active_user, require_role

router = APIRouter()


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    org_in: OrganizationCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new organization (PUBLIC endpoint - no auth required).

    User is found by email. User becomes the owner and their role is upgraded from guest to owner.
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
            detail="Kullanıcı zaten bir organizasyona sahip. Bir kullanıcı sadece 1 organizasyon oluşturabilir."
        )

    # Create organization directly (not using CRUD to avoid schema issues)
    organization = Organization(
        name=org_in.name,
        owner_id=user.id,
        organization_type=org_in.organization_type,
        organization_size=org_in.organization_size
    )
    db.add(organization)
    await db.commit()
    await db.refresh(organization)

    # Update user's organization_id
    user.organization_id = organization.id
    db.add(user)
    await db.commit()

    # Upgrade user role from guest to owner
    # Get roles with relationships loaded
    stmt = select(User).where(User.id == user.id).options(selectinload(User.roles))
    result = await db.execute(stmt)
    user_with_roles = result.scalar_one()

    # Get owner role
    owner_role = await role_crud.get_by_name(db, name="owner")
    if not owner_role:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Owner role bulunamadı. Lütfen database seed işlemini çalıştırın."
        )

    # Remove guest role if exists
    guest_roles = [role for role in user_with_roles.roles if role.name.lower() == "guest"]
    for guest_role in guest_roles:
        await user_crud.remove_role(db, user=user_with_roles, role=guest_role)

    # Add owner role
    await user_crud.add_role(db, user=user_with_roles, role=owner_role)

    print(f"✅ Organization created:")
    print(f"   Name: {organization.name}")
    print(f"   Owner: {user.email}")
    print(f"   Type: {org_in.organization_type}")
    print(f"   Size: {org_in.organization_size}")

    # Refresh organization to return
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

    # Get all users in the organization
    stmt = select(User).where(User.organization_id == current_user.organization_id)
    result = await db.execute(stmt)
    org_users = result.scalars().all()

    # Build member list with organization-specific roles
    members = []
    for user in org_users:
        # Get user's roles for this organization
        # Note: user_roles table has organization_id column
        stmt = (
            select(User)
            .where(User.id == user.id)
            .options(selectinload(User.roles))
        )
        result = await db.execute(stmt)
        user_with_roles = result.scalar_one()

        # For now, get the primary role (first role in the list)
        # TODO: Filter roles by organization_id when role assignment is org-specific
        primary_role = user_with_roles.roles[0].name if user_with_roles.roles else "guest"
        role_display = ROLE_DISPLAY_NAMES.get(primary_role, primary_role.title())

        members.append(OrganizationMemberResponse(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role=primary_role,
            role_display_name=role_display,
            is_owner=str(user.id) == str(organization.owner_id),
            is_verified=user.is_verified,
            joined_at=user.created_at
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
    current_user: User = Depends(get_current_active_user)
):
    """
    Invite users to current user's organization.

    Only organization owner or admin can invite users.
    Maximum 10 emails per batch.

    Args:
        invite_in: Batch invitation data (emails list, role)
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of created invitations

    Raises:
        HTTPException: If user doesn't have organization, not authorized, or email already invited
    """
    # Check if user has an organization
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcının organizasyonu yok"
        )

    # Check if user is owner or admin
    user_roles = [role.name.lower() for role in current_user.roles]
    organization = await organization_crud.get(db, id=current_user.organization_id)

    is_owner = str(organization.owner_id) == str(current_user.id)
    is_admin = "admin" in user_roles

    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sadece organizasyon sahibi veya admin kullanıcı davet edebilir"
        )

    # Validate role (cannot invite as owner)
    if invite_in.role.lower() == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner rolüne davet gönderilemez. Bir organizasyonun sadece 1 sahibi olabilir."
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
