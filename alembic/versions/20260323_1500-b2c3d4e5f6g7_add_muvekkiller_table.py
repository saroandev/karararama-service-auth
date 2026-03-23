"""add_muvekkiller_table_and_muvekkil_organizations_association

Revision ID: b2c3d4e5f6g7
Revises: c3d4e5f6g7h8
Create Date: 2026-03-23 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create muvekkiller table
    op.create_table('muvekkiller',
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id')
    )
    op.create_index(op.f('ix_muvekkiller_email'), 'muvekkiller', ['email'], unique=False)

    # Create muvekkil_organizations association table
    op.create_table('muvekkil_organizations',
        sa.Column('muvekkil_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['muvekkil_id'], ['muvekkiller.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('muvekkil_id', 'organization_id')
    )


def downgrade() -> None:
    # Drop association table first (due to foreign keys)
    op.drop_table('muvekkil_organizations')

    # Drop muvekkiller table
    op.drop_index(op.f('ix_muvekkiller_email'), table_name='muvekkiller')
    op.drop_table('muvekkiller')
