"""guest_otp_active_portal

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-05-31 13:00:00.000000

Two additions for Guest user OTP login + per-user active portal tracking:

1. `otp_codes` table holds one-time email codes. Stored as SHA-256 hashes
   so a DB leak can't replay live codes. `email` is the recipient,
   `organization_id` is optional (brand-scoped rate limiting / email
   styling), `attempts` lets verify back off after repeated wrong codes,
   and `consumed_at` flips the row to "spent" so the same code can't be
   redeemed twice. TTL is 1 hour per the checklist (§3); the value lives
   in expires_at, not a global setting, so per-request overrides are
   trivial.

2. `users.active_portal_id` is the user's currently-focused portal —
   purely a UX/JWT hint, not an access grant (the portal_members table
   is still the authority). NULL means "no portal context active yet";
   the FE picks one on first login (last_used preference per spec §6).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1) otp_codes ----------------------------------------------------
    op.create_table(
        "otp_codes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("requested_ip", sa.String(length=64), nullable=True),
        sa.Column("requested_user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_otp_codes_email", "otp_codes", ["email"])
    op.create_index(
        "ix_otp_codes_active",
        "otp_codes",
        ["email", "expires_at"],
        postgresql_where=sa.text("consumed_at IS NULL"),
    )

    # ---- 2) users.active_portal_id ---------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "active_portal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("muvekkiller.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_users_active_portal_id",
        "users",
        ["active_portal_id"],
        postgresql_where=sa.text("active_portal_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_active_portal_id", table_name="users")
    op.drop_column("users", "active_portal_id")

    op.drop_index("ix_otp_codes_active", table_name="otp_codes")
    op.drop_index("ix_otp_codes_email", table_name="otp_codes")
    op.drop_table("otp_codes")
