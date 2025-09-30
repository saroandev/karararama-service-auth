"""
Authentication endpoints: login, register, refresh token.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import jwt_handler
from app.crud import user_crud
from app.models import User
from app.schemas import (
    LoginRequest,
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