"""
User onboarding helpers: personal organization provisioning for new registrations.
"""
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.plans import PLAN_FREE_TRIAL, TRIAL_DURATION_DAYS
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

    The org starts on free_trial with a 14-day clock; once they purchase
    a plan the billing service flips this over to solo/team/elite/enterprise.

    Does not commit — caller is responsible for the transaction boundary.
    Returns the flushed Organization instance (id is available).
    """
    now = datetime.utcnow()
    org = Organization(
        name=_personal_org_name(user),
        owner_id=user.id,
        is_active=True,
        plan=PLAN_FREE_TRIAL,
        trial_started_at=now,
        trial_ends_at=now + timedelta(days=TRIAL_DURATION_DAYS),
    )
    db.add(org)
    await db.flush()
    return org
