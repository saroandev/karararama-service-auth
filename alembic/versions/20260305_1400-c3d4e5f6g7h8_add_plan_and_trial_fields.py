"""add_plan_and_trial_fields

Revision ID: c3d4e5f6g7h8
Revises: a1f2b3c4d5e6
Create Date: 2026-03-05 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, None] = 'a1f2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add plan columns to users table
    op.add_column('users', sa.Column('plan', sa.String(50), nullable=True))
    op.add_column('users', sa.Column('trial_started_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))

    # Index for plan-based queries
    op.create_index(op.f('ix_users_plan'), 'users', ['plan'], unique=False)

    # Set all existing users to free_trial with 14-day trial from creation date
    op.execute(
        "UPDATE users SET plan = 'free_trial', "
        "trial_started_at = created_at, "
        "trial_ends_at = created_at + INTERVAL '14 days' "
        "WHERE plan IS NULL"
    )

    # Upgrade superuser/admin users to professional plan
    op.execute(
        "UPDATE users SET plan = 'professional', trial_ends_at = NULL "
        "WHERE id IN ("
        "  SELECT ur.user_id FROM user_roles ur "
        "  JOIN roles r ON r.id = ur.role_id "
        "  WHERE r.name IN ('superuser', 'admin')"
        ")"
    )

    # Make plan NOT NULL with default
    op.alter_column('users', 'plan', nullable=False, server_default='free_trial')


def downgrade() -> None:
    op.drop_index(op.f('ix_users_plan'), table_name='users')
    op.drop_column('users', 'trial_ends_at')
    op.drop_column('users', 'trial_started_at')
    op.drop_column('users', 'plan')
