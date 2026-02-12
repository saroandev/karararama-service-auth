"""add_phone_coupon_and_legal_consents

Revision ID: a1b2c3d4e5f6
Revises: d26cd4811e34
Create Date: 2026-01-25 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd26cd4811e34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add phone and coupon_code columns
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('coupon_code', sa.String(length=50), nullable=True))

    # Add legal consent timestamp columns
    op.add_column('users', sa.Column('kvkk_consent_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('cookie_consent_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('privacy_consent_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove legal consent columns
    op.drop_column('users', 'privacy_consent_at')
    op.drop_column('users', 'cookie_consent_at')
    op.drop_column('users', 'kvkk_consent_at')

    # Remove phone and coupon_code columns
    op.drop_column('users', 'coupon_code')
    op.drop_column('users', 'phone')
