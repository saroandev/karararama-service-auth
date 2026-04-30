"""add_uyap_accounts_table

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-04-30 11:52:00.000000

UYAP accounts are organization-level resources: any member of the org can
add/list/remove them. Account names are unique per organization, so the
primary key is (org_id, uyap_account_name). The creator is tracked for
audit via created_by_user_id (nullable so user deletion does not cascade
the account away).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'k1l2m3n4o5p6'
down_revision: Union[str, None] = 'j0k1l2m3n4o5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'uyap_accounts',
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('uyap_account_name', sa.String(length=255), nullable=False),
        sa.Column('created_by_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('org_id', 'uyap_account_name'),
    )


def downgrade() -> None:
    op.drop_table('uyap_accounts')
