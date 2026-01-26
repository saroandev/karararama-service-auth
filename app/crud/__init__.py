"""
CRUD operations for database models.
"""
from app.crud.organization import CRUDOrganization, organization_crud
from app.crud.user import CRUDUser, user_crud
from app.crud.role import CRUDRole, role_crud
from app.crud.permission import CRUDPermission, permission_crud
from app.crud.usage import CRUDUsage, usage_crud
from app.crud.refresh_token import CRUDRefreshToken, refresh_token_crud
from app.crud.blacklisted_token_crud import CRUDBlacklistedToken, blacklisted_token_crud
from app.crud.invitation import CRUDInvitation, invitation_crud
from app.crud import email_verification

__all__ = [
    "CRUDOrganization",
    "organization_crud",
    "CRUDUser",
    "user_crud",
    "CRUDRole",
    "role_crud",
    "CRUDPermission",
    "permission_crud",
    "CRUDUsage",
    "usage_crud",
    "CRUDRefreshToken",
    "refresh_token_crud",
    "CRUDBlacklistedToken",
    "blacklisted_token_crud",
    "CRUDInvitation",
    "invitation_crud",
    "email_verification",
]