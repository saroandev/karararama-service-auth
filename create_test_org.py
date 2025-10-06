"""
Create a test organization with an admin user.
"""
import asyncio
from sqlalchemy import select
from passlib.context import CryptContext

from app.core.database import AsyncSessionLocal
from app.models import User, Organization, Role

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def create_test_organization():
    """Create test organization with admin user."""
    async with AsyncSessionLocal() as db:
        # Create admin user first
        email = "testorg-admin@example.com"

        # Check if user already exists
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"❌ User already exists: {email}")
            print(f"   User ID: {existing_user.id}")
            return

        # Create new user
        hashed_password = pwd_context.hash("testorg123")
        new_user = User(
            email=email,
            password_hash=hashed_password,
            first_name="Test",
            last_name="Admin",
            is_active=True,
            is_verified=True
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)

        print(f"✅ Created user: {email}")
        print(f"   User ID: {new_user.id}")
        print(f"   Password: testorg123")

        # Create organization
        new_org = Organization(
            name="Test Organization",
            owner_id=new_user.id,
            is_active=True
        )
        db.add(new_org)
        await db.commit()
        await db.refresh(new_org)

        print(f"✅ Created organization: {new_org.name}")
        print(f"   Organization ID: {new_org.id}")

        # Assign organization to user
        new_user.organization_id = new_org.id
        await db.commit()

        # Get admin role
        stmt = select(Role).where(Role.name == "admin")
        result = await db.execute(stmt)
        admin_role = result.scalar_one_or_none()

        if not admin_role:
            print("❌ Admin role not found in database")
            return

        # Assign admin role to user
        new_user.roles.append(admin_role)

        # Update user quotas to match admin role defaults
        new_user.daily_query_limit = admin_role.default_daily_query_limit
        new_user.monthly_query_limit = admin_role.default_monthly_query_limit
        new_user.daily_document_upload_limit = admin_role.default_daily_document_limit
        new_user.max_document_size_mb = admin_role.default_max_document_size_mb

        await db.commit()

        # Update user_roles with organization_id
        from sqlalchemy import text
        update_query = text("""
            UPDATE user_roles
            SET organization_id = :org_id
            WHERE user_id = :user_id AND role_id = :role_id
        """)
        await db.execute(
            update_query,
            {"org_id": new_org.id, "user_id": new_user.id, "role_id": admin_role.id}
        )
        await db.commit()

        print(f"✅ Assigned admin role to user")
        print(f"\n{'='*60}")
        print("Test Organization Created Successfully!")
        print(f"{'='*60}")
        print(f"Organization: {new_org.name}")
        print(f"Admin Email: {email}")
        print(f"Admin Password: testorg123")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(create_test_organization())
