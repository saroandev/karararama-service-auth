"""add_organization_slug_and_branding

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-05-30 12:00:00.000000

Adds whitelabel subdomain identifier (`slug`) and branding fields
(`logo_url`, `primary_color`) to organizations.

`slug` is the DNS label used in <slug>.onedocs.ai. It is left nullable in
the schema for now so legacy rows can be backfilled in-place without a
chicken-and-egg problem; this upgrade backfills every existing row from
the organization name using the same normalization rule that the API
applies at write time (see app/core/subdomain.py::slugify). Collisions
are resolved deterministically by appending -2, -3, ... so the result is
reproducible across environments.

Once all environments have run this migration and there are no NULL
slugs, a follow-up migration can flip the column to NOT NULL.
"""
from typing import Sequence, Union

import re
import unicodedata

from alembic import op
import sqlalchemy as sa


revision: str = 'p6q7r8s9t0u1'
down_revision: Union[str, None] = 'o5p6q7r8s9t0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reproduce slugify() locally so the migration does not import app code
# (alembic env executes outside the FastAPI app context, and importing
# app.core would drag in pydantic settings that may not be configured
# during ops runs).
def _slugify(value: str) -> str:
    value = value.replace("ı", "i").replace("İ", "i")
    value = value.replace("ş", "s").replace("Ş", "s")
    value = value.replace("ğ", "g").replace("Ğ", "g")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    hyphenated = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return hyphenated[:63] or "org"


def upgrade() -> None:
    op.add_column(
        'organizations',
        sa.Column('slug', sa.String(length=63), nullable=True),
    )
    op.add_column(
        'organizations',
        sa.Column('logo_url', sa.String(length=500), nullable=True),
    )
    op.add_column(
        'organizations',
        sa.Column('primary_color', sa.String(length=7), nullable=True),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    # Backfill slugs for existing rows. Iterate deterministically by id so
    # collision suffixes (-2, -3, ...) come out the same in every env.
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT id, name FROM organizations ORDER BY id"
    )).fetchall()

    taken: set[str] = set()
    for row in rows:
        base = _slugify(row.name or "")
        candidate = base
        suffix = 2
        while candidate in taken:
            candidate = f"{base}-{suffix}"[:63]
            suffix += 1
        taken.add(candidate)
        bind.execute(
            sa.text("UPDATE organizations SET slug = :slug WHERE id = :id"),
            {"slug": candidate, "id": row.id},
        )


def downgrade() -> None:
    op.drop_index('ix_organizations_slug', table_name='organizations')
    op.drop_column('organizations', 'primary_color')
    op.drop_column('organizations', 'logo_url')
    op.drop_column('organizations', 'slug')
