"""
Permission and data access control utilities.
"""
from typing import Iterable, List, Optional
from app.models import Role, User


# Role-based data access mapping
DATA_ACCESS_BY_ROLE = {
    "superuser": {
        "own_data": True,
        "shared_data": True,
        "all_users_data": True
    },
    "admin": {
        "own_data": True,
        "shared_data": True,
        "all_users_data": True
    },
    "member": {
        "own_data": True,
        "shared_data": True,
        "all_users_data": False
    },
    "viewer": {
        "own_data": False,
        "shared_data": True,
        "all_users_data": False
    },
}


def get_data_access_for_user(user: User, roles: Optional[Iterable[Role]] = None) -> dict:
    """
    Get data access permissions for a user based on their roles.

    Args:
        user: User model instance
        roles: Optional explicit role list. When provided (e.g. scoped to the
            user's active organization), this replaces user.roles for the
            computation. Falls back to user.roles when omitted.

    Returns:
        Dictionary with own_data, shared_data, all_users_data flags
    """
    source_roles = roles if roles is not None else user.roles
    role_names = [role.name.lower() for role in source_roles]

    # Superuser users get full access
    if "superuser" in role_names:
        return DATA_ACCESS_BY_ROLE["superuser"]

    # Admin users get full access
    if "admin" in role_names:
        return DATA_ACCESS_BY_ROLE["admin"]

    # Member users get own + shared access
    if "member" in role_names or "user" in role_names:
        return DATA_ACCESS_BY_ROLE["member"]

    # Viewer users get only shared access
    if "viewer" in role_names:
        return DATA_ACCESS_BY_ROLE["viewer"]

    # Default: member access
    return DATA_ACCESS_BY_ROLE["member"]


def get_primary_role(user: User, roles: Optional[Iterable[Role]] = None) -> str:
    """
    Get the primary (most privileged) role for a user.

    Role hierarchy: superuser > admin > member/user > viewer

    Args:
        user: User model instance
        roles: Optional explicit role list. When provided (e.g. scoped to the
            user's active organization), this replaces user.roles for the
            computation. Falls back to user.roles when omitted.

    Returns:
        Primary role name
    """
    source_roles = roles if roles is not None else user.roles
    role_names = [role.name.lower() for role in source_roles]

    # Check in priority order
    if "superuser" in role_names:
        return "superuser"
    if "admin" in role_names:
        return "admin"
    if "member" in role_names or "user" in role_names:
        return "member"
    if "viewer" in role_names:
        return "viewer"

    # Default
    return "member"


def calculate_remaining_credits(user: User, today_usage: int = 0) -> Optional[int]:
    """
    Calculate remaining daily credits for a user.

    Args:
        user: User model instance
        today_usage: Number of queries used today

    Returns:
        Remaining credits or None (unlimited)
    """
    if user.daily_query_limit is None:
        # Unlimited
        return None

    remaining = user.daily_query_limit - today_usage
    return max(0, remaining)
