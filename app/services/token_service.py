"""
Token payload builder shared by login, refresh, and switch-organization flows.
"""
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions import (
    calculate_remaining_credits,
    get_data_access_for_user,
)
from app.crud import organization_member_crud, usage_crud
from app.models import Role, User
from app.models.user import user_roles


async def get_active_org_roles(db: AsyncSession, user: User) -> List[Role]:
    """Return roles assigned to the user scoped to their active organization.

    After the user_roles org-required refactor every user_roles row has an
    organization_id, so a user without an active organization indicates a
    data-integrity regression; we fall back to relationship-loaded roles in
    that case rather than raise.
    """
    if user.organization_id is None:
        return list(user.roles)

    stmt = (
        select(Role)
        .join(user_roles, user_roles.c.role_id == Role.id)
        .where(user_roles.c.user_id == user.id)
        .where(user_roles.c.organization_id == user.organization_id)
        .options(selectinload(Role.permissions))
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def build_user_token_payload(
    db: AsyncSession,
    user: User,
) -> Dict[str, Any]:
    """Build the JWT access token payload for a user.

    Reads the user's current primary organization, roles scoped to that
    organization, their permissions, quotas and remaining daily credits, and
    returns the dict that will be signed into the access token.
    """
    active_roles = await get_active_org_roles(db, user)

    roles = [role.name for role in active_roles]

    permissions = []
    seen = set()
    for role in active_roles:
        for perm in role.permissions:
            key = (perm.resource, perm.action)
            if key in seen:
                continue
            seen.add(key)
            permissions.append({"resource": perm.resource, "action": perm.action})

    data_access = get_data_access_for_user(user, roles=active_roles)
    # JWT 'role' = aktif organizasyondaki gerçek rol adı.
    primary_role = active_roles[0].name if active_roles else "member"

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
