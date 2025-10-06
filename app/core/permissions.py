"""
Permission and data access control utilities.
"""
from typing import List, Optional
from app.models import User


# Role-based data access mapping
DATA_ACCESS_BY_ROLE = {
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
    "guest": {
        "own_data": False,
        "shared_data": False,
        "all_users_data": False
    }
}


def get_data_access_for_user(user: User) -> dict:
    """
    Get data access permissions for a user based on their roles.

    Args:
        user: User model instance

    Returns:
        Dictionary with own_data, shared_data, all_users_data flags
    """
    # Get all role names
    role_names = [role.name.lower() for role in user.roles]

    # Admin users get full access
    if "admin" in role_names:
        return DATA_ACCESS_BY_ROLE["admin"]

    # Member users get own + shared access
    if "member" in role_names or "user" in role_names:
        return DATA_ACCESS_BY_ROLE["member"]

    # Viewer users get only shared access
    if "viewer" in role_names:
        return DATA_ACCESS_BY_ROLE["viewer"]

    # Guest users get no access
    if "guest" in role_names or "demo" in role_names:
        return DATA_ACCESS_BY_ROLE["guest"]

    # Default: member access
    return DATA_ACCESS_BY_ROLE["member"]


def get_primary_role(user: User) -> str:
    """
    Get the primary (most privileged) role for a user.

    Role hierarchy: admin > member/user > viewer > guest/demo

    Args:
        user: User model instance

    Returns:
        Primary role name
    """
    role_names = [role.name.lower() for role in user.roles]

    # Check in priority order
    if "admin" in role_names:
        return "admin"
    if "member" in role_names or "user" in role_names:
        return "member"
    if "viewer" in role_names:
        return "viewer"
    if "guest" in role_names or "demo" in role_names:
        return "guest"

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
