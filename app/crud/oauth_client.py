"""CRUD for OAuth clients registered via DCR."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_client import OAuthClient


class CRUDOAuthClient:
    """OAuth 2.1 client lifecycle (DCR + lookup + revoke)."""

    async def create(
        self,
        db: AsyncSession,
        *,
        client_id: str,
        client_name: str,
        redirect_uris: list[str],
        grant_types: list[str],
        response_types: list[str],
        scope: str,
        token_endpoint_auth_method: str = "none",
        client_uri: Optional[str] = None,
        logo_uri: Optional[str] = None,
    ) -> OAuthClient:
        row = OAuthClient(
            client_id=client_id,
            client_name=client_name,
            client_uri=client_uri,
            logo_uri=logo_uri,
            redirect_uris=redirect_uris,
            grant_types=grant_types,
            response_types=response_types,
            scope=scope,
            token_endpoint_auth_method=token_endpoint_auth_method,
            is_active=True,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return row

    async def get_by_client_id(
        self, db: AsyncSession, client_id: str
    ) -> Optional[OAuthClient]:
        """Look up an active client by its public identifier."""
        result = await db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, db: AsyncSession, client_id: str) -> bool:
        """Soft-delete a client. Returns False if it doesn't exist / already off."""
        row = await self.get_by_client_id(db, client_id)
        if row is None:
            return False
        row.is_active = False
        await db.commit()
        return True


oauth_client_crud = CRUDOAuthClient()
