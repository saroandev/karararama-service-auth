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


def compact_permissions(permissions: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Drop permission entries that are already covered by a wildcard.

    `*:*` collapses the whole list to a single entry. Otherwise any specific
    `(r, a)` covered by an existing `(r, *)` or `(*, a)` is dropped. The
    matching contract here mirrors `JWTPayload.has_permission`.
    """
    perm_set = {(p["resource"], p["action"]) for p in permissions}

    if ("*", "*") in perm_set:
        return [{"resource": "*", "action": "*"}]

    wildcard_resources = {r for (r, a) in perm_set if a == "*" and r != "*"}
    wildcard_actions = {a for (r, a) in perm_set if r == "*" and a != "*"}

    compacted: List[Dict[str, str]] = []
    for perm in permissions:
        r, a = perm["resource"], perm["action"]
        if r != "*" and a != "*" and (r in wildcard_resources or a in wildcard_actions):
            continue
        compacted.append(perm)
    return compacted


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

    permissions: List[Dict[str, str]] = []
    seen = set()
    for role in active_roles:
        for perm in role.permissions:
            key = (perm.resource, perm.action)
            if key in seen:
                continue
            seen.add(key)
            permissions.append({"resource": perm.resource, "action": perm.action})
    permissions = compact_permissions(permissions)

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

    # Plan now lives on the organization (Solo/Team/Elite/Enterprise). For
    # legacy compatibility we fall back to user.plan when no org plan exists.
    org_plan = None
    org_plan_expires_at = None
    org_trial_ends_at = None
    org_seat_count = None
    org_storage_gb_per_user = None
    if user.organization is not None:
        org_plan = user.organization.plan
        org_plan_expires_at = user.organization.plan_expires_at
        org_trial_ends_at = user.organization.trial_ends_at
        org_seat_count = user.organization.seat_count
        # Decimal → float for JSON serialization
        if user.organization.storage_gb_per_user is not None:
            org_storage_gb_per_user = float(user.organization.storage_gb_per_user)

    plan = org_plan or user.plan or "free_trial"
    trial_ends_at_iso = (
        org_trial_ends_at.isoformat() if org_trial_ends_at
        else (user.trial_ends_at.isoformat() if user.trial_ends_at else None)
    )
    plan_expires_at_iso = org_plan_expires_at.isoformat() if org_plan_expires_at else None

    # Paywall flag — frontend middleware bunu kullanarak protected route'lardan
    # /paketler'e zorla yönlendirir. expired_trial veya expired_subscription
    # durumunda true; aktif veya henüz dolmamış trial'da false.
    paywall = plan in {"expired_trial", "expired_subscription"}

    # Whitelabel slug of the active org — surfaced as a JWT claim so the FE
    # can verify token-vs-subdomain match without an extra round trip
    # (and so other services see which whitelabel context the token came from).
    org_slug = user.organization.slug if user.organization is not None else None

    return {
        "sub": str(user.id),
        "organization_id": str(user.organization_id) if user.organization_id else None,
        "organization_slug": org_slug,
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
        "plan": plan,
        "plan_expires_at": plan_expires_at_iso,
        "trial_ends_at": trial_ends_at_iso,
        "seat_count": org_seat_count,
        "storage_gb_per_user": org_storage_gb_per_user,
        "paywall": paywall,
    }
