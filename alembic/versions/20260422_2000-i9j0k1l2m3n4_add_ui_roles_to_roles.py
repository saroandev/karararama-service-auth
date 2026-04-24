"""add ui_roles boolean to roles

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-04-22 20:00:00.000000

Adds a flag that marks roles intended for user-facing UI selection
(invite dropdown, role-change dropdown). System roles (admin, superuser,
user, premium) stay ui_roles=false.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i9j0k1l2m3n4"
down_revision: Union[str, None] = "h8i9j0k1l2m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("ui_roles", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.execute(
        """
        UPDATE roles
        SET ui_roles = TRUE
        WHERE name IN ('owner', 'org-admin', 'managing-lawyer', 'lawyer', 'trainee');
        """
    )


def downgrade() -> None:
    op.drop_column("roles", "ui_roles")
