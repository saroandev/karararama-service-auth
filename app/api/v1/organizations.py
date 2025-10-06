"""
Organization management endpoints.
"""
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud import organization_crud, user_crud
from app.models import User
from app.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationWithStats,
    UserResponse,
)
from app.api.deps import get_current_active_user

router = APIRouter()


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
            detail="User has no organization"
        )

    organization = await organization_crud.get(db, id=current_user.organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
        )

    return organization


@router.get("/me/stats", response_model=OrganizationWithStats)
async def get_my_organization_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current user's organization with statistics.

    Args:
        db: Database session
        current_user: Current authenticated user

    Returns:
        Organization with stats

    Raises:
        HTTPException: If organization not found
    """
    if not current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User has no organization"
        )

    organization = await organization_crud.get(db, id=current_user.organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found"
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
            detail="User has no organization"
        )

    members = await organization_crud.get_members(db, organization_id=current_user.organization_id)
    return members


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
            detail="Organization not found"
        )

    # Check if user has access to this organization
    if str(current_user.organization_id) != str(organization_id):
        # Only allow if user is admin
        user_roles = [role.name.lower() for role in current_user.roles]
        if "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this organization"
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
            detail="Organization not found"
        )

    # Check if user is the owner or admin
    user_roles = [role.name.lower() for role in current_user.roles]
    is_owner = str(organization.owner_id) == str(current_user.id)
    is_admin = "admin" in user_roles

    if not (is_owner or is_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization owner or admin can update"
        )

    updated_org = await organization_crud.update(db, db_obj=organization, obj_in=org_in)
    return updated_org
