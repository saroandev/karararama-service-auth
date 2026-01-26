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
from app.crud import user_crud, refresh_token_crud, usage_crud, organization_crud, blacklisted_token_crud, invitation_crud, role_crud
from app.crud.activity_watch_token import activity_watch_token_crud
from app.models import User
from app.models.invitation import InvitationStatus
from app.schemas import (
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
    OrganizationCreate,
    SendVerificationEmailRequest,
    SendVerificationEmailResponse,
    VerifyEmailCodeRequest,
    VerifyEmailCodeResponse,
    ResendVerificationEmailRequest,
    ResendVerificationEmailResponse,
)
from app.schemas.activity_watch import (
    ActivityWatchLoginRequest,
    ActivityWatchTokenResponse,
    ActivityWatchVerifyResponse,
    ErrorResponse
)
from app.api.deps import get_current_active_user, security
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter()


def generate_verification_code() -> str:
    """Generate a 6-digit verification code."""
    return ''.join(random.choices(string.digits, k=6))


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    db: AsyncSession = Depends(get_db),
    invitation_token: str = None
) -> User:
    """
    Register a new user.

    Creates a new user with default 'guest' role.
    Guest users can login immediately with limited permissions.

    If invitation_token is provided:
        - Validates the invitation
        - Assigns organization and role from invitation
        - Marks invitation as accepted

    Args:
        user_in: User registration data (first_name, last_name, email, password, password_confirm).
        db: Database session
        invitation_token: Optional invitation token (query parameter)

    Returns:
        Created user with assigned role and organization

    Raises:
        HTTPException: If email already exists, passwords don't match, or invitation invalid
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

    # Validate invitation if token provided
    invitation = None
    if invitation_token:
        invitation = await invitation_crud.get_by_token(db, token=invitation_token)

        if not invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geçersiz davet tokeni"
            )

        # Check if invitation is valid
        if not invitation.is_valid:
            if invitation.status == InvitationStatus.ACCEPTED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bu davet zaten kabul edilmiş"
                )
            elif invitation.status == InvitationStatus.EXPIRED or invitation.is_expired:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bu davetin süresi dolmuş"
                )
            elif invitation.status == InvitationStatus.REVOKED:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bu davet iptal edilmiş"
                )

        # Verify email matches invitation
        if invitation.email.lower() != user_in.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-posta adresi davet ile eşleşmiyor"
            )

    # Create user using CRUD (handles hashing, consent timestamps, and default values)
    user = await user_crud.create(db, obj_in=user_in)

    # Process invitation if exists
    if invitation:
        # Assign organization from invitation
        user.organization_id = invitation.organization_id
        db.add(user)
        await db.commit()

        # Get role from invitation
        invited_role = await role_crud.get_by_name(db, name=invitation.role)
        if invited_role:
            await user_crud.add_role(db, user=user, role=invited_role)

        # Mark invitation as accepted
        await invitation_crud.mark_accepted(db, invitation=invitation)

        print(f"✅ Kullanıcı davet ile kaydoldu:")
        print(f"   Email: {user.email}")
        print(f"   Organization ID: {invitation.organization_id}")
        print(f"   Role: {invitation.role}")
    else:
        # Assign default 'guest' role
        guest_role = await role_crud.get_by_name(db, name="guest")

        if guest_role:
            await user_crud.add_role(db, user=user, role=guest_role)

    # Reload user with all relationships
    user = await user_crud.get_with_roles(db, id=user.id)

    # Send verification email automatically
    try:
        from app.crud import email_verification
        from app.services import send_verification_email

        # Create verification code
        verification = await email_verification.create_verification_code(
            db, user_id=user.id, email=user.email
        )

        # Send email
        await send_verification_email(user.email, verification.code)

        print(f"✅ Verification email sent to {user.email}")
        print(f"   Code: {verification.code} (expires in 30 minutes)")

    except Exception as e:
        # Don't fail registration if email sending fails
        print(f"⚠️  Failed to send verification email: {str(e)}")
        print(f"   User registration succeeded but email not sent")

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

    # Check if user needs onboarding (no organization)
    needs_onboarding = user.organization_id is None

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        needs_onboarding=needs_onboarding
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


@router.post(
    "/activity-watch-login",
    response_model=ActivityWatchTokenResponse,
    responses={
        200: {
            "description": "Login başarılı, token döndürüldü",
            "model": ActivityWatchTokenResponse
        },
        400: {
            "description": "Geçersiz istek (email formatı hatalı veya şifre çok kısa)",
            "model": ErrorResponse
        },
        401: {
            "description": "Email veya şifre hatalı",
            "model": ErrorResponse
        },
        403: {
            "description": "Kullanıcı hesabı aktif değil",
            "model": ErrorResponse
        },
        500: {
            "description": "Token oluşturma hatası",
            "model": ErrorResponse
        }
    }
)
async def activity_watch_login(
    login_data: ActivityWatchLoginRequest,
    db: AsyncSession = Depends(get_db)
) -> ActivityWatchTokenResponse:
    """
    Login endpoint for Activity Watch desktop application.

    This endpoint provides a long-lived token (no expiration) for the Activity Watch
    desktop application. Each user can have only one active token at a time.
    New logins will return the existing token.

    **Error Scenarios:**
    - `400`: Email formatı hatalı veya şifre çok kısa (minimum 6 karakter)
    - `401`: Email veya şifre yanlış
    - `403`: Kullanıcı hesabı aktif değil
    - `500`: Token oluşturma sırasında beklenmeyen hata

    Args:
        login_data: Login credentials (email and password)
        db: Database session

    Returns:
        Long-lived Activity Watch token
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
    try:
        plain_token, _ = await activity_watch_token_crud.create_or_update(
            db,
            user_id=user.id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token oluşturulurken hata oluştu: {str(e)}"
        )

    return ActivityWatchTokenResponse(
        token=plain_token,
        token_type="activity_watch"
    )


