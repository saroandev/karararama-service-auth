"""add_organization_members_table

Revision ID: f9a8b7c6d5e4
Revises: a40cfb556bec
Create Date: 2026-01-26 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'f9a8b7c6d5e4'
down_revision: Union[str, None] = 'a40cfb556bec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create organization_members table
    op.create_table(
        'organization_members',
        sa.Column('id', UUID(), nullable=False),
        sa.Column('user_id', UUID(), nullable=False),
        sa.Column('organization_id', UUID(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='member'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_org_members_user_id', 'organization_members', ['user_id'])
    op.create_index('ix_org_members_org_id', 'organization_members', ['organization_id'])
    op.create_index('ix_org_members_user_org', 'organization_members', ['user_id', 'organization_id'], unique=True)
    op.create_index('ix_org_members_is_primary', 'organization_members', ['is_primary'])

    # Migrate existing data: users.organization_id -> organization_members
    # For all users with organization_id, create membership record
    # Set role='owner' if user is the owner of the organization, otherwise 'member'
    op.execute("""
        INSERT INTO organization_members (id, user_id, organization_id, role, is_primary, joined_at, created_at, updated_at)
        SELECT
            gen_random_uuid(),
            u.id,
            u.organization_id,
            CASE
                WHEN o.owner_id = u.id THEN 'owner'
                ELSE 'member'
            END,
            true,  -- is_primary = true for existing memberships (this is their only org)
            u.created_at,
            NOW(),
            NOW()
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.organization_id IS NOT NULL
    """)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_org_members_is_primary', 'organization_members')
    op.drop_index('ix_org_members_user_org', 'organization_members')
    op.drop_index('ix_org_members_org_id', 'organization_members')
    op.drop_index('ix_org_members_user_id', 'organization_members')

    # Drop table
    op.drop_table('organization_members')
