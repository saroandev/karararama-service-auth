"""
MCP API key endpoints.

Two-step flow:

1. `POST /mcp/keys`  (auth: user JWT)
       Mints a long-lived `od_mcp_...` key for the logged-in user. The raw
       key is shown ONCE in the response and never stored in plaintext.

2. `POST /mcp/exchange`  (auth: the raw API key itself)
       The OneDocs MCP server posts the user's key here and gets back a
       short-lived JWT, equivalent to what `/auth/login` produces. The MCP
       server then uses that JWT to call GlobalDB.

Plus management:
- `GET /mcp/keys`        list active keys (metadata only — no secrets)
- `DELETE /mcp/keys/{id}` revoke (soft-delete)
"""
from datetime import timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.core.security import jwt_handler
from app.core.config import settings
from app.crud.mcp_api_key import mcp_api_key_crud
from app.models import User
from app.schemas.mcp_api_key import (
    MCPApiKeyCreateRequest,
    MCPApiKeyCreateResponse,
    MCPApiKeyListResponse,
    MCPApiKeyMetadata,
    MCPExchangeRequest,
    MCPExchangeResponse,
)
from app.services.token_service import build_user_token_payload

router = APIRouter()

# Max active keys a single user may hold concurrently. Soft cap to bound DoS.
MAX_KEYS_PER_USER = 10

# Short TTL for JWTs minted via the exchange endpoint. API keys are
# long-lived, so the JWT they yield should be short — limits blast radius
# if the token leaks. The MCP server caches and re-exchanges before expiry.
MCP_JWT_TTL_MINUTES = 15


def _to_metadata(row) -> MCPApiKeyMetadata:
    return MCPApiKeyMetadata(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        last_used_at=row.last_used_at,
        usage_count=row.usage_count or 0,
        is_active=row.is_active,
    )


@router.post(
    "/keys",
    response_model=MCPApiKeyCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new MCP API key for the current user",
)
async def create_mcp_api_key(
    body: MCPApiKeyCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MCPApiKeyCreateResponse:
    """Mint a new MCP API key. The raw value is returned ONCE — store it now."""
    active_count = await mcp_api_key_crud.count_active_for_user(db, current_user.id)
    if active_count >= MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Aktif MCP anahtarı sayısı sınıra ulaştı ({MAX_KEYS_PER_USER}). "
                "Yeni anahtar oluşturmak için kullanılmayanları iptal edin."
            ),
        )

    key_row, raw_key = await mcp_api_key_crud.create(
        db,
        user_id=current_user.id,
        name=body.name,
        expires_at=body.expires_at,
    )
    return MCPApiKeyCreateResponse(
        api_key=raw_key,
        metadata=_to_metadata(key_row),
    )


@router.get(
    "/keys",
    response_model=MCPApiKeyListResponse,
    summary="List the current user's MCP API keys",
)
async def list_mcp_api_keys(
    include_revoked: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MCPApiKeyListResponse:
    rows = await mcp_api_key_crud.list_for_user(
        db, current_user.id, include_revoked=include_revoked
    )
    return MCPApiKeyListResponse(keys=[_to_metadata(r) for r in rows])


@router.delete(
    "/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke (soft-delete) an MCP API key",
)
async def revoke_mcp_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    ok = await mcp_api_key_crud.revoke(db, user_id=current_user.id, key_id=key_id)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Anahtar bulunamadı veya zaten iptal edilmiş.",
        )


@router.post(
    "/exchange",
    response_model=MCPExchangeResponse,
    summary="Exchange an MCP API key for a short-lived JWT",
)
async def exchange_mcp_api_key(
    body: MCPExchangeRequest,
    db: AsyncSession = Depends(get_db),
) -> MCPExchangeResponse:
    """Validate the API key and mint a fresh JWT for the underlying user.

    The JWT TTL is intentionally short ({MCP_JWT_TTL_MINUTES} min) — the MCP
    server is expected to cache it briefly and re-exchange before expiry.
    """
    key_row = await mcp_api_key_crud.get_by_raw_key(db, body.api_key)
    if key_row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz MCP API anahtarı.",
        )
    if key_row.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bu anahtar iptal edilmiş.",
        )
    if key_row.is_expired:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bu anahtarın süresi dolmuş.",
        )

    # Load the owning user fresh — plan/permissions may have changed since
    # the key was minted, and the JWT must reflect *current* state.
    from sqlalchemy import select

    from app.models import User as UserModel

    result = await db.execute(select(UserModel).where(UserModel.id == key_row.user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Anahtar sahibi kullanıcı pasif veya silinmiş.",
        )

    token_data = await build_user_token_payload(db, user)
    access_token = jwt_handler.create_access_token(
        token_data,
        expires_delta=timedelta(minutes=MCP_JWT_TTL_MINUTES),
    )

    await mcp_api_key_crud.touch(db, key_row)

    return MCPExchangeResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=MCP_JWT_TTL_MINUTES * 60,
    )
