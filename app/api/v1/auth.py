"""
Authentication endpoints: login, register, refresh token.
"""
from datetime import datetime, timedelta
import random
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import jwt_handler
from app.core.permissions import get_data_access_for_user, get_primary_role, calculate_remaining_credits
from app.crud import user_crud, refresh_token_crud, usage_crud, organization_crud, blacklisted_token_crud
from app.crud.activity_watch_token import activity_watch_token_crud
from app.models import User
from app.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    OrganizationCreate,
)
from app.schemas.activity_watch import ActivityWatchLoginRequest, ActivityWatchTokenResponse
from app.api.deps import get_current_active_user, security
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter()


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Register a new user.

    Creates a new user with default 'guest' role.
    Guest users can login immediately with limited permissions.
    Other roles require admin to assign organization.

    Args:
        user_in: User registration data (first_name, last_name, email, password, password_confirm).
        db: Database session

    Returns:
        Created user with guest role

    Raises:
        HTTPException: If email already exists or passwords don't match
    """
    # Check if passwords match
    if not user_in.validate_passwords():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifreler eşleşmiyor"
        )

    # Check if user already exists
    existing_user = await user_crud.get_by_email(db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu e-posta adresi zaten kayıtlı"
        )

    # Create user using CRUD (handles hashing and default values)
    user = await user_crud.create(db, obj_in=user_in)

    # Assign default 'guest' role
    from app.crud import role_crud
    guest_role = await role_crud.get_by_name(db, name="guest")

    if guest_role:
        await user_crud.add_role(db, user=user, role=guest_role)

    # Reload user with all relationships
    user = await user_crud.get_with_roles(db, id=user.id)
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
            detail="E-posta veya şifre hatalı"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hesap aktif değil"
        )

    # Check if email is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lütfen e-posta adresinizi doğrulayın"
        )

    # Check if user has at least one role
    if not user.roles or len(user.roles) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesabınız rol ataması bekliyor. Lütfen yönetici ile iletişime geçin."
        )

    # Check organization assignment (except for guest/demo users)
    role_names = [role.name.lower() for role in user.roles]
    is_guest_or_demo = "guest" in role_names or "demo" in role_names

    if not user.organization_id and not is_guest_or_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesabınız organizasyon ataması bekliyor. Lütfen yönetici ile iletişime geçin."
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
            detail="Geçersiz refresh token"
        )

    if not db_token.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token süresi dolmuş veya iptal edilmiş"
        )

    # Verify JWT token
    try:
        payload = jwt_handler.decode_token(refresh_data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Geçersiz token tipi"
            )
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz refresh token"
        )

    # Get user with roles and permissions
    user = await user_crud.get(db, id=user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı veya hesap aktif değil"
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
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout user by blacklisting access token and revoking all refresh tokens.

    Uses access token from Authorization header to:
    1. Add the access token to blacklist (prevents further use)
    2. Revoke all refresh tokens (logs out from all devices)

    Args:
        credentials: HTTP Bearer credentials (access token)
        db: Database session
        current_user: Current authenticated user (from access token)

    Returns:
        Success message with logout details
    """
    access_token = credentials.credentials

    # Decode token to get expiration time
    try:
        payload = jwt_handler.decode_token(access_token)
        expires_at = datetime.fromtimestamp(payload.get("exp"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token"
        )

    # Add access token to blacklist
    await blacklisted_token_crud.add_to_blacklist(
        db=db,
        token=access_token,
        user_id=current_user.id,
        expires_at=expires_at,
        reason="logout"
    )

    # Revoke all user's refresh tokens
    revoked_count = await refresh_token_crud.revoke_all_user_tokens(db, current_user.id)

    return {
        "message": "Başarıyla çıkış yapıldı",
        "sessions_terminated": revoked_count
    }


@router.post("/verify-email/{email}")
async def verify_email(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Mark user's email as verified.

    This endpoint is called by CRM after user verifies their email.
    CRM handles verification code generation and validation.

    Args:
        email: User's email address
        db: Database session

    Returns:
        Success message

    Raises:
        HTTPException: If user not found
    """
    # Get user by email
    user = await user_crud.get_by_email(db, email=email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
        )

    # Mark as verified
    user.is_verified = True
    await db.commit()

    return {
        "message": "E-posta başarıyla doğrulandı",
        "email": email,
        "is_verified": True
    }


@router.post("/activity-watch-login", response_model=ActivityWatchTokenResponse)
async def activity_watch_login(
    login_data: ActivityWatchLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> ActivityWatchTokenResponse:
    """
    Login endpoint for Activity Watch desktop application.

    This endpoint provides a long-lived token (no expiration) for the Activity Watch
    desktop application. Each user can have only one active token at a time.
    New logins will replace the existing token.

    Args:
        login_data: Login credentials (email and password)
        db: Database session

    Returns:
        Long-lived Activity Watch token

    Raises:
        HTTPException: If credentials are invalid or user is not active
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
            detail="Email veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcı hesabı aktif değil"
        )

    # Create or update Activity Watch token for this user
    plain_token, _ = await activity_watch_token_crud.create_or_update(
        db,
        user_id=user.id
    )

    return ActivityWatchTokenResponse(
        token=plain_token,
        token_type="activity_watch"
    )