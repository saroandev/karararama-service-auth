"""
User management endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud import user_crud
from app.models import User
from app.schemas import UserResponse, UserUpdate, UserWithRoles, UserDeleteResponse
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
                detail="Email already registered"
            )

    updated_user = await user_crud.update(db, db_obj=current_user, obj_in=user_update)
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
            detail="User not found"
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
            detail="User not found"
        )

    # Delete user
    deleted_user = await user_crud.delete(db, id=user_id)

    # Return custom response
    return UserDeleteResponse(
        id=user.id,
        email=user.email,
        message="User deleted successfully"
    )