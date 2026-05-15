"""add_org_plan_fields

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-05-15 14:00:00.000000

Move plan/billing from `users` to `organizations` (the new source of truth).
Backfill organization plan from member users; users without an organization
get a personal organization auto-created so the JWT path always resolves.

`users.plan` columns stay in place for now to keep older deployments and
the JWT migration period happy — they are populated during login from the
organization until they can be dropped in a follow-up migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add new columns to organizations (all nullable first; we backfill, then tighten plan)
    op.add_column('organizations', sa.Column('plan', sa.String(50), nullable=True))
    op.add_column('organizations', sa.Column('plan_started_at', sa.DateTime(), nullable=True))
    op.add_column('organizations', sa.Column('plan_expires_at', sa.DateTime(), nullable=True))
    op.add_column('organizations', sa.Column('billing_cycle', sa.String(20), nullable=True))
    op.add_column('organizations', sa.Column('seat_count', sa.Integer(), nullable=True))
    op.add_column('organizations', sa.Column('storage_gb_per_user', sa.Numeric(6, 2), nullable=True))
    op.add_column('organizations', sa.Column('trial_started_at', sa.DateTime(), nullable=True))
    op.add_column('organizations', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))

    op.create_index(op.f('ix_organizations_plan'), 'organizations', ['plan'], unique=False)

    # 2) Auto-create a personal organization for every user without one (Solo default)
    #    The org is named after the user; owner_id points back to the user.
    op.execute(
        """
        INSERT INTO organizations (id, name, owner_id, organization_type, organization_size,
                                   is_active, created_at, updated_at)
        SELECT gen_random_uuid(),
               COALESCE(NULLIF(TRIM(CONCAT(u.first_name, ' ', u.last_name)), ''), u.email) || ' (Personal)',
               u.id,
               'other',
               '1-9',
               TRUE,
               NOW(),
               NOW()
        FROM users u
        WHERE u.organization_id IS NULL
        """
    )

    # 3) Link the user to the freshly created org
    op.execute(
        """
        UPDATE users u
        SET organization_id = o.id
        FROM organizations o
        WHERE u.organization_id IS NULL
          AND o.owner_id = u.id
          AND o.name LIKE '%(Personal)'
        """
    )

    # 4) Backfill org plan from the owner user, with sensible defaults for free trial.
    #    Existing free_trial users carried trial dates on users → mirror onto org.
    op.execute(
        """
        UPDATE organizations o
        SET plan = COALESCE(u.plan, 'free_trial'),
            trial_started_at = u.trial_started_at,
            trial_ends_at = u.trial_ends_at,
            plan_started_at = CASE WHEN u.plan IN ('solo','team','elite','enterprise','professional')
                                   THEN COALESCE(u.trial_started_at, o.created_at) END
        FROM users u
        WHERE o.owner_id = u.id
        """
    )

    # 5) Fill in defaults for any org still missing a plan (orgs without a clear owner)
    op.execute(
        """
        UPDATE organizations
        SET plan = 'free_trial',
            trial_started_at = COALESCE(trial_started_at, created_at),
            trial_ends_at = COALESCE(trial_ends_at, created_at + INTERVAL '14 days')
        WHERE plan IS NULL
        """
    )

    # 6) Treat legacy 'professional' rows as Solo with a long expiry so admins still bypass quotas.
    op.execute(
        """
        UPDATE organizations
        SET plan = 'solo',
            seat_count = 1,
            storage_gb_per_user = 1,
            billing_cycle = 'yearly',
            plan_expires_at = COALESCE(plan_expires_at, NOW() + INTERVAL '10 years')
        WHERE plan = 'professional'
        """
    )

    # 7) Tighten the plan column
    op.alter_column('organizations', 'plan', nullable=False, server_default='free_trial')


def downgrade() -> None:
    op.drop_index(op.f('ix_organizations_plan'), table_name='organizations')
    for col in (
        'trial_ends_at',
        'trial_started_at',
        'storage_gb_per_user',
        'seat_count',
        'billing_cycle',
        'plan_expires_at',
        'plan_started_at',
        'plan',
    ):
        op.drop_column('organizations', col)
