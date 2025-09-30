"""
Pydantic schemas for request/response validation.
"""
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserUpdatePassword,
    UserResponse,
    UserWithRoles,
    UserDeleteResponse,
)
from app.schemas.role import (
    RoleBase,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleWithPermissions,
)
from app.schemas.permission import (
    PermissionBase,
    PermissionCreate,
    PermissionUpdate,
    PermissionResponse,
)
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    TokenPayload,
    RefreshTokenRequest,
)

__all__ = [
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserUpdatePassword",
    "UserResponse",
    "UserWithRoles",
    "UserDeleteResponse",
    # Role
    "RoleBase",
    "RoleCreate",
    "RoleUpdate",
    "RoleResponse",
    "RoleWithPermissions",
    # Permission
    "PermissionBase",
    "PermissionCreate",
    "PermissionUpdate",
    "PermissionResponse",
    # Auth
    "LoginRequest",
    "TokenResponse",
    "TokenPayload",
    "RefreshTokenRequest",
]