"""portal_invitations

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-05-31 12:00:00.000000

Extends `invitations` to carry portal-scoped invites without forking the
table. An invitation is org-scoped (legacy) when muvekkil_id IS NULL,
portal-scoped when set. portal_role mirrors PortalMember.portal_role
and is required for portal invites (validated at API).

Why one table instead of two: invitation lifecycle (pending/accepted/
expired/revoked, token, expires_at, email rate-limit, revoke endpoint)
is identical for both scopes. Forking it would mean two copies of the
same status machine.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, None] = "q7r8s9t0u1v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "invitations",
        sa.Column(
            "muvekkil_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("muvekkiller.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column(
        "invitations",
        sa.Column("portal_role", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_invitations_muvekkil_id",
        "invitations",
        ["muvekkil_id"],
        postgresql_where=sa.text("muvekkil_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_invitations_muvekkil_id", table_name="invitations")
    op.drop_column("invitations", "portal_role")
    op.drop_column("invitations", "muvekkil_id")
