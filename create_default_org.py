"""
Create default organization and assign admin user to it.
Run this script after database setup and seed data.
"""
import asyncio
from uuid import uuid4

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import Organization, User


async def create_default_organization():
    """Create default organization and assign admin to it."""
    async with AsyncSessionLocal() as db:
        # Check if organization already exists
        stmt = select(Organization).where(Organization.name == "OneDocs Organization")
        result = await db.execute(stmt)
        existing_org = result.scalar_one_or_none()

        if existing_org:
            print(f"✓ Default organization already exists: {existing_org.name} ({existing_org.id})")
            org = existing_org
        else:
            # Create default organization
            org = Organization(
                id=uuid4(),
                name="OneDocs Organization",
                is_active=True,
                owner_id=None  # Will be set to admin after admin is created
            )
            db.add(org)
            await db.commit()
            await db.refresh(org)
            print(f"✓ Created default organization: {org.name} ({org.id})")

        # Find admin user
        stmt = select(User).where(User.email == "admin@onedocs.com")
        result = await db.execute(stmt)
        admin_user = result.scalar_one_or_none()

        if admin_user:
            # Assign admin to organization if not already assigned
            if not admin_user.organization_id:
                admin_user.organization_id = org.id
                await db.commit()
                print(f"✓ Assigned admin user to organization")
            else:
                print(f"✓ Admin user already assigned to organization")

            # Set organization owner to admin
            if not org.owner_id:
                org.owner_id = admin_user.id
                await db.commit()
                print(f"✓ Set admin as organization owner")
        else:
            print("⚠ Admin user not found. Please run db_seed.py first.")

        # Clean up old test organizations
        stmt = select(Organization).where(
            Organization.name != "OneDocs Organization"
        )
        result = await db.execute(stmt)
        old_orgs = result.scalars().all()

        if old_orgs:
            for old_org in old_orgs:
                # Remove organization_id from users in this org
                stmt = select(User).where(User.organization_id == old_org.id)
                result = await db.execute(stmt)
                users_in_org = result.scalars().all()

                for user in users_in_org:
                    user.organization_id = None

                # Delete organization
                await db.delete(old_org)

            await db.commit()
            print(f"✓ Cleaned up {len(old_orgs)} old test organizations")

        print("\n✅ Default organization setup complete!")
        print(f"   Organization ID: {org.id}")
        print(f"   Organization Name: {org.name}")
        if admin_user:
            print(f"   Admin Email: {admin_user.email}")


if __name__ == "__main__":
    asyncio.run(create_default_organization())
