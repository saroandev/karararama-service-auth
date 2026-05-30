"""
Plan catalog and billing constants.

Pricing model: USD per user per month. PayTR charges in TRY (kuruş);
the daily USD→TRY exchange rate is applied at order creation time.

Billing cycles:
- yearly   = 12 months prepaid
- sixmonth = 6 months prepaid
"""
from typing import Optional, TypedDict


class PlanDefinition(TypedDict):
    name: str
    min_users: int
    max_users: Optional[int]  # None = unlimited (Enterprise)
    price_usd_per_user_monthly: int
    storage_gb_per_user: float
    contact_sales_only: bool


# `contact_sales_only`:
#   True  → frontend "Iletisime Gec" gosterir, /odeme akisi kapali; backend
#           /billing/orders bu plan icin 400 doner (sadece Solo self-service).
#   False → /odeme akisi acik (PayTR ile self-service satin alma).
PLAN_CATALOG: dict[str, PlanDefinition] = {
    "solo": {
        "name": "Solo",
        "min_users": 1,
        "max_users": 1,
        "price_usd_per_user_monthly": 45,
        "storage_gb_per_user": 1.0,
        "contact_sales_only": False,
    },
    "team": {
        "name": "Team",
        "min_users": 2,
        "max_users": 9,
        "price_usd_per_user_monthly": 40,
        "storage_gb_per_user": 5.0,
        # Team/Elite/Enterprise satislari satis ekibi uzerinden yurutulur;
        # self-service PayTR akisi simdilik sadece Solo'ya acik.
        "contact_sales_only": True,
    },
    "elite": {
        "name": "Elite",
        "min_users": 10,
        "max_users": 49,
        "price_usd_per_user_monthly": 35,
        "storage_gb_per_user": 7.5,
        "contact_sales_only": True,
    },
    "enterprise": {
        "name": "Enterprise",
        "min_users": 50,
        "max_users": None,
        "price_usd_per_user_monthly": 30,
        "storage_gb_per_user": 10.0,
        "contact_sales_only": True,
    },
}

BILLING_CYCLES = {
    "yearly": 12,    # 12 months
    "sixmonth": 6,   # 6 months
}

# Plans that count as paid (post-trial)
PAID_PLANS = {"solo", "team", "elite", "enterprise"}

# Plans that include the whitelabel subdomain feature (<slug>.onedocs.ai).
# Organizations on other plans technically have a slug column (assigned at
# create time / via migration backfill) but it is intentionally not
# addressable: the by-slug branding endpoint returns 404 and the login
# X-Org-Slug pin is treated as a no-op. Upgrade to Elite to unlock.
WHITELABEL_PLANS = {"elite", "enterprise"}

# Plan states
PLAN_FREE_TRIAL = "free_trial"
PLAN_EXPIRED_TRIAL = "expired_trial"
PLAN_EXPIRED_SUBSCRIPTION = "expired_subscription"

# Trial duration
TRIAL_DURATION_DAYS = 14


def validate_seat_count(plan: str, seat_count: int) -> bool:
    """Return True if seat_count is within the allowed range for the plan."""
    definition = PLAN_CATALOG.get(plan)
    if definition is None:
        return False
    if seat_count < definition["min_users"]:
        return False
    if definition["max_users"] is not None and seat_count > definition["max_users"]:
        return False
    return True


def calculate_total_usd(plan: str, seat_count: int, billing_cycle: str) -> float:
    """Total USD amount for the given plan/seats/cycle. Caller should validate inputs."""
    definition = PLAN_CATALOG[plan]
    months = BILLING_CYCLES[billing_cycle]
    return definition["price_usd_per_user_monthly"] * seat_count * months
