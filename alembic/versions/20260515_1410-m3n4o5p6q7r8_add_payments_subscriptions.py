"""add_payments_subscriptions

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-05-15 14:10:00.000000

Persist PayTR orders and the resulting active subscriptions. The two
tables intentionally mirror what the JWT/quota path needs at runtime so
we never have to recompute on the read path.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'm3n4o5p6q7r8'
down_revision: Union[str, None] = 'l2m3n4o5p6q7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('merchant_oid', sa.String(64), unique=True, nullable=False),
        sa.Column('plan', sa.String(50), nullable=False),
        sa.Column('billing_cycle', sa.String(20), nullable=False),
        sa.Column('seat_count', sa.Integer(), nullable=False),
        sa.Column('storage_gb_per_user', sa.Numeric(6, 2), nullable=False),
        sa.Column('amount_kurus', sa.BigInteger(), nullable=False),
        sa.Column('amount_usd', sa.Numeric(10, 2), nullable=False),
        sa.Column('exchange_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('currency', sa.String(8), nullable=False, server_default='TRY'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('paytr_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('failed_reason', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_payments_merchant_oid', 'payments', ['merchant_oid'], unique=True)
    op.create_index('ix_payments_user_id', 'payments', ['user_id'])
    op.create_index('ix_payments_organization_id', 'payments', ['organization_id'])
    op.create_index('ix_payments_status', 'payments', ['status'])
    op.create_index('ix_payments_user_status', 'payments', ['user_id', 'status'])
    op.create_index('ix_payments_org_status', 'payments', ['organization_id', 'status'])

    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('payment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('payments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('plan', sa.String(50), nullable=False),
        sa.Column('billing_cycle', sa.String(20), nullable=False),
        sa.Column('seat_count', sa.Integer(), nullable=False),
        sa.Column('storage_gb_per_user', sa.Numeric(6, 2), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_subscriptions_organization_id', 'subscriptions', ['organization_id'])
    op.create_index('ix_subscriptions_started_at', 'subscriptions', ['started_at'])
    op.create_index('ix_subscriptions_expires_at', 'subscriptions', ['expires_at'])
    op.create_index('ix_subscriptions_status', 'subscriptions', ['status'])
    op.create_index('ix_subscriptions_org_status', 'subscriptions', ['organization_id', 'status'])


def downgrade() -> None:
    op.drop_index('ix_subscriptions_org_status', table_name='subscriptions')
    op.drop_index('ix_subscriptions_status', table_name='subscriptions')
    op.drop_index('ix_subscriptions_expires_at', table_name='subscriptions')
    op.drop_index('ix_subscriptions_started_at', table_name='subscriptions')
    op.drop_index('ix_subscriptions_organization_id', table_name='subscriptions')
    op.drop_table('subscriptions')

    op.drop_index('ix_payments_org_status', table_name='payments')
    op.drop_index('ix_payments_user_status', table_name='payments')
    op.drop_index('ix_payments_status', table_name='payments')
    op.drop_index('ix_payments_organization_id', table_name='payments')
    op.drop_index('ix_payments_user_id', table_name='payments')
    op.drop_index('ix_payments_merchant_oid', table_name='payments')
    op.drop_table('payments')
