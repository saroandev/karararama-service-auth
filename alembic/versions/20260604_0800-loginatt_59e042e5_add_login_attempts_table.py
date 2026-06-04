"""add_login_attempts_table

Revision ID: loginatt_59e042e5
Revises: p6q7r8s9t0u1
Create Date: 2026-06-04 08:00:00.000000

Tracks every login attempt (success or failure) so the auth service can
enforce progressive brute-force protection per the policy below.

Policy (enforced by future CRUD + login endpoint changes, NOT this
migration — this revision only provisions the storage):

  Window         | Failed attempts | Action
  ---------------|-----------------|----------------------------------
  last 15 min    |       3-5       | require CAPTCHA (HTTP 428)
  last 1 hour    |       6-9       | 15-min cooldown (HTTP 429)
  last 24 hours  |       10+       | 24-hour account lock (HTTP 423)

Two axes are evaluated independently and the stricter outcome wins:
  - per-email   → defends against account-targeted brute force
  - per-ip      → defends against password spray (many emails, one pass)

Lockout reset paths:
  - successful /reset-password (mail link) → counters cleared
  - admin unlock endpoint                  → counters cleared
  - 24 hours of inactivity                 → window naturally expires

Composite indexes (email, created_at) and (ip_address, created_at) keep
the windowed lookup queries cheap as the table grows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'loginatt_59e042e5'
down_revision: Union[str, None] = 'p6q7r8s9t0u1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'login_attempts',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        # IPv6 max representation = 45 chars; nullable because trust-proxy
        # parsing may fail behind a misconfigured load balancer and we
        # would rather record the attempt than drop it.
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        # 'bad_password' | 'unknown_email' | 'inactive' | 'unverified'
        # | 'locked' | 'captcha_required' | 'cooldown'
        sa.Column('failure_reason', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_login_attempts_email_created_at',
        'login_attempts',
        ['email', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_login_attempts_ip_created_at',
        'login_attempts',
        ['ip_address', 'created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_login_attempts_ip_created_at', table_name='login_attempts')
    op.drop_index('ix_login_attempts_email_created_at', table_name='login_attempts')
    op.drop_table('login_attempts')
