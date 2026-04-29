"""iliskili_muvekkiller: case-insensitive unique on (organization_id, unvan, first_name, last_name)

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-04-29 12:00:00.000000

Prevents duplicate related-clients within the same organization where the
tuple (unvan, first_name, last_name) collides case-insensitively. Uses a
functional unique index on lower(first_name) / lower(last_name) so 'Ahmet
Yılmaz' and 'AHMET YILMAZ' clash.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "j0k1l2m3n4o5"
down_revision: Union[str, None] = "i9j0k1l2m3n4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_iliskili_muvekkil_org_unvan_name_ci"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE UNIQUE INDEX {INDEX_NAME}
        ON iliskili_muvekkiller (
            organization_id,
            unvan,
            lower(first_name),
            lower(last_name)
        );
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME};")
