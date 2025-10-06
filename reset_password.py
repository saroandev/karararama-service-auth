"""
Reset user password manually (for development/testing).
Usage: python3 reset_password.py <email> <new_password>
"""
import asyncio
import sys
from sqlalchemy import select
from passlib.context import CryptContext

from app.core.database import AsyncSessionLocal
from app.models import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def reset_password(email: str, new_password: str):
    """Reset user password."""
    async with AsyncSessionLocal() as db:
        # Find user
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            print(f"❌ User not found: {email}")
            return

        # Hash new password
        hashed = pwd_context.hash(new_password)
        user.password_hash = hashed

        await db.commit()

        print(f"✅ Password reset successful!")
        print(f"   Email: {email}")
        print(f"   New Password: {new_password}")
        print(f"   Hash: {hashed[:50]}...")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 reset_password.py <email> <new_password>")
        print("Example: python3 reset_password.py newtest@example.com NewPass123")
        sys.exit(1)

    email = sys.argv[1]
    new_password = sys.argv[2]

    asyncio.run(reset_password(email, new_password))
