"""
Admin management endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud import user_crud, role_crud, organization_crud
from app.models import User
from app.schemas import (
    RoleResponse,
    RoleCreate,
    UserWithRoles,
    UserUpdate,
    UserResponse,
)
from app.api.deps import require_role, get_current_active_user

router = APIRouter()


@router.get("/roles", response_model=List[RoleResponse])
async def get_all_roles(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(["admin"]))
) -> List:
    """
    Get all roles (admin only).

    Args:
        skip: Number of records to skip
        limit: Maximum number of records
        db: Database session

    Returns:
        List of roles
    """
    roles = await role_crud.get_multi(db, skip=skip, limit=limit)
    return roles


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_in: RoleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(["admin"]))
):
    """
    Create new role (admin only).

    Args:
        role_in: Role creation data
        db: Database session

    Returns:
        Created role
    """
    # Check if role already exists
    existing_role = await role_crud.get_by_name(db, name=role_in.name)
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists"
        )

    role = await role_crud.create(db, obj_in=role_in)
    return role


@router.post("/users/{user_id}/roles/{role_id}", response_model=UserWithRoles)
async def assign_role_to_user(
    user_id: UUID,
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
) -> User:
    """
    Assign role to user (admin only).
    Note: User must have organization assigned before role assignment.
    Each user can have only one role. All existing roles will be removed.
    Admin can only assign roles to users in their own organization.

    Args:
        user_id: User ID
        role_id: Role ID
        db: Database session
        current_admin: Current admin user

    Returns:
        Updated user with roles

    Raises:
        HTTPException: If user or role not found, user has no organization, or cross-org access
    """
    # Get user with roles
    user = await user_crud.get_with_roles(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user has organization assigned
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User must be assigned to an organization before assigning role"
        )

    # Check if admin is trying to manage user from different organization
    if str(current_admin.organization_id) != str(user.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage users in your own organization"
        )

    # Get role
    role = await role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Remove all existing roles (each user can have only one role)
    for existing_role in list(user.roles):
        await user_crud.remove_role(db, user=user, role=existing_role)

    # Reload user to get fresh state
    user = await user_crud.get_with_roles(db, id=user_id)

    # Add new role to user
    await user_crud.add_role(db, user=user, role=role)

    # Update user_roles with organization_id
    from sqlalchemy import text
    update_query = text("""
        UPDATE user_roles
        SET organization_id = :org_id
        WHERE user_id = :user_id AND role_id = :role_id
    """)
    await db.execute(
        update_query,
        {"org_id": user.organization_id, "user_id": user.id, "role_id": role.id}
    )
    await db.commit()

    # Update user quotas based on role defaults
    # Always update to match the role's default values
    update_data = {
        "daily_query_limit": role.default_daily_query_limit,
        "monthly_query_limit": role.default_monthly_query_limit,
        "daily_document_upload_limit": role.default_daily_document_limit,
        "max_document_size_mb": role.default_max_document_size_mb,
    }
    await user_crud.update(db, db_obj=user, obj_in=update_data)

    # Refresh and return user with roles
    updated_user = await user_crud.get_with_roles(db, id=user_id)
    return updated_user


@router.delete("/users/{user_id}/roles/{role_id}", response_model=UserWithRoles)
async def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
) -> User:
    """
    Remove role from user (admin only).
    Admin can only remove roles from users in their own organization.

    Args:
        user_id: User ID
        role_id: Role ID
        db: Database session
        current_admin: Current admin user

    Returns:
        Updated user with roles

    Raises:
        HTTPException: If user or role not found, or cross-org access
    """
    # Get user with roles
    user = await user_crud.get_with_roles(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if admin is trying to manage user from different organization
    if user.organization_id and str(current_admin.organization_id) != str(user.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage users in your own organization"
        )

    # Get role
    role = await role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Check if user has this role
    if role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have this role"
        )

    # Remove role from user
    await user_crud.remove_role(db, user=user, role=role)

    # Refresh and return user with roles
    updated_user = await user_crud.get_with_roles(db, id=user_id)
    return updated_user


@router.put("/users/{user_id}/quotas", response_model=UserWithRoles)
async def update_user_quotas(
    user_id: UUID,
    daily_query_limit: Optional[int] = None,
    monthly_query_limit: Optional[int] = None,
    daily_document_limit: Optional[int] = None,
    max_document_size_mb: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
) -> User:
    """
    Update user quotas (admin only).
    Admin can only update quotas for users in their own organization.

    Args:
        user_id: User ID
        daily_query_limit: Daily query limit (None = unlimited)
        monthly_query_limit: Monthly query limit (None = unlimited)
        daily_document_limit: Daily document upload limit (None = unlimited)
        max_document_size_mb: Max document size in MB
        db: Database session
        current_admin: Current admin user

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found or cross-org access
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if admin is trying to manage user from different organization
    if user.organization_id and str(current_admin.organization_id) != str(user.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage users in your own organization"
        )

    # Validate quota values
    if daily_query_limit is not None and daily_query_limit < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Daily query limit must be non-negative"
        )
    if monthly_query_limit is not None and monthly_query_limit < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monthly query limit must be non-negative"
        )
    if daily_document_limit is not None and daily_document_limit < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Daily document limit must be non-negative"
        )
    if max_document_size_mb is not None and (max_document_size_mb < 1 or max_document_size_mb > 100):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Max document size must be between 1 and 100 MB"
        )

    # Build update dict
    update_data = {}
    if daily_query_limit is not None:
        update_data["daily_query_limit"] = daily_query_limit
    if monthly_query_limit is not None:
        update_data["monthly_query_limit"] = monthly_query_limit
    if daily_document_limit is not None:
        update_data["daily_document_upload_limit"] = daily_document_limit
    if max_document_size_mb is not None:
        update_data["max_document_size_mb"] = max_document_size_mb

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No quota values provided"
        )

    # Update user
    await user_crud.update(db, db_obj=user, obj_in=update_data)

    # Return user with roles
    updated_user = await user_crud.get_with_roles(db, id=user_id)
    return updated_user


