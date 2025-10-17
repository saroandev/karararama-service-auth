"""
Authentication endpoints: login, register, refresh token.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import jwt_handler
from app.core.permissions import get_data_access_for_user, get_primary_role, calculate_remaining_credits
from app.crud import user_crud, refresh_token_crud, usage_crud, organization_crud
from app.models import User
from app.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    OrganizationCreate,
)
from app.api.deps import get_current_active_user

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Register a new user.

    Creates a new user without organization or role assignment.
    Admin must assign organization and role before user can login.

    Args:
        user_in: User registration data (full_name, email, password, password_confirm).
        db: Database session

    Returns:
        Created user (pending organization and role assignment)

    Raises:
        HTTPException: If email already exists or passwords don't match
    """
    # Check if passwords match
    if not user_in.validate_passwords():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )

    # Check if user already exists
    existing_user = await user_crud.get_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Split full_name into first_name and last_name
    first_name, last_name = user_in.get_first_last_name()

    # Hash password
    from app.core.security import password_handler
    hashed_password = password_handler.hash_password(user_in.password)

    # Create user directly
    from app.models import User
    db_obj = User(
        email=user_in.email,
        first_name=first_name,
        last_name=last_name,
        password_hash=hashed_password
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)

    # Assign default 'guest' role
    from app.models import Role
    from sqlalchemy import select
    result = await db.execute(
        select(Role).where(Role.name == "guest")
    )
    guest_role = result.scalar_one_or_none()

    if guest_role:
        # Reload user with roles relationship
        from sqlalchemy.orm import selectinload
        result = await db.execute(
            select(User)
            .where(User.id == db_obj.id)
            .options(selectinload(User.roles))
        )
        user_with_roles = result.scalar_one()
        user_with_roles.roles.append(guest_role)
        await db.commit()

    # Return user without roles loaded (for response serialization)
    await db.refresh(db_obj)
    return db_obj


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Login with email and password.

    Args:
        login_data: Login credentials
        db: Database session

    Returns:
        Access and refresh tokens

    Raises:
        HTTPException: If credentials are invalid
    """
    # Authenticate user
    user = await user_crud.authenticate(
        db,
        email=login_data.email,
        password=login_data.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Check if user has organization assigned
    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending organization assignment. Please contact administrator."
        )

    # Check if user has at least one role
    if not user.roles or len(user.roles) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is pending role assignment. Please contact administrator."
        )

    # Update last login
    await user_crud.update_last_login(db, user=user)

    # Get user roles and permissions
    roles = [role.name for role in user.roles]
    permissions = []
    for role in user.roles:
        for perm in role.permissions:
            permissions.append({
                "resource": perm.resource,
                "action": perm.action
            })

    # Get data access permissions
    data_access = get_data_access_for_user(user)

    # Get primary role
    primary_role = get_primary_role(user)

    # Calculate remaining credits
    today_usage = await usage_crud.get_user_daily_usage(db, user_id=user.id)
    remaining_credits = calculate_remaining_credits(user, today_usage)

    # Create token payload
    token_data = {
        "sub": str(user.id),
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "email": user.email,
        "role": primary_role,
        "roles": roles,
        "permissions": permissions,
        "data_access": data_access,
        "remaining_credits": remaining_credits,
        "quotas": {
            "daily_query_limit": user.daily_query_limit,
            "monthly_query_limit": user.monthly_query_limit,
            "daily_document_limit": user.daily_document_upload_limit,
        }
    }

    # Create tokens
    access_token = jwt_handler.create_access_token(token_data)
    refresh_token = jwt_handler.create_refresh_token({"sub": str(user.id)})

    # Save refresh token to database
    await refresh_token_crud.create(
        db=db,
        user_id=user.id,
        token=refresh_token,
        device_info=None  # TODO: Extract from request headers
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current user information.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user data
    """
    return current_user


