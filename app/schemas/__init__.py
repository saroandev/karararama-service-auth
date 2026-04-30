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
    UserAssignToOrgRequest,
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
    DataAccess,
    RefreshTokenRequest,
    SwitchOrganizationRequest,
    ForgotPasswordRequest,
    ValidateResetTokenRequest,
    ValidateResetTokenResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.schemas.usage import (
    UsageConsumeRequest,
    UsageConsumeResponse,
    UsageErrorResponse,
    UsageLogResponse,
)
from app.schemas.organization import (
    OrganizationBase,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse,
    OrganizationWithStats,
    OrganizationMemberResponse,
    PendingInvitationResponse,
    OrganizationMembersResponse,
)
from app.schemas.invitation import (
    InvitationBase,
    InvitationCreate,
    InvitationBatchCreate,
    InvitationAccept,
    InvitationResponse,
    InvitationPublicResponse,
)
from app.schemas.email_verification import (
    SendVerificationEmailRequest,
    SendVerificationEmailResponse,
    VerifyEmailCodeRequest,
    VerifyEmailCodeResponse,
    ResendVerificationEmailRequest,
    ResendVerificationEmailResponse,
)
from app.schemas.organization_member import (
    OrganizationMembershipResponse,
    UserOrganizationResponse,
    UserOrganizationsListResponse,
    SetPrimaryOrganizationRequest,
    SetPrimaryOrganizationResponse,
)
from app.schemas.uets_account import (
    UetsAccountCreate,
    UetsAccountResponse,
    UetsAccountItem,
    UetsAccountListResponse,
)
from app.schemas.uyap_account import (
    UyapAccountCreate,
    UyapAccountResponse,
    UyapAccountItem,
    UyapAccountListResponse,
)
from app.schemas.muvekkil import (
    MuvekkillBase,
    MuvekkillCreate,
    MuvekkillUpdate,
    MuvekkillResponse,
    MuvekkillWithOrganizations,
)
from app.schemas.iliskili_muvekkil import (
    IliskiliMuvekkillBase,
    IliskiliMuvekkillCreate,
    IliskiliMuvekkillUpdate,
    IliskiliMuvekkillResponse,
    IliskiliMuvekkillAssign,
)
from app.schemas.department import (
    DepartmentBase,
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
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
    "UserAssignToOrgRequest",
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
    "DataAccess",
    "RefreshTokenRequest",
    "SwitchOrganizationRequest",
    "ForgotPasswordRequest",
    "ValidateResetTokenRequest",
    "ValidateResetTokenResponse",
    "ResetPasswordRequest",
    "ResetPasswordResponse",
    # Usage
    "UsageConsumeRequest",
    "UsageConsumeResponse",
    "UsageErrorResponse",
    "UsageLogResponse",
    # Organization
    "OrganizationBase",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    "OrganizationWithStats",
    # UETS Account
    "UetsAccountCreate",
    "UetsAccountResponse",
    "UetsAccountItem",
    "UetsAccountListResponse",
    # UYAP Account
    "UyapAccountCreate",
    "UyapAccountResponse",
    "UyapAccountItem",
    "UyapAccountListResponse",
    # Invitation
    "InvitationBase",
    "InvitationCreate",
    "InvitationBatchCreate",
    "InvitationAccept",
    "InvitationResponse",
    "InvitationPublicResponse",
    # Email Verification
    "SendVerificationEmailRequest",
    "SendVerificationEmailResponse",
    "VerifyEmailCodeRequest",
    "VerifyEmailCodeResponse",
    "ResendVerificationEmailRequest",
    "ResendVerificationEmailResponse",
    # Organization Member
    "OrganizationMembershipResponse",
    "UserOrganizationResponse",
    "UserOrganizationsListResponse",
    "SetPrimaryOrganizationRequest",
    "SetPrimaryOrganizationResponse",
    # Muvekkil
    "MuvekkillBase",
    "MuvekkillCreate",
    "MuvekkillUpdate",
    "MuvekkillResponse",
    "MuvekkillWithOrganizations",
    # Iliskili Muvekkil
    "IliskiliMuvekkillBase",
    "IliskiliMuvekkillCreate",
    "IliskiliMuvekkillUpdate",
    "IliskiliMuvekkillResponse",
    "IliskiliMuvekkillAssign",
    # Department
    "DepartmentBase",
    "DepartmentCreate",
    "DepartmentUpdate",
    "DepartmentResponse",
]