"""portal_foundation

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-05-31 11:00:00.000000

Reshapes the Muvekkil entity into a true Portal:

1. `muvekkiller` gains `organization_id` (FK, NOT NULL after backfill),
   `tckn` (gerçek kişi kimlik), `vkn` (tüzel kişi vergi no), and
   `is_archived` / `archived_at` for soft archival.

   The old M2M `muvekkil_organizations` is collapsed: each muvekkil gets
   pinned to exactly one organization (the oldest org it was linked to
   wins — deterministic for both prod and dev). The junction table is
   then dropped.

   tckn/vkn are nullable in this migration (legacy rows have neither);
   uniqueness inside an org is enforced via partial unique indexes so
   nulls don't conflict.

2. `portal_members` table joins users to portals with a per-portal role
   (manager / responsible / user / guest). Replaces the implicit "any
   user in the host org can touch any muvekkil" rule that we lived with
   before.

3. `users.user_type` enum-as-varchar distinguishes organization members
   from guest users. Existing users default to organization_member.

Local dev DB has no portal data, so the M2M backfill is a no-op there.
On preprod/prod the SELECT-and-UPDATE pass copies the chosen org_id per
muvekkil before the M2M table is dropped.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "q7r8s9t0u1v2"
down_revision: Union[str, None] = "p6q7r8s9t0u1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- 1) muvekkiller: new columns -------------------------------------
    op.add_column(
        "muvekkiller",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("muvekkiller", sa.Column("tckn", sa.String(length=11), nullable=True))
    op.add_column("muvekkiller", sa.Column("vkn", sa.String(length=10), nullable=True))
    op.add_column(
        "muvekkiller",
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "muvekkiller",
        sa.Column("archived_at", sa.DateTime(), nullable=True),
    )

    # ---- 2) Backfill organization_id from the M2M ------------------------
    # Pick the org with the earliest organizations.created_at per muvekkil
    # so the choice is deterministic. If two orgs tie, the smaller UUID
    # wins (stable secondary sort).
    op.execute(
        sa.text(
            """
            UPDATE muvekkiller m
            SET organization_id = sub.organization_id
            FROM (
                SELECT DISTINCT ON (mo.muvekkil_id)
                    mo.muvekkil_id,
                    mo.organization_id
                FROM muvekkil_organizations mo
                JOIN organizations o ON o.id = mo.organization_id
                ORDER BY mo.muvekkil_id, o.created_at ASC, o.id ASC
            ) sub
            WHERE m.id = sub.muvekkil_id
            """
        )
    )

    # Any muvekkil without ANY org link gets orphaned. Production should
    # have none of these (junction is the only way they were linked), but
    # if there are, this lets us flag them rather than silently break:
    op.execute(
        sa.text(
            """
            DO $$
            DECLARE orphan_count int;
            BEGIN
                SELECT COUNT(*) INTO orphan_count
                FROM muvekkiller WHERE organization_id IS NULL;
                IF orphan_count > 0 THEN
                    RAISE NOTICE
                        'WARNING: % muvekkil row(s) have no org link and will be left NULL — '
                        'NOT NULL constraint will follow once they are cleaned up.',
                        orphan_count;
                END IF;
            END $$;
            """
        )
    )

    # Promote to NOT NULL + create the FK + helpful index. If any orphans
    # exist, this ALTER will fail — operators must clean them first.
    op.alter_column("muvekkiller", "organization_id", nullable=False)
    op.create_foreign_key(
        "fk_muvekkiller_organization_id",
        "muvekkiller",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_muvekkiller_organization_id",
        "muvekkiller",
        ["organization_id"],
    )

    # Per-org uniqueness on TCKN/VKN. Partial indexes keep NULL rows from
    # colliding while ensuring no two muvekkil in the same org share a
    # real-world identity number.
    op.create_index(
        "uq_muvekkiller_org_tckn",
        "muvekkiller",
        ["organization_id", "tckn"],
        unique=True,
        postgresql_where=sa.text("tckn IS NOT NULL"),
    )
    op.create_index(
        "uq_muvekkiller_org_vkn",
        "muvekkiller",
        ["organization_id", "vkn"],
        unique=True,
        postgresql_where=sa.text("vkn IS NOT NULL"),
    )

    # Drop the junction table — single FK is the new model.
    op.drop_table("muvekkil_organizations")

    # ---- 3) portal_members ----------------------------------------------
    op.create_table(
        "portal_members",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "muvekkil_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("muvekkiller.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # portal_role: 'manager' | 'responsible' | 'user' | 'guest'.
        # Kept as plain VARCHAR (no native enum) so future additions
        # don't require a schema migration — mirrors how MuvekkilUnvan
        # is stored.
        sa.Column("portal_role", sa.String(length=32), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "invited_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.UniqueConstraint(
            "muvekkil_id", "user_id", name="uq_portal_members_muvekkil_user"
        ),
    )
    op.create_index(
        "ix_portal_members_muvekkil_id", "portal_members", ["muvekkil_id"]
    )
    op.create_index("ix_portal_members_user_id", "portal_members", ["user_id"])
    op.create_index(
        "ix_portal_members_active",
        "portal_members",
        ["muvekkil_id"],
        postgresql_where=sa.text("is_active = true"),
    )

    # ---- 4) users.user_type ---------------------------------------------
    # 'organization_member' = firm-side (avukat/çalışan), can own org data
    # 'guest'               = client-side (Guest user via portal), no org
    op.add_column(
        "users",
        sa.Column(
            "user_type",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'organization_member'"),
        ),
    )
    op.create_index("ix_users_user_type", "users", ["user_type"])


def downgrade() -> None:
    # 4)
    op.drop_index("ix_users_user_type", table_name="users")
    op.drop_column("users", "user_type")

    # 3)
    op.drop_index("ix_portal_members_active", table_name="portal_members")
    op.drop_index("ix_portal_members_user_id", table_name="portal_members")
    op.drop_index("ix_portal_members_muvekkil_id", table_name="portal_members")
    op.drop_table("portal_members")

    # 2) recreate the junction and copy data back; drop new columns
    op.create_table(
        "muvekkil_organizations",
        sa.Column(
            "muvekkil_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("muvekkiller.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO muvekkil_organizations (muvekkil_id, organization_id)
            SELECT id, organization_id FROM muvekkiller WHERE organization_id IS NOT NULL
            """
        )
    )

    op.drop_index("uq_muvekkiller_org_vkn", table_name="muvekkiller")
    op.drop_index("uq_muvekkiller_org_tckn", table_name="muvekkiller")
    op.drop_index("ix_muvekkiller_organization_id", table_name="muvekkiller")
    op.drop_constraint(
        "fk_muvekkiller_organization_id", "muvekkiller", type_="foreignkey"
    )
    op.drop_column("muvekkiller", "archived_at")
    op.drop_column("muvekkiller", "is_archived")
    op.drop_column("muvekkiller", "vkn")
    op.drop_column("muvekkiller", "tckn")
    op.drop_column("muvekkiller", "organization_id")
