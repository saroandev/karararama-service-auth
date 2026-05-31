"""
FastAPI dependencies for portal-scoped permission checks.

Adds a thin layer on top of get_current_active_user that resolves the
target portal and verifies the caller is allowed to act on it.

Authorization model:
- Superuser → everything.
- Members of the host organization → may interact with their own org's
  portals according to their portal_role (manager > responsible > user).
- Guest users → only see portals where they have an active row in
  portal_members.

`require_portal_role()` is the building block; convenience aliases for
the common gates live below.
"""
from typing import Iterable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.crud import muvekkil_crud, portal_member_crud
from app.models import Muvekkil, PortalRole, User


# Loosely ordered from "most authority" to "least"; lookups treat them
# as a set so the order itself doesn't grant escalation.
_PORTAL_ROLE_RANK = {
    PortalRole.MANAGER.value: 3,
    PortalRole.RESPONSIBLE.value: 2,
    PortalRole.USER.value: 1,
    PortalRole.GUEST.value: 0,
}


def _is_superuser(user: User) -> bool:
    return any(r.name.lower() == "superuser" for r in user.roles)


async def _resolve_portal(
    db: AsyncSession, muvekkil_id: UUID
) -> Muvekkil:
    muvekkil = await muvekkil_crud.get(db, id=muvekkil_id)
    if muvekkil is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portal bulunamadı"
        )
    return muvekkil


def require_portal_role(*allowed_roles: PortalRole):
    """Require the caller to hold one of `allowed_roles` on the target portal.

    Usage:
        @router.post("/muvekkiller/{muvekkil_id}/members", ...)
        async def add_member(
            muvekkil_id: UUID,
            ctx = Depends(require_portal_role(PortalRole.MANAGER)),
        ):
            portal: Muvekkil = ctx.portal
            ...
    """
    allowed_set = {r.value for r in allowed_roles}

    async def _dependency(
        muvekkil_id: UUID,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
    ) -> "PortalContext":
        portal = await _resolve_portal(db, muvekkil_id)

        if _is_superuser(current_user):
            return PortalContext(
                portal=portal, current_user=current_user, portal_role=None
            )

        # Org-side members with a matching role inside this portal.
        membership = await portal_member_crud.get_membership(
            db, muvekkil_id=portal.id, user_id=current_user.id
        )
        if membership is not None and membership.is_active:
            if membership.portal_role in allowed_set:
                return PortalContext(
                    portal=portal,
                    current_user=current_user,
                    portal_role=membership.portal_role,
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bu işlem için portal rolünüz yetersiz",
            )

        # No portal membership → only allowed if caller is the host org's
        # owner/admin AND the portal lives in that org. This bridges the
        # "firm admin creates the first portal manager" bootstrap step
        # without forcing them to grant themselves membership first.
        is_host_org_admin = (
            current_user.organization_id == portal.organization_id
            and any(
                r.name.lower() in {"owner", "admin", "org-admin"}
                for r in current_user.roles
            )
            and PortalRole.MANAGER.value in allowed_set
        )
        if is_host_org_admin:
            return PortalContext(
                portal=portal, current_user=current_user, portal_role=None
            )

        # Hide the existence of the portal from non-members.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portal bulunamadı"
        )

    return _dependency


def require_portal_permission(resource: str, action: str):
    """Higher-level permission gate that maps (resource, action) to the
    minimum portal role needed.

    The mapping is conservative — promote roles here when a new endpoint
    needs finer control instead of baking the role list into every
    handler.
    """
    # Manager-only: manage members, archive, delete portal
    manager_only = {
        ("members", "add"), ("members", "remove"), ("members", "update"),
        ("invite", "send"), ("invite", "revoke"),
        ("portal", "archive"), ("portal", "delete"), ("portal", "update"),
    }
    # Manager + responsible: write portal content
    responsible_up = {
        ("files", "upload"), ("files", "delete"),
        ("notes", "write"),
    }
    if (resource, action) in manager_only:
        gate = require_portal_role(PortalRole.MANAGER)
    elif (resource, action) in responsible_up:
        gate = require_portal_role(PortalRole.MANAGER, PortalRole.RESPONSIBLE)
    else:
        # Default: any active portal member can read.
        gate = require_portal_role(
            PortalRole.MANAGER,
            PortalRole.RESPONSIBLE,
            PortalRole.USER,
            PortalRole.GUEST,
        )
    return gate


class PortalContext:
    """Resolved portal + caller, returned by the dependency.

    Endpoints typically destructure: `ctx.portal`, `ctx.current_user`.
    """

    __slots__ = ("portal", "current_user", "portal_role")

    def __init__(self, *, portal: Muvekkil, current_user: User, portal_role):
        self.portal = portal
        self.current_user = current_user
        self.portal_role = portal_role
