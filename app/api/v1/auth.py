"""
Authentication endpoints: login, register, refresh token.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import jwt_handler
from app.crud import user_crud, refresh_token_crud
from app.models import User
from app.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
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

    Args:
        user_in: User registration data
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException: If email already exists
    """
    # Check if user already exists
    existing_user = await user_crud.get_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create new user
    user = await user_crud.create(db, obj_in=user_in)
    return user


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

    # Create token payload
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "roles": roles,
        "permissions": permissions,
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

    return {
        "valid": True,
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "is_active": current_user.is_active,
        },
        "roles": roles,
        "permissions": permissions,
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

    # Create new token payload
    token_data = {
        "sub": str(user.id),
        "email": user.email,
        "roles": roles,
        "permissions": permissions,
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