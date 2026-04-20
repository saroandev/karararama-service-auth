"""
Token payload builder shared by login, refresh, and switch-organization flows.
"""
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import (
    calculate_remaining_credits,
    get_data_access_for_user,
    get_primary_role,
)
from app.crud import organization_member_crud, usage_crud
from app.models import User


async def build_user_token_payload(
    db: AsyncSession,
    user: User,
) -> Dict[str, Any]:
    """Build the JWT access token payload for a user.

    Reads the user's current primary organization, all memberships, roles,
    permissions, quotas and remaining daily credits, and returns the dict
    that will be signed into the access token.
    """
    roles = [role.name for role in user.roles]

    permissions = []
    seen = set()
    for role in user.roles:
        for perm in role.permissions:
            key = (perm.resource, perm.action)
            if key in seen:
                continue
            seen.add(key)
            permissions.append({"resource": perm.resource, "action": perm.action})

    data_access = get_data_access_for_user(user)
    primary_role = get_primary_role(user)

    today_usage = await usage_crud.get_user_daily_usage(db, user_id=user.id)
    remaining_credits = calculate_remaining_credits(user, today_usage)

    memberships = await organization_member_crud.get_user_memberships(db, user_id=user.id)
    organizations = [
        {
            "id": str(membership.organization.id),
            "name": membership.organization.name,
            "role": membership.role,
            "is_primary": membership.is_primary,
            "is_owner": membership.organization.owner_id == user.id,
        }
        for membership in memberships
    ]

    return {
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
        },
        "organizations": organizations,
        "plan": user.plan,
        "trial_ends_at": user.trial_ends_at.isoformat() if user.trial_ends_at else None,
    }
