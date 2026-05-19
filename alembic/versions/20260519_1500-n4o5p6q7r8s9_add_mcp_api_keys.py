"""add_mcp_api_keys

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-05-19 15:00:00.000000

Long-lived personal access keys minted by users for the OneDocs MCP server.
The MCP server exchanges these keys for short-lived JWTs at
`/api/v1/mcp/exchange`. Only SHA-256 hashes are stored — raw keys are
returned to the user exactly once at creation time.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'n4o5p6q7r8s9'
down_revision: Union[str, None] = 'm3n4o5p6q7r8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mcp_api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False, unique=True),
        sa.Column('key_prefix', sa.String(20), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('idx_mcp_api_keys_user_id', 'mcp_api_keys', ['user_id'])
    op.create_index('idx_mcp_api_keys_key_hash', 'mcp_api_keys', ['key_hash'], unique=True)


def downgrade() -> None:
    op.drop_index('idx_mcp_api_keys_key_hash', table_name='mcp_api_keys')
    op.drop_index('idx_mcp_api_keys_user_id', table_name='mcp_api_keys')
    op.drop_table('mcp_api_keys')