@router.post("/verify")
async def verify_token(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Verify JWT token and return user information.
    This endpoint is used by other services to validate tokens.

    Args:
        current_user: Current authenticated user (from JWT)

    Returns:
        Token validation result with user info, roles, permissions, and quotas
    """
    # Get user roles and permissions
    roles = [role.name for role in current_user.roles]
    permissions = []
    for role in current_user.roles:
        for perm in role.permissions:
            perm_dict = {
                "resource": perm.resource,
                "action": perm.action
            }
            if perm_dict not in permissions:
                permissions.append(perm_dict)

    # Get data access permissions
    data_access = get_data_access_for_user(current_user)

    # Get primary role
    primary_role = get_primary_role(current_user)

    # Calculate remaining credits
    today_usage = await usage_crud.get_user_daily_usage(db, user_id=current_user.id)
    remaining_credits = calculate_remaining_credits(current_user, today_usage)

    return {
        "valid": True,
        "user": {
            "id": str(current_user.id),
            "organization_id": str(current_user.organization_id) if current_user.organization_id else None,
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "is_active": current_user.is_active,
        },
        "role": primary_role,
        "roles": roles,
        "permissions": permissions,
        "data_access": data_access,
        "remaining_credits": remaining_credits,
        "quotas": {
            "daily_query_limit": current_user.daily_query_limit,
            "monthly_query_limit": current_user.monthly_query_limit,
            "daily_document_limit": current_user.daily_document_upload_limit,
            "max_document_size_mb": current_user.max_document_size_mb,
        },
        "usage": {
            "total_queries_used": current_user.total_queries_used,
            "total_documents_uploaded": current_user.total_documents_uploaded,
        }
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    """
    Refresh access token using refresh token.

    Args:
        refresh_data: Refresh token request
        db: Database session

    Returns:
        New access and refresh tokens

    Raises:
        HTTPException: If refresh token is invalid or expired
    """
    # Verify refresh token from database
    db_token = await refresh_token_crud.get_by_token(db, refresh_data.refresh_token)

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    if not db_token.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or revoked"
        )

    # Verify JWT token
    try:
        payload = jwt_handler.decode_token(refresh_data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    # Get user with roles and permissions
    user = await user_crud.get(db, id=user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Get user roles and permissions
    roles = [role.name for role in user.roles]
    permissions = []
    for role in user.roles:
        for perm in role.permissions:
            permissions.append({
                "resource": perm.resource,
                "action": perm.action
            })

    # Get data access permissions
    data_access = get_data_access_for_user(user)

    # Get primary role
    primary_role = get_primary_role(user)

    # Calculate remaining credits
    today_usage = await usage_crud.get_user_daily_usage(db, user_id=user.id)
    remaining_credits = calculate_remaining_credits(user, today_usage)

    # Create new token payload
    token_data = {
        "sub": str(user.id),
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "email": user.email,
        "role": primary_role,
        "roles": roles,
        "permissions": permissions,
        "data_access": data_access,
        "remaining_credits": remaining_credits,
        "quotas": {
            "daily_query_limit": user.daily_query_limit,
            "monthly_query_limit": user.monthly_query_limit,
            "daily_document_limit": user.daily_document_upload_limit,
        }
    }

    # Create new tokens
    new_access_token = jwt_handler.create_access_token(token_data)
    new_refresh_token = jwt_handler.create_refresh_token({"sub": str(user.id)})

    # Revoke old refresh token
    await refresh_token_crud.revoke(db, refresh_data.refresh_token)

    # Save new refresh token to database
    await refresh_token_crud.create(
        db=db,
        user_id=user.id,
        token=new_refresh_token,
        device_info=None  # TODO: Extract from request headers
    )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.post("/logout")
async def logout(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout user by revoking refresh token.

    Args:
        refresh_data: Refresh token to revoke
        db: Database session
        current_user: Current authenticated user

    Returns:
        Success message
    """
    # Revoke the refresh token
    revoked = await refresh_token_crud.revoke(db, refresh_data.refresh_token)

    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Refresh token not found"
        )

    return {"message": "Successfully logged out"}