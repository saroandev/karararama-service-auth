"""
List all users with their details (for development/testing).
Shows email, organization, roles - NOT passwords (they're hashed).
"""
import asyncio
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import User


async def list_users():
    """List all users."""
    async with AsyncSessionLocal() as db:
        stmt = select(User).order_by(User.email)
        result = await db.execute(stmt)
        users = result.scalars().all()

        print(f"\n{'='*80}")
        print(f"Total Users: {len(users)}")
        print(f"{'='*80}\n")

        print(f"{'Email':<30} {'Org ID':<38} {'Roles':<20}")
        print(f"{'-'*30} {'-'*38} {'-'*20}")

        for user in users:
            org_id = str(user.organization_id)[:36] if user.organization_id else "NULL"
            roles = ", ".join([r.name for r in user.roles]) if user.roles else "NO ROLE"
            print(f"{user.email:<30} {org_id:<38} {roles:<20}")

        print(f"\n{'='*80}")
        print("Note: Passwords are bcrypt hashed and cannot be reversed.")
        print("Use reset_password.py to change a user's password.")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(list_users())
