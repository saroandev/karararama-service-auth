"""add_oauth_tables

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-05-20 10:00:00.000000

OAuth 2.1 + Dynamic Client Registration provider tables.

Three tables, all needed for the spec-correct flow used by claude.ai web
custom MCP connectors:

- oauth_clients: clients registered via RFC 7591 DCR (one row per Claude
  connector or similar OAuth-aware client).
- oauth_authorization_codes: very short-lived (60s), single-use codes
  emitted by /oauth/authorize and redeemed at /oauth/token.
- oauth_refresh_tokens: long-lived (30d), rotating refresh tokens
  emitted alongside access tokens.

All credentials are stored hashed (SHA-256). Raw tokens are returned to
the client exactly once, same pattern as mcp_api_keys.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'o5p6q7r8s9t0'
down_revision: Union[str, None] = 'n4o5p6q7r8s9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- oauth_clients ----
    op.create_table(
        'oauth_clients',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('client_id', sa.String(80), nullable=False, unique=True),
        sa.Column('client_name', sa.String(255), nullable=False),
        sa.Column('client_uri', sa.String(500), nullable=True),
        sa.Column('logo_uri', sa.String(500), nullable=True),
        # JSONB array of redirect URIs; Claude.ai sends one or more.
        sa.Column('redirect_uris', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False),
        sa.Column('token_endpoint_auth_method', sa.String(32), nullable=False,
                  server_default='none'),
        sa.Column('grant_types', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False),
        sa.Column('response_types', postgresql.JSONB(astext_type=sa.Text()),
                  nullable=False),
        sa.Column('scope', sa.String(500), nullable=False,
                  server_default='mcp:search'),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    op.create_index('ix_oauth_clients_client_id', 'oauth_clients',
                    ['client_id'], unique=True)
    op.create_index('ix_oauth_clients_is_active', 'oauth_clients',
                    ['is_active'])

    # ---- oauth_authorization_codes ----
    # Single-use; consumed atomically at /oauth/token. SHA-256 hash stored
    # so a DB leak doesn't leak usable codes (codes are also expired in 60s
    # but defense-in-depth costs us nothing).
    op.create_table(
        'oauth_authorization_codes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('code_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('client_id', sa.String(80), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('redirect_uri', sa.String(500), nullable=False),
        sa.Column('code_challenge', sa.String(128), nullable=False),
        sa.Column('code_challenge_method', sa.String(8), nullable=False,
                  server_default='S256'),
        sa.Column('scope', sa.String(500), nullable=False),
        # RFC 8707 — must match resource server URI (mcp.onedocs.ai)
        sa.Column('resource', sa.String(500), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    op.create_index('ix_oauth_auth_codes_hash',
                    'oauth_authorization_codes', ['code_hash'], unique=True)
    op.create_index('ix_oauth_auth_codes_expires_at',
                    'oauth_authorization_codes', ['expires_at'])

    # ---- oauth_refresh_tokens ----
    # Rotating: each successful refresh_token grant marks the old token
    # revoked and issues a new one. SHA-256 hash stored.
    op.create_table(
        'oauth_refresh_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('token_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('client_id', sa.String(80), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('users.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('scope', sa.String(500), nullable=False),
        sa.Column('resource', sa.String(500), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('NOW()')),
    )
    op.create_index('ix_oauth_refresh_token_hash',
                    'oauth_refresh_tokens', ['token_hash'], unique=True)
    op.create_index('ix_oauth_refresh_user_client',
                    'oauth_refresh_tokens', ['user_id', 'client_id'])
    op.create_index('ix_oauth_refresh_expires_at',
                    'oauth_refresh_tokens', ['expires_at'])


def downgrade() -> None:
    op.drop_index('ix_oauth_refresh_expires_at', table_name='oauth_refresh_tokens')
    op.drop_index('ix_oauth_refresh_user_client', table_name='oauth_refresh_tokens')
    op.drop_index('ix_oauth_refresh_token_hash', table_name='oauth_refresh_tokens')
    op.drop_table('oauth_refresh_tokens')

    op.drop_index('ix_oauth_auth_codes_expires_at',
                  table_name='oauth_authorization_codes')
    op.drop_index('ix_oauth_auth_codes_hash',
                  table_name='oauth_authorization_codes')
    op.drop_table('oauth_authorization_codes')

    op.drop_index('ix_oauth_clients_is_active', table_name='oauth_clients')
    op.drop_index('ix_oauth_clients_client_id', table_name='oauth_clients')
    op.drop_table('oauth_clients')
