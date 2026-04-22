"""
User onboarding helpers: personal organization provisioning for new registrations.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, User


def _personal_org_name(user: User) -> str:
    parts = [p for p in (user.first_name, user.last_name) if p and p.strip()]
    return " ".join(parts) if parts else "Kişisel Organizasyon"


async def create_personal_organization(
    db: AsyncSession,
    user: User,
) -> Organization:
    """
    Create an organization owned by the user, named after them.

    Does not commit — caller is responsible for the transaction boundary.
    Returns the flushed Organization instance (id is available).
    """
    org = Organization(
        name=_personal_org_name(user),
        owner_id=user.id,
        is_active=True,
    )
    db.add(org)
    await db.flush()
    return org
