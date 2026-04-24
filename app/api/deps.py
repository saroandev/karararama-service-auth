"""
FastAPI dependencies for authentication and authorization.
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import JWTPayload, jwt_handler
from app.crud import user_crud, blacklisted_token_crud
from app.crud.activity_watch_token import activity_watch_token_crud
from app.models import User

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_jwt_payload(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> JWTPayload:
    """
    Decode and validate the JWT access token, check blacklist, return a typed
    JWTPayload. Does not touch the users table — stateless authorization.

    Used as a sub-dependency by `get_current_user` and `require_permission`;
    FastAPI deduplicates so a single request decodes the token only once.
    """
    token = credentials.credentials

    is_blacklisted = await blacklisted_token_crud.is_blacklisted(db, token)
    if is_blacklisted:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token iptal edildi. Lütfen tekrar giriş yapın.",
        )

    try:
        raw_payload = jwt_handler.decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama başarısız",
        )

    payload = JWTPayload(raw_payload)
    if payload.sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama başarısız",
        )
    return payload


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    payload: JWTPayload = Depends(get_jwt_payload),
) -> User:
    """
    Get current user (ORM) from the JWT payload.

    Use this only when you actually need the full User object with its
    relationships (roles, memberships, etc). For simple permission gates
    use `require_permission(...)` instead — it avoids the DB round trip.
    """
    user = await user_crud.get_with_roles(db, id=UUID(payload.sub))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı",
        )
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user.

    Args:
        current_user: Current user from token

    Returns:
        Current active user

    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hesap aktif değil"
        )
    return current_user


def require_role(required_roles: List[str]):
    """
    Dependency to check if user has required role.

    Args:
        required_roles: List of role names required

    Returns:
        Dependency function

    Usage:
        @app.get("/admin")
        async def admin_endpoint(user: User = Depends(require_role(["admin"]))):
            ...
    """
    async def role_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        user_roles = [role.name for role in current_user.roles]

        # Superuser has access to everything
        if "superuser" in user_roles:
            return current_user

        # Admin has access to everything
        if "admin" in user_roles:
            return current_user

        # Check if user has any of the required roles
        if not any(role in user_roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Gerekli rol: {', '.join(required_roles)}"
            )

        return current_user

    return role_checker


def require_permission(resource: str, action: str):
    """
    Stateless permission gate backed by the JWT `permissions` array.

    The JWT is already scoped to the user's active organization by the token
    builder, so checking it here gives correct org-scoped authorization
    without any DB round trip. Wildcards (`resource:*`, `*:action`, `*:*`)
    are honoured.

    Returns the JWTPayload so the endpoint can use claims directly:

        @router.post("/tebligatlar/batch")
        async def batch(
            current_user: JWTPayload = Depends(require_permission("tebligat", "senkronize")),
        ):
            current_user.email, current_user.organization_id, ...

    Endpoints that also need the User ORM object can layer
    `Depends(get_current_active_user)` separately — FastAPI deduplicates the
    underlying JWT decode so it still happens once per request.
    """

    async def permission_checker(
        payload: JWTPayload = Depends(get_jwt_payload),
    ) -> JWTPayload:
        if not payload.has_permission(resource, action):
            logger.warning(
                "Permission denied: user=%s resource=%s action=%s",
                payload.email,
                resource,
                action,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem için '{resource}:{action}' yetkisi gereklidir",
            )
        return payload

    return permission_checker