@router.post(
    "/activity-watch-verify",
    response_model=ActivityWatchVerifyResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Token geçerli",
            "model": ActivityWatchVerifyResponse
        },
        401: {
            "description": "Token geçersiz veya decrypt edilemedi",
            "model": ErrorResponse
        },
        403: {
            "description": "Kullanıcı hesabı aktif değil",
            "model": ErrorResponse
        },
        404: {
            "description": "Token'a ait kullanıcı bulunamadı",
            "model": ErrorResponse
        },
        500: {
            "description": "Token doğrulama sırasında beklenmeyen hata",
            "model": ErrorResponse
        }
    }
)
async def activity_watch_verify(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> ActivityWatchVerifyResponse:
    """
    Verify Activity Watch token.

    This endpoint validates the Activity Watch token sent in the Authorization header.
    Used by the desktop application to check if the token is still valid.

    **Error Scenarios:**
    - `401`: Token geçersiz, bulunamadı veya decrypt edilemedi
    - `403`: Kullanıcı hesabı aktif değil
    - `404`: Token'a ait kullanıcı veritabanında bulunamadı
    - `500`: Token doğrulama sırasında beklenmeyen hata

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        User active status
    """
    token = credentials.credentials

    # Verify token exists in database and decrypt it
    try:
        token_record = await activity_watch_token_crud.verify_token(db, token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token decrypt edilemedi: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user
    try:
        user = await user_crud.get_with_roles(db, id=token_record.user_id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kullanıcı bilgisi alınırken hata oluştu: {str(e)}"
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Kullanıcı hesabı aktif değil"
        )

    # Update last_used_at
    try:
        await activity_watch_token_crud.update_last_used(db, token_record)
    except Exception:
        # Don't fail if last_used_at update fails, just log it
        pass

    return ActivityWatchVerifyResponse(
        is_active=user.is_active
    )


# ============================================================================
# EMAIL VERIFICATION ENDPOINTS
# ============================================================================


@router.post(
    "/send-verification-email",
    response_model=SendVerificationEmailResponse,
    status_code=status.HTTP_200_OK
)
async def send_verification_email_endpoint(
    request: SendVerificationEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send verification email with 6-digit code to user.

    This is typically called automatically after registration,
    but can also be called manually if needed.

    Args:
        request: Email address to send verification code to
        db: Database session

    Returns:
        Success response with cooldown information if applicable

    Raises:
        HTTPException: If user not found or cooldown active
    """
    from app.crud import email_verification
    from app.services import send_verification_email

    # Find user by email
    user = await user_crud.get_by_email(db, email=request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu email adresiyle kayıtlı kullanıcı bulunamadı"
        )

    # Check if user already verified
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu email adresi zaten doğrulanmış"
        )

    # Check resend cooldown (60 seconds)
    can_resend, seconds_remaining = await email_verification.check_resend_cooldown(
        db, email=request.email
    )

    if not can_resend:
        return SendVerificationEmailResponse(
            success=False,
            message=f"Lütfen {seconds_remaining} saniye bekleyin",
            cooldown_remaining=seconds_remaining
        )

    # Invalidate old codes
    await email_verification.invalidate_old_codes(db, email=request.email)

    # Create new verification code
    verification = await email_verification.create_verification_code(
        db, user_id=user.id, email=request.email
    )

    # Send email
    email_sent = await send_verification_email(request.email, verification.code)

    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email gönderilemedi. Lütfen tekrar deneyin"
        )

    return SendVerificationEmailResponse(
        success=True,
        message="Doğrulama kodu email adresinize gönderildi",
        cooldown_remaining=None
    )


@router.post(
    "/verify-email-code",
    response_model=VerifyEmailCodeResponse,
    status_code=status.HTTP_200_OK
)
async def verify_email_code_endpoint(
    request: VerifyEmailCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify email with 6-digit code.

    Args:
        request: Email and verification code
        db: Database session

    Returns:
        Success response

    Raises:
        HTTPException: If code invalid, expired, or max attempts reached
    """
    from app.crud import email_verification

    # Find user by email
    user = await user_crud.get_by_email(db, email=request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
        )

    # Check if already verified
    if user.is_verified:
        return VerifyEmailCodeResponse(
            success=True,
            message="Email adresi zaten doğrulanmış"
        )

    # Validate code
    is_valid, error_message, verification = await email_verification.validate_code(
        db, email=request.email, code=request.code
    )

    if not is_valid:
        # Increment attempts if verification record exists
        if verification:
            await email_verification.increment_attempts(db, verification=verification)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message
        )

    # Mark code as used
    await email_verification.mark_as_used(db, verification=verification)

    # Mark user as verified
    user.is_verified = True
    db.add(user)
    await db.commit()

    return VerifyEmailCodeResponse(
        success=True,
        message="Email adresiniz başarıyla doğrulandı"
    )


@router.post(
    "/resend-verification-email",
    response_model=ResendVerificationEmailResponse,
    status_code=status.HTTP_200_OK
)
async def resend_verification_email_endpoint(
    request: ResendVerificationEmailRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Resend verification email (60s cooldown).

    Args:
        request: Email address to resend verification code to
        db: Database session

    Returns:
        Success response with next resend time

    Raises:
        HTTPException: If user not found, already verified, or cooldown active
    """
    from app.crud import email_verification
    from app.services import send_verification_email
    from datetime import datetime

    # Find user by email
    user = await user_crud.get_by_email(db, email=request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
        )

    # Check if already verified
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu email adresi zaten doğrulanmış"
        )

    # Check resend cooldown (60 seconds)
    can_resend, seconds_remaining = await email_verification.check_resend_cooldown(
        db, email=request.email
    )

    if not can_resend:
        next_resend_timestamp = int(datetime.utcnow().timestamp()) + seconds_remaining
        return ResendVerificationEmailResponse(
            success=False,
            message=f"Lütfen {seconds_remaining} saniye bekleyin",
            cooldown_remaining=seconds_remaining,
            next_resend_time=next_resend_timestamp
        )

    # Invalidate old codes
    await email_verification.invalidate_old_codes(db, email=request.email)

    # Create new verification code
    verification = await email_verification.create_verification_code(
        db, user_id=user.id, email=request.email
    )

    # Send email
    email_sent = await send_verification_email(request.email, verification.code)

    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email gönderilemedi. Lütfen tekrar deneyin"
        )

    # Calculate next resend time
    from app.crud.email_verification import EMAIL_RESEND_COOLDOWN_SECONDS
    next_resend_timestamp = int(datetime.utcnow().timestamp()) + EMAIL_RESEND_COOLDOWN_SECONDS

    return ResendVerificationEmailResponse(
        success=True,
        message="Yeni doğrulama kodu gönderildi",
        cooldown_remaining=EMAIL_RESEND_COOLDOWN_SECONDS,
        next_resend_time=next_resend_timestamp
    )