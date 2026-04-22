"""add tebligat, gorev, gorev-kural permissions

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-04-22 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text


revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f6g7h8i9j0k1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (resource, action, description) - 12 entries
PERMISSIONS = [
    # Tebligat
    ("tebligat", "goruntule", "Tebligat görüntüleme"),
    ("tebligat", "senkronize", "Harici tebligat servisinden senkronizasyon (batch, detay, ek yükleme)"),
    ("tebligat", "*", "Tüm tebligat işlemleri"),
    # Görev
    ("gorev", "goruntule", "Görev görüntüleme"),
    ("gorev", "durum-guncelle", "Görev durumunu güncelleme"),
    ("gorev", "atama-ekle", "Göreve atama ekleme"),
    ("gorev", "atama-sil", "Görevden atama silme"),
    ("gorev", "senkronize", "Tebligatlardan görev oluşturma senkronizasyonu"),
    ("gorev", "*", "Tüm görev işlemleri"),
    # Görev-Kural
    ("gorev-kural", "goruntule", "Görev kurallarını görüntüleme"),
    ("gorev-kural", "yonet", "Görev kurallarını yönetme (oluştur/güncelle/sil)"),
    ("gorev-kural", "*", "Tüm görev-kural işlemleri"),
]


# (role_name, resource, action) - 5 entries (minimal assignments per product decision)
ROLE_PERMISSION_ASSIGNMENTS = [
    ("owner", "tebligat", "senkronize"),
    ("owner", "gorev", "senkronize"),
    ("managing-lawyer", "gorev", "durum-guncelle"),
    ("managing-lawyer", "gorev", "atama-ekle"),
    ("managing-lawyer", "gorev", "atama-sil"),
]


def upgrade() -> None:
    conn = op.get_bind()

    insert_permission_sql = text(
        """
        INSERT INTO permissions (id, resource, action, description)
        SELECT gen_random_uuid(), CAST(:resource AS VARCHAR), CAST(:action AS VARCHAR), CAST(:description AS TEXT)
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions
            WHERE resource = CAST(:resource AS VARCHAR)
              AND action = CAST(:action AS VARCHAR)
        )
        """
    )
    for resource, action, description in PERMISSIONS:
        conn.execute(
            insert_permission_sql,
            {"resource": resource, "action": action, "description": description},
        )

    assign_role_permission_sql = text(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = CAST(:role_name AS VARCHAR)
          AND p.resource = CAST(:resource AS VARCHAR)
          AND p.action = CAST(:action AS VARCHAR)
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions rp
              WHERE rp.role_id = r.id AND rp.permission_id = p.id
          )
        """
    )
    for role_name, resource, action in ROLE_PERMISSION_ASSIGNMENTS:
        conn.execute(
            assign_role_permission_sql,
            {"role_name": role_name, "resource": resource, "action": action},
        )


def downgrade() -> None:
    conn = op.get_bind()

    conn.execute(
        text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions
                WHERE resource IN ('tebligat', 'gorev', 'gorev-kural')
            )
            """
        )
    )

    conn.execute(
        text(
            """
            DELETE FROM permissions
            WHERE resource IN ('tebligat', 'gorev', 'gorev-kural')
            """
        )
    )
