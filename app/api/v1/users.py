"""
User management endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash
from app.crud import user_crud, organization_member_crud
from app.models import User, Organization
from app.schemas import (
    UserResponse,
    UserUpdate,
    UserWithRoles,
    UserDeleteResponse,
    UserUpdatePassword,
    UserOrganizationsListResponse,
    UserOrganizationResponse,
    SetPrimaryOrganizationResponse
)
from app.api.deps import get_current_active_user, require_role

router = APIRouter()


@router.get("/me", response_model=UserWithRoles)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current user's information with roles.

    Args:
        current_user: Current authenticated user

    Returns:
        User data with roles
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Update current user's information.

    Args:
        user_update: Update data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated user data
    """
    # Check if email is being updated and already exists
    if user_update.email and user_update.email != current_user.email:
        existing_user = await user_crud.get_by_email(db, email=user_update.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu e-posta adresi zaten kayıtlı"
            )

    updated_user = await user_crud.update(db, db_obj=current_user, obj_in=user_update)
    return updated_user


@router.put("/me/password", response_model=UserResponse)
async def update_current_user_password(
    password_update: UserUpdatePassword,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Update current user's password.

    Args:
        password_update: Password update data (old_password, new_password, new_password_confirm)
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated user data

    Raises:
        HTTPException: If passwords don't match, old password is incorrect, new password is weak, or same as old
    """
    # Check if new passwords match
    if not password_update.passwords_match:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yeni şifreler eşleşmiyor"
        )

    # Verify old password
    if not verify_password(password_update.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Eski şifre hatalı"
        )

    # Check if new password is same as old password
    if verify_password(password_update.new_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Yeni şifre eskisinden farklı olmalı"
        )

    # Password strength is already validated by Pydantic (min_length=6)
    # Hash and update password
    new_password_hash = get_password_hash(password_update.new_password)
    updated_user = await user_crud.update(
        db,
        db_obj=current_user,
        obj_in={"password_hash": new_password_hash}
    )

    return updated_user


@router.get("", response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(["admin"]))
) -> List[User]:
    """
    Get all users (admin only).

    Args:
        skip: Number of records to skip
        limit: Maximum number of records
        db: Database session

    Returns:
        List of users
    """
    users = await user_crud.get_multi(db, skip=skip, limit=limit)
    return users


@router.get("/{user_id}", response_model=UserWithRoles)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(["admin"]))
) -> User:
    """
    Get user by ID (admin only).

    Args:
        user_id: User ID
        db: Database session

    Returns:
        User data with roles

    Raises:
        HTTPException: If user not found
    """
    user = await user_crud.get_with_roles(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
        )
    return user


@router.delete("/{user_id}", response_model=UserDeleteResponse)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(["admin"]))
) -> UserDeleteResponse:
    """
    Delete user by ID (admin only).

    Args:
        user_id: User ID
        db: Database session

    Returns:
        Deletion confirmation with user details

    Raises:
        HTTPException: If user not found
    """
    # Get user first to retrieve data before deletion
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
        )

    # Delete user
    deleted_user = await user_crud.delete(db, id=user_id)

    # Return custom response
    return UserDeleteResponse(
        id=user.id,
        email=user.email,
        message="Kullanıcı başarıyla silindi"
    )


@router.get("/me/organizations", response_model=UserOrganizationsListResponse)
async def get_user_organizations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> UserOrganizationsListResponse:
    """
    Get all organizations the current user belongs to.

    Returns list of organizations with:
    - Organization details
    - User's role in each organization
    - Whether it's their primary/active organization
    - Whether they own the organization

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of user's organizations with membership details
    """
    # Get all memberships with organization details loaded
    memberships = await organization_member_crud.get_user_memberships(
        db,
        user_id=current_user.id
    )

    # Role display names mapping
    role_names = {
        "owner": "Organizasyon Sahibi",
        "org-admin": "Organizasyon Yöneticisi",
        "managing-lawyer": "Yönetici Avukat",
        "lawyer": "Avukat",
        "trainee": "Stajyer Avukat",
        "member": "Üye",
    }

    # Build response
    organizations = []
    primary_org_id = None
    owned_org_id = None

    for membership in memberships:
        org = membership.organization

        # Check if user owns this organization
        is_owner = (org.owner_id == current_user.id)

        if is_owner:
            owned_org_id = org.id

        if membership.is_primary:
            primary_org_id = org.id

        organizations.append(
            UserOrganizationResponse(
                id=membership.id,
                organization_id=org.id,
                organization_name=org.name,
                organization_type=org.organization_type,
                organization_size=org.organization_size,
                role=membership.role,
                role_display_name=role_names.get(membership.role, membership.role),
                is_primary=membership.is_primary,
                is_owner=is_owner,
                joined_at=membership.joined_at
            )
        )

    return UserOrganizationsListResponse(
        organizations=organizations,
        primary_organization_id=primary_org_id,
        owned_organization_id=owned_org_id
    )


@router.post("/me/organizations/{organization_id}/set-primary", response_model=SetPrimaryOrganizationResponse)
async def set_primary_organization(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> SetPrimaryOrganizationResponse:
    """
    Set a different organization as the user's primary/active organization.

    The user must be a member of the organization to set it as primary.
    This will update:
    - All memberships: set is_primary=False
    - Target membership: set is_primary=True
    - User.organization_id: set to new organization

    Args:
        organization_id: ID of organization to set as primary
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message with organization details

    Raises:
        HTTPException: If user is not a member of the organization
    """
    # Verify user is member of this organization
    membership = await organization_member_crud.get_membership(
        db,
        user_id=current_user.id,
        organization_id=organization_id
    )

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu organizasyonun üyesi değilsiniz"
        )

    # Set as primary (also updates user.organization_id)
    updated_membership = await organization_member_crud.set_primary(
        db,
        user_id=current_user.id,
        organization_id=organization_id
    )

    # Get organization details
    stmt = select(Organization).where(Organization.id == organization_id)
    result = await db.execute(stmt)
    organization = result.scalar_one()

    return SetPrimaryOrganizationResponse(
        message="Aktif organizasyon başarıyla değiştirildi",
        organization_id=organization.id,
        organization_name=organization.name
    )