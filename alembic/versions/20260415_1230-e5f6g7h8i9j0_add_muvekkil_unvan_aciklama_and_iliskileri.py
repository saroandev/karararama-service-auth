"""add_muvekkil_unvan_aciklama_and_iliskileri

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-04-15 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6g7h8i9j0'
down_revision: Union[str, None] = 'd4e5f6g7h8i9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unvan (person/company classification) with default 'kisi' for existing rows
    op.add_column(
        'muvekkiller',
        sa.Column(
            'unvan',
            sa.Enum('kisi', 'sirket', name='muvekkilunvan', native_enum=False),
            nullable=False,
            server_default='kisi',
        ),
    )

    # Add free-form description column
    op.add_column(
        'muvekkiller',
        sa.Column('muvekkil_aciklama', sa.Text(), nullable=True),
    )

    # Directed self-referential association table
    op.create_table(
        'muvekkil_iliskileri',
        sa.Column('muvekkil_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('iliskili_muvekkil_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['muvekkil_id'], ['muvekkiller.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['iliskili_muvekkil_id'], ['muvekkiller.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('muvekkil_id', 'iliskili_muvekkil_id'),
    )


def downgrade() -> None:
    op.drop_table('muvekkil_iliskileri')
    op.drop_column('muvekkiller', 'muvekkil_aciklama')
    op.drop_column('muvekkiller', 'unvan')
