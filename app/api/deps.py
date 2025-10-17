"""
FastAPI dependencies for authentication and authorization.
"""
from typing import List, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import jwt_handler
from app.crud import user_crud
from app.models import User

# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get current user from JWT token.

    Args:
        db: Database session
        credentials: HTTP Bearer credentials

    Returns:
        Current user instance

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    try:
        payload = jwt_handler.decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Kimlik doğrulama başarısız"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama başarısız"
        )

    user = await user_crud.get_with_roles(db, id=UUID(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı"
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
    Dependency to check if user has required permission.

    Args:
        resource: Resource name (e.g., 'research', 'documents')
        action: Action name (e.g., 'query', 'upload')

    Returns:
        Dependency function

    Usage:
        @app.post("/research/query")
        async def query(user: User = Depends(require_permission("research", "query"))):
            ...
    """
    async def permission_checker(
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        user_roles = [role.name for role in current_user.roles]

        # Superuser has all permissions
        if "superuser" in user_roles:
            return current_user

        # Admin has all permissions
        if "admin" in user_roles:
            return current_user

        # Check if user has the required permission through their roles
        for role in current_user.roles:
            for permission in role.permissions:
                # Check for exact match
                if permission.resource == resource and permission.action == action:
                    return current_user

                # Check for wildcard permissions
                # *:* = full access to everything
                if permission.resource == "*" and permission.action == "*":
                    return current_user

                # resource:* = full access to specific resource
                if permission.resource == resource and permission.action == "*":
                    return current_user

                # *:action = specific action on all resources
                if permission.resource == "*" and permission.action == action:
                    return current_user

        # Collect user's permissions for error message
        user_permissions = []
        for role in current_user.roles:
            for perm in role.permissions:
                user_permissions.append({
                    'resource': perm.resource,
                    'action': perm.action
                })

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"İzin reddedildi: {resource}:{action}. Mevcut izinler: {user_permissions}"
        )

    return permission_checker