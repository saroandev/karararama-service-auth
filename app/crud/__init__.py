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
from app.crud.uets_account import CRUDUetsAccount, uets_account_crud
from app.crud.uyap_account import CRUDUyapAccount, uyap_account_crud
from app.crud.invitation import CRUDInvitation, invitation_crud
from app.crud.organization_member import CRUDOrganizationMember, organization_member_crud
from app.crud import email_verification
from app.crud.muvekkil import CRUDMuvekkil, muvekkil_crud
from app.crud.portal_member import CRUDPortalMember, portal_member_crud
from app.crud.iliskili_muvekkil import CRUDIliskiliMuvekkil, iliskili_muvekkil_crud
from app.crud.department import CRUDDepartment, department_crud
from app.crud.mcp_api_key import CRUDMcpApiKey, mcp_api_key_crud
from app.crud.oauth_client import CRUDOAuthClient, oauth_client_crud
from app.crud.oauth_authorization_code import (
    CRUDOAuthAuthorizationCode,
    oauth_authorization_code_crud,
)
from app.crud.oauth_refresh_token import (
    CRUDOAuthRefreshToken,
    oauth_refresh_token_crud,
)

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
    "CRUDUetsAccount",
    "uets_account_crud",
    "CRUDUyapAccount",
    "uyap_account_crud",
    "CRUDInvitation",
    "invitation_crud",
    "CRUDOrganizationMember",
    "organization_member_crud",
    "email_verification",
    "CRUDMuvekkil",
    "muvekkil_crud",
    "CRUDPortalMember",
    "portal_member_crud",
    "CRUDIliskiliMuvekkil",
    "iliskili_muvekkil_crud",
    "CRUDDepartment",
    "department_crud",
    "CRUDMcpApiKey",
    "mcp_api_key_crud",
    "CRUDOAuthClient",
    "oauth_client_crud",
    "CRUDOAuthAuthorizationCode",
    "oauth_authorization_code_crud",
    "CRUDOAuthRefreshToken",
    "oauth_refresh_token_crud",
]