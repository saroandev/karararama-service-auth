"""
Sync organization_id in user_roles table with users table.
Updates all user_roles records to match their user's organization_id.
"""
import asyncio
from sqlalchemy import text

from app.core.database import AsyncSessionLocal


async def sync_user_roles_organization():
    """Sync organization_id in user_roles from users table."""
    async with AsyncSessionLocal() as db:
        # Update user_roles.organization_id to match users.organization_id
        update_query = text("""
            UPDATE user_roles
            SET organization_id = users.organization_id
            FROM users
            WHERE user_roles.user_id = users.id
        """)

        result = await db.execute(update_query)
        await db.commit()

        print(f"✅ Synced organization_id for {result.rowcount} user_roles records")


if __name__ == "__main__":
    asyncio.run(sync_user_roles_organization())