@router.post("/users/{user_id}/organization", response_model=UserWithRoles)
async def assign_user_to_organization(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
) -> User:
    """
    Assign user to admin's organization (admin only).
    Automatically assigns user to the admin's organization.

    Args:
        user_id: User ID
        db: Database session
        current_admin: Current admin user

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found, user already has org, or admin has no organization
    """
    # Check if admin has organization
    if not current_admin.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user must have an organization assigned"
        )

    # Get user
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user already has organization
    if user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already belongs to an organization. Remove first before reassigning."
        )

    # Assign admin's organization to user
    user.organization_id = current_admin.organization_id
    await db.commit()
    await db.refresh(user)

    # Update user_roles table with organization_id if user has any roles
    from sqlalchemy import text
    update_query = text("""
        UPDATE user_roles
        SET organization_id = :org_id
        WHERE user_id = :user_id
    """)
    await db.execute(
        update_query,
        {"org_id": current_admin.organization_id, "user_id": user_id}
    )
    await db.commit()

    # Return user with roles
    updated_user = await user_crud.get_with_roles(db, id=user_id)
    return updated_user


@router.delete("/users/{user_id}/organization", response_model=UserWithRoles)
async def remove_user_from_organization(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
) -> User:
    """
    Remove user from organization (admin only).
    Also removes all roles from user.
    Admin can only remove users from their own organization.

    Args:
        user_id: User ID
        db: Database session
        current_admin: Current admin user

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found, user has no org, or admin trying to remove from different org
    """
    # Get user with roles
    user = await user_crud.get_with_roles(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user has organization
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to any organization"
        )

    # Check if admin is trying to remove from their own organization
    if str(current_admin.organization_id) != str(user.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only remove users from your own organization"
        )

    # Remove all roles first
    for role in list(user.roles):
        await user_crud.remove_role(db, user=user, role=role)

    # Remove organization
    user.organization_id = None
    await db.commit()
    await db.refresh(user)

    # Return user with roles
    updated_user = await user_crud.get_with_roles(db, id=user_id)
    return updated_user


@router.get("/users/pending", response_model=List[UserResponse])
async def get_pending_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(["admin"]))
) -> List[User]:
    """
    Get all users pending organization assignment (admin only).

    Args:
        db: Database session

    Returns:
        List of users without organization
    """
    # Get all users where organization_id is NULL
    from sqlalchemy import select
    from app.models import User as UserModel

    stmt = select(UserModel).where(UserModel.organization_id == None)
    result = await db.execute(stmt)
    pending_users = list(result.scalars().all())

    return pending_users


@router.patch("/users/{user_id}/status", response_model=UserWithRoles)
async def update_user_status(
    user_id: UUID,
    is_active: bool,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(["admin"]))
) -> User:
    """
    Activate or deactivate user (admin only).
    Admin can only manage users in their own organization.

    Args:
        user_id: User ID
        is_active: Active status (true/false)
        db: Database session
        current_admin: Current admin user

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found or cross-org access
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if admin is trying to manage user from different organization
    if user.organization_id and str(current_admin.organization_id) != str(user.organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage users in your own organization"
        )

    # Update user status
    await user_crud.update(db, db_obj=user, obj_in={"is_active": is_active})

    # Return user with roles
    updated_user = await user_crud.get_with_roles(db, id=user_id)
    return updated_user