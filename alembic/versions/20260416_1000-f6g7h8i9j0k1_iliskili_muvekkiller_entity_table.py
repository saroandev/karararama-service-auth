"""iliskili_muvekkiller_entity_table

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-04-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f6g7h8i9j0k1'
down_revision: Union[str, None] = 'e5f6g7h8i9j0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('muvekkil_iliskileri')

    op.create_table(
        'iliskili_muvekkiller',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('unvan', sa.Enum('kisi', 'sirket', name='muvekkilunvan', native_enum=False), nullable=False, server_default='kisi'),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('address', sa.String(length=500), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('muvekkil_aciklama', sa.Text(), nullable=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('muvekkil_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['muvekkil_id'], ['muvekkiller.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id'),
    )
    op.create_index(op.f('ix_iliskili_muvekkiller_email'), 'iliskili_muvekkiller', ['email'], unique=False)
    op.create_index(op.f('ix_iliskili_muvekkiller_organization_id'), 'iliskili_muvekkiller', ['organization_id'], unique=False)
    op.create_index(op.f('ix_iliskili_muvekkiller_muvekkil_id'), 'iliskili_muvekkiller', ['muvekkil_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_iliskili_muvekkiller_muvekkil_id'), table_name='iliskili_muvekkiller')
    op.drop_index(op.f('ix_iliskili_muvekkiller_organization_id'), table_name='iliskili_muvekkiller')
    op.drop_index(op.f('ix_iliskili_muvekkiller_email'), table_name='iliskili_muvekkiller')
    op.drop_table('iliskili_muvekkiller')

    op.create_table(
        'muvekkil_iliskileri',
        sa.Column('muvekkil_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('iliskili_muvekkil_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['muvekkil_id'], ['muvekkiller.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['iliskili_muvekkil_id'], ['muvekkiller.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('muvekkil_id', 'iliskili_muvekkil_id'),
    )
