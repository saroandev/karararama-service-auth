"""RFC 8414 OAuth 2.1 authorization server metadata.

Exposed at the well-known path (no `/api/v1` prefix) so the MCP spec
discovery flow can find it directly under the issuer URL:

    GET https://karar-arama-auth-preprod.onedocs.ai/.well-known/oauth-authorization-server

Static, cacheable. Reflects what /api/v1/oauth/* and /oauth/* support.
"""
from fastapi import APIRouter

from app.core.config import settings
from app.schemas.oauth import AuthorizationServerMetadata

router = APIRouter()


@router.get(
    "/.well-known/oauth-authorization-server",
    response_model=AuthorizationServerMetadata,
    summary="OAuth 2.1 Authorization Server Metadata (RFC 8414)",
    include_in_schema=False,
)
async def authorization_server_metadata() -> AuthorizationServerMetadata:
    issuer = settings.OAUTH_ISSUER_URL.rstrip("/")
    return AuthorizationServerMetadata(
        issuer=issuer,
        authorization_endpoint=f"{issuer}/oauth/authorize",
        token_endpoint=f"{issuer}/api/v1/oauth/token",
        registration_endpoint=f"{issuer}/api/v1/oauth/register",
        response_types_supported=["code"],
        grant_types_supported=["authorization_code", "refresh_token"],
        code_challenge_methods_supported=["S256"],
        token_endpoint_auth_methods_supported=["none"],
        scopes_supported=["mcp:search"],
        service_documentation=f"{issuer}/docs",
    )
