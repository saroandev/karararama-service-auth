"""user_roles org required; personal org per user; drop guest/demo

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-04-22 18:00:00.000000

Data migration + schema change:
- Provision a personal organization for every user missing one.
- Backfill user_roles.organization_id where NULL.
- Drop guest/demo roles along with their user/role links.
- Tighten user_roles: organization_id NOT NULL, PK includes organization_id.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Personal orgs for users without organization_id.
    #    Name: "{first_name} {last_name}" with empty parts stripped; fallback
    #    to "Kişisel Organizasyon" when both are empty.
    op.execute(
        """
        WITH new_orgs AS (
            INSERT INTO organizations (id, name, owner_id, is_active, created_at, updated_at)
            SELECT
                gen_random_uuid(),
                COALESCE(
                    NULLIF(
                        TRIM(BOTH ' ' FROM
                            COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')
                        ),
                        ''
                    ),
                    'Kişisel Organizasyon'
                ),
                u.id,
                TRUE,
                NOW(),
                NOW()
            FROM users u
            WHERE u.organization_id IS NULL
            RETURNING id AS org_id, owner_id
        )
        UPDATE users u
        SET organization_id = no.org_id
        FROM new_orgs no
        WHERE u.id = no.owner_id;
        """
    )

    # 2. Owner membership for every user in their primary organization
    #    (idempotent — skip when membership already exists).
    op.execute(
        """
        INSERT INTO organization_members
            (id, user_id, organization_id, role, is_primary, joined_at, created_at, updated_at)
        SELECT
            gen_random_uuid(), u.id, u.organization_id, 'owner', TRUE, NOW(), NOW(), NOW()
        FROM users u
        WHERE u.organization_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM organization_members om
              WHERE om.user_id = u.id AND om.organization_id = u.organization_id
          );
        """
    )

    # 3. Ensure every org has an 'owner' role entry in user_roles for its owner.
    op.execute(
        """
        INSERT INTO user_roles (user_id, role_id, organization_id)
        SELECT o.owner_id, r.id, o.id
        FROM organizations o
        JOIN roles r ON r.name = 'owner'
        WHERE o.owner_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM user_roles ur
              WHERE ur.user_id = o.owner_id
                AND ur.role_id = r.id
                AND ur.organization_id = o.id
          );
        """
    )

    # 4. Backfill NULL organization_id in existing user_roles rows.
    op.execute(
        """
        UPDATE user_roles ur
        SET organization_id = u.organization_id
        FROM users u
        WHERE ur.user_id = u.id
          AND ur.organization_id IS NULL
          AND u.organization_id IS NOT NULL;
        """
    )

    # 5. Delete remaining NULL rows (shouldn't exist after step 1, defensive).
    op.execute("DELETE FROM user_roles WHERE organization_id IS NULL;")

    # 6. Drop guest/demo user_roles, role_permissions, and roles.
    op.execute(
        """
        DELETE FROM user_roles
        WHERE role_id IN (SELECT id FROM roles WHERE name IN ('guest', 'demo'));
        """
    )
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (SELECT id FROM roles WHERE name IN ('guest', 'demo'));
        """
    )
    op.execute("DELETE FROM roles WHERE name IN ('guest', 'demo');")

    # 7. Tighten schema: NOT NULL + composite PK including organization_id.
    op.alter_column("user_roles", "organization_id", nullable=False)
    op.drop_constraint("user_roles_pkey", "user_roles", type_="primary")
    op.create_primary_key(
        "user_roles_pkey",
        "user_roles",
        ["user_id", "role_id", "organization_id"],
    )


def downgrade() -> None:
    # Restore 2-column PK and relax NOT NULL. Data-level changes (personal
    # orgs, deleted guest/demo roles) are NOT reverted — rollback requires a
    # DB restore from backup.
    op.drop_constraint("user_roles_pkey", "user_roles", type_="primary")
    op.create_primary_key(
        "user_roles_pkey",
        "user_roles",
        ["user_id", "role_id"],
    )
    op.alter_column("user_roles", "organization_id", nullable=True)
