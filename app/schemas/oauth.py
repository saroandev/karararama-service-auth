"""Pydantic schemas for OAuth 2.1 + DCR endpoints.

Field names are intentionally OAuth-spec-canonical (snake_case where the
RFCs use snake_case) so we can parse RFC 7591 / RFC 6749 / RFC 9728 wire
formats verbatim. Don't aliasify these without a strong reason.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


# ---------------------------------------------------------------------------
# DCR (RFC 7591)
# ---------------------------------------------------------------------------

class ClientRegistrationRequest(BaseModel):
    """Body of `POST /api/v1/oauth/register`.

    Public clients only: `token_endpoint_auth_method` must be "none".
    PKCE will be enforced at /oauth/authorize regardless.
    """

    client_name: str = Field(..., min_length=1, max_length=255)
    redirect_uris: List[HttpUrl] = Field(..., min_length=1, max_length=10)
    grant_types: List[Literal["authorization_code", "refresh_token"]] = Field(
        default_factory=lambda: ["authorization_code", "refresh_token"]
    )
    response_types: List[Literal["code"]] = Field(
        default_factory=lambda: ["code"]
    )
    token_endpoint_auth_method: Literal["none"] = "none"
    scope: str = "mcp:search"
    client_uri: Optional[HttpUrl] = None
    logo_uri: Optional[HttpUrl] = None

    @field_validator("redirect_uris")
    @classmethod
    def _https_only(cls, urls: list[HttpUrl]) -> list[HttpUrl]:
        for u in urls:
            scheme = u.scheme if hasattr(u, "scheme") else str(u).split(":", 1)[0]
            if scheme != "https":
                raise ValueError(
                    "redirect_uris must be https://; got: " + str(u)
                )
        return urls


class ClientRegistrationResponse(BaseModel):
    """Response of `POST /api/v1/oauth/register`. Mirrors RFC 7591 §3.2.1."""

    client_id: str
    client_id_issued_at: int
    client_name: str
    client_uri: Optional[str] = None
    logo_uri: Optional[str] = None
    redirect_uris: List[str]
    grant_types: List[str]
    response_types: List[str]
    token_endpoint_auth_method: str
    scope: str


# ---------------------------------------------------------------------------
# Token endpoint (RFC 6749 §3.2, §4.1.3, §6)
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """Successful token response. Same shape for code and refresh grants."""

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    refresh_token: str
    scope: str


class OAuthError(BaseModel):
    """RFC 6749 §5.2 error response."""

    error: str
    error_description: Optional[str] = None
    error_uri: Optional[str] = None


# ---------------------------------------------------------------------------
# Discovery (RFC 8414)
# ---------------------------------------------------------------------------

class AuthorizationServerMetadata(BaseModel):
    """Subset of RFC 8414 metadata we actually emit. Extra fields are fine
    in JSON output (clients should ignore unknowns); we only declare here
    what we want Pydantic to validate-on-build."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    response_types_supported: List[str]
    grant_types_supported: List[str]
    code_challenge_methods_supported: List[str]
    token_endpoint_auth_methods_supported: List[str]
    scopes_supported: List[str]
    service_documentation: Optional[str] = None
