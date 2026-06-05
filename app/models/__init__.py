"""
Database models for the authentication service.
"""
from app.models.organization import Organization
from app.models.user import User, user_roles
from app.models.role import Role, role_permissions
from app.models.permission import Permission
from app.models.refresh_token import RefreshToken
from app.models.blacklisted_token import BlacklistedToken
from app.models.usage_log import UsageLog
from app.models.activity_watch_token import ActivityWatchToken
from app.models.uets_account import UetsAccount
from app.models.uyap_account import UyapAccount
from app.models.invitation import Invitation, InvitationStatus
from app.models.email_verification import EmailVerification
from app.models.organization_member import OrganizationMember
from app.models.password_reset import PasswordResetToken
from app.models.muvekkil import Muvekkil, MuvekkilUnvan, muvekkil_organizations
from app.models.iliskili_muvekkil import IliskiliMuvekkil
from app.models.department import Department
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.models.mcp_api_key import MCPApiKey
from app.models.oauth_client import OAuthClient
from app.models.oauth_authorization_code import OAuthAuthorizationCode
from app.models.oauth_refresh_token import OAuthRefreshToken
from app.models.login_attempt import LoginAttempt
from app.models.billing_info import BillingInfo
from app.models.discount_code import DiscountCode, DiscountCodeUse

__all__ = [
    "Organization",
    "User",
    "Role",
    "Permission",
    "RefreshToken",
    "BlacklistedToken",
    "UsageLog",
    "ActivityWatchToken",
    "UetsAccount",
    "UyapAccount",
    "Invitation",
    "InvitationStatus",
    "EmailVerification",
    "OrganizationMember",
    "PasswordResetToken",
    "Muvekkil",
    "MuvekkilUnvan",
    "IliskiliMuvekkil",
    "Department",
    "Payment",
    "Subscription",
    "MCPApiKey",
    "OAuthClient",
    "OAuthAuthorizationCode",
    "OAuthRefreshToken",
    "LoginAttempt",
    "BillingInfo",
    "DiscountCode",
    "DiscountCodeUse",
    "user_roles",
    "role_permissions",
    "muvekkil_organizations",
]