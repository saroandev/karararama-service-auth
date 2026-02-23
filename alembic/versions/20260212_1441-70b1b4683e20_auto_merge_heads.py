"""auto_merge_heads

Revision ID: 70b1b4683e20
Revises: f9a8b7c6d5e4, 089c6a76ed05
Create Date: 2026-02-12 14:41:50.171604

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70b1b4683e20'
down_revision: Union[str, None] = ('f9a8b7c6d5e4', '089c6a76ed05')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
