"""add_billing_info_discount_codes_payment_extensions

Revision ID: pricing_a1b2c3d4
Revises: loginatt_59e042e5
Create Date: 2026-06-05 14:00:00.000000

PayTR akışını bozmadan paket sistemine fatura bilgisi + indirim kodu +
arşiv add-on ekleyen migration:

  * billing_infos     — org bazlı tek bir kayıt (e-fatura için)
  * discount_codes    — % indirim, opsiyonel max_uses + valid_until
  * discount_code_uses — composite unique (code, user) → kullanıcı bir kodu 1 kere kullanır
  * payments          — addon_archive_gb, discount_*, vat_kurus, billing_info_snapshot
  * payments          — amount_usd ve exchange_rate artık nullable (yeni akışta yok)
  * subscriptions     — addon_archive_gb (toplam storage hesabına eklenir)

Mevcut user'ların trial_ends_at değerine **dokunmuyoruz** — yeni 1 günlük
trial sadece register endpoint'inde uygulanır; eski kullanıcılar 14 günlük
sürelerini tamamlar.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "pricing_a1b2c3d4"
down_revision: Union[str, None] = "loginatt_59e042e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -----------------------------------------------------------------------
    # billing_infos
    # -----------------------------------------------------------------------
    op.create_table(
        "billing_infos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("ad_soyad", sa.String(255), nullable=True),
        sa.Column("tckn", sa.String(11), nullable=True),
        sa.Column("firma", sa.String(255), nullable=True),
        sa.Column("vergi_no", sa.String(20), nullable=True),
        sa.Column("vergi_dairesi", sa.String(120), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("telefon", sa.String(30), nullable=False),
        sa.Column("adres", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_billing_infos_organization_id", "billing_infos", ["organization_id"], unique=True)

    # -----------------------------------------------------------------------
    # discount_codes + discount_code_uses
    # -----------------------------------------------------------------------
    op.create_table(
        "discount_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("percent_off", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column("times_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_discount_codes_code", "discount_codes", ["code"], unique=True)
    op.create_index("ix_discount_codes_is_active", "discount_codes", ["is_active"])

    op.create_table(
        "discount_code_uses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("discount_code_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("discount_codes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("discount_code_id", "user_id", name="uq_discount_code_user"),
    )
    op.create_index("ix_discount_code_uses_discount_code_id", "discount_code_uses", ["discount_code_id"])
    op.create_index("ix_discount_code_uses_user_id", "discount_code_uses", ["user_id"])

    # -----------------------------------------------------------------------
    # payments — yeni sütunlar + amount_usd / exchange_rate nullable
    # -----------------------------------------------------------------------
    op.add_column("payments", sa.Column("addon_archive_gb", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("discount_code", sa.String(40), nullable=True))
    op.add_column("payments", sa.Column("discount_percent", sa.Integer(), nullable=True))
    op.add_column("payments", sa.Column("discount_amount_kurus", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("vat_kurus", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("payments", sa.Column("billing_info_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Yeni akış USD bilgisi tutmuyor; mevcut satırlar için değer korunur.
    op.alter_column("payments", "amount_usd", existing_type=sa.Numeric(10, 2), nullable=True)
    op.alter_column("payments", "exchange_rate", existing_type=sa.Numeric(10, 4), nullable=True)

    # -----------------------------------------------------------------------
    # subscriptions — addon_archive_gb
    # -----------------------------------------------------------------------
    op.add_column(
        "subscriptions",
        sa.Column("addon_archive_gb", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "addon_archive_gb")

    op.alter_column("payments", "exchange_rate", existing_type=sa.Numeric(10, 4), nullable=False)
    op.alter_column("payments", "amount_usd", existing_type=sa.Numeric(10, 2), nullable=False)
    op.drop_column("payments", "billing_info_snapshot")
    op.drop_column("payments", "vat_kurus")
    op.drop_column("payments", "discount_amount_kurus")
    op.drop_column("payments", "discount_percent")
    op.drop_column("payments", "discount_code")
    op.drop_column("payments", "addon_archive_gb")

    op.drop_index("ix_discount_code_uses_user_id", table_name="discount_code_uses")
    op.drop_index("ix_discount_code_uses_discount_code_id", table_name="discount_code_uses")
    op.drop_table("discount_code_uses")

    op.drop_index("ix_discount_codes_is_active", table_name="discount_codes")
    op.drop_index("ix_discount_codes_code", table_name="discount_codes")
    op.drop_table("discount_codes")

    op.drop_index("ix_billing_infos_organization_id", table_name="billing_infos")
    op.drop_table("billing_infos")
