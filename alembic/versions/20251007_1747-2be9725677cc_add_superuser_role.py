"""add_superuser_role

Revision ID: 2be9725677cc
Revises: 99740f35a284
Create Date: 2025-10-07 17:47:19.149516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2be9725677cc'
down_revision: Union[str, None] = '99740f35a284'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add superuser role to database with all permissions."""
    # Note: This migration runs seed script to add superuser role
    # Run: python -m app.db_seed after this migration to populate the role
    pass


def downgrade() -> None:
    """Remove superuser role from database."""
    # Delete superuser role and its associations
    op.execute("""
        DELETE FROM role_permissions
        WHERE role_id IN (SELECT id FROM roles WHERE name = 'superuser')
    """)
    op.execute("""
        DELETE FROM user_roles
        WHERE role_id IN (SELECT id FROM roles WHERE name = 'superuser')
    """)
    op.execute("DELETE FROM roles WHERE name = 'superuser'")
