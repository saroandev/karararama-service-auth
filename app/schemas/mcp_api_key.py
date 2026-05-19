"""Pydantic schemas for the MCP API key endpoints."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class MCPApiKeyCreateRequest(BaseModel):
    """Body for `POST /api/v1/mcp/keys`."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable label for this key (e.g. 'Laptop Claude').",
    )
    expires_at: Optional[datetime] = Field(
        None,
        description=(
            "Optional hard expiry (ISO 8601). Null = never expires. "
            "Recommended: set 90 days for production keys."
        ),
    )


class MCPApiKeyMetadata(BaseModel):
    """Safe-to-display metadata about a key. Never includes the raw secret."""

    id: UUID
    name: str
    key_prefix: str = Field(..., description="First few chars of the raw key, for identification.")
    created_at: datetime
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    usage_count: int = 0
    is_active: bool

    model_config = {"from_attributes": True}


class MCPApiKeyCreateResponse(BaseModel):
    """Response shown ONCE at creation. Contains the raw key — store it now."""

    api_key: str = Field(
        ...,
        description="Raw MCP API key. Shown ONCE — store it securely. Cannot be retrieved later.",
    )
    metadata: MCPApiKeyMetadata


class MCPApiKeyListResponse(BaseModel):
    keys: List[MCPApiKeyMetadata]


class MCPExchangeRequest(BaseModel):
    """Body for `POST /api/v1/mcp/exchange`.

    The MCP server passes the user's API key here and gets a fresh JWT back.
    """

    api_key: str = Field(..., description="The `od_mcp_...` key obtained from `/mcp/keys`.")


class MCPExchangeResponse(BaseModel):
    """Mirrors `TokenResponse` for drop-in interchangeability on the consumer side."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(
        ...,
        description="JWT lifetime in seconds. The MCP server should refresh before expiry.",
    )
