"""
Admin management endpoints.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud import user_crud, role_crud
from app.models import User
from app.schemas import (
    RoleResponse,
    RoleCreate,
    UserWithRoles,
    UserUpdate,
)
from app.api.deps import require_role

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
    _: User = Depends(require_role(["admin"]))
) -> User:
    """
    Assign role to user (admin only).

    Args:
        user_id: User ID
        role_id: Role ID
        db: Database session

    Returns:
        Updated user with roles

    Raises:
        HTTPException: If user or role not found
    """
    # Get user with roles
    user = await user_crud.get_with_roles(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get role
    role = await role_crud.get(db, id=role_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    # Check if user already has this role
    if role in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this role"
        )

    # Add role to user
    await user_crud.add_role(db, user=user, role=role)

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
    _: User = Depends(require_role(["admin"]))
) -> User:
    """
    Remove role from user (admin only).

    Args:
        user_id: User ID
        role_id: Role ID
        db: Database session

    Returns:
        Updated user with roles

    Raises:
        HTTPException: If user or role not found
    """
    # Get user with roles
    user = await user_crud.get_with_roles(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
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
    _: User = Depends(require_role(["admin"]))
) -> User:
    """
    Update user quotas (admin only).

    Args:
        user_id: User ID
        daily_query_limit: Daily query limit (None = unlimited)
        monthly_query_limit: Monthly query limit (None = unlimited)
        daily_document_limit: Daily document upload limit (None = unlimited)
        max_document_size_mb: Max document size in MB
        db: Database session

    Returns:
        Updated user

    Raises:
        HTTPException: If user not found
    """
    user = await user_crud.get(db, id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
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