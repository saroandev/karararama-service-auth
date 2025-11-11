"""
Create a superuser account
"""
import asyncio
from uuid import uuid4
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.role import Role
from app.models.organization import Organization
from app.core.security import PasswordHandler


async def create_superuser():
    """Create superuser account"""
    async with AsyncSessionLocal() as db:
        try:
            # Check if superuser already exists
            result = await db.execute(
                select(User).where(User.email == "superuser@onedocs.com")
            )
            existing_user = result.scalar_one_or_none()

            if existing_user:
                print("❌ Superuser already exists: superuser@onedocs.com")
                return

            # Get default organization
            result = await db.execute(select(Organization).limit(1))
            organization = result.scalar_one_or_none()

            if not organization:
                print("❌ No organization found. Please run db_seed.py first.")
                return

            # Get superuser role
            result = await db.execute(
                select(Role).where(Role.name == "superuser")
            )
            superuser_role = result.scalar_one_or_none()

            if not superuser_role:
                print("❌ Superuser role not found. Please run db_seed.py first.")
                return

            # Create superuser
            password_handler = PasswordHandler()
            hashed_password = password_handler.hash_password("superuser123")

            new_user = User(
                id=uuid4(),
                email="superuser@onedocs.com",
                password_hash=hashed_password,
                first_name="Super",
                last_name="User",
                is_active=True,
                is_verified=True,
                organization_id=organization.id,
                # Unlimited quotas
                daily_query_limit=None,
                monthly_query_limit=None,
                daily_document_upload_limit=None,
                max_document_size_mb=None
            )

            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

            # Assign superuser role
            new_user.roles.append(superuser_role)
            await db.commit()

            print("✅ Superuser created successfully!")
            print(f"   Email: superuser@onedocs.com")
            print(f"   Password: superuser123")
            print(f"   Role: superuser")
            print(f"   Organization: {organization.name}")

        except Exception as e:
            await db.rollback()
            print(f"❌ Error creating superuser: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(create_superuser())
