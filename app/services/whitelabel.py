"""
Whitelabel slug provisioning at plan upgrade time.

Slug is treated as a paid feature: free trial / solo / team orgs don't
carry one by default. The first time an org lands on a whitelabel plan
(Elite/Enterprise), we derive a slug from its name and persist it so the
tenant subdomain immediately works without an extra admin step.

The helper is idempotent: an org that already has a slug keeps it,
including across downgrade → re-upgrade cycles.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import WHITELABEL_PLANS
from app.core.subdomain import RESERVED_SLUGS, slugify
from app.models import Organization


async def _resolve_unique_slug(db: AsyncSession, *, base: str) -> str:
    """Pick the first free slug of the form base, base-2, base-3, ...

    Suffix is capped so the result stays within the 63-char DNS-label limit.
    """
    candidate = base
    suffix = 2
    while True:
        existing = (
            await db.execute(select(Organization.id).where(Organization.slug == candidate))
        ).first()
        if existing is None:
            return candidate
        tail = f"-{suffix}"
        candidate = f"{base[:63 - len(tail)]}{tail}"
        suffix += 1


async def ensure_whitelabel_slug(db: AsyncSession, *, org: Organization) -> None:
    """Assign a slug to `org` if its plan unlocks the whitelabel feature.

    Idempotent — no-op when `org.slug` is already set or when the plan
    is not in WHITELABEL_PLANS. Mutates `org.slug` in place and stages
    the change on the session; caller owns the commit.

    Reserved labels (collisions with first-party service hosts like
    auth-preprod, mcp, ...) are dodged by tacking on "-org" before the
    collision resolver runs.
    """
    if org.slug:
        return
    if org.plan not in WHITELABEL_PLANS:
        return

    base = slugify(org.name or "") or "org"
    if base in RESERVED_SLUGS:
        base = f"{base}-org"

    org.slug = await _resolve_unique_slug(db, base=base)
    db.add(org)
