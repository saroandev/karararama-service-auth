"""
Assign role to a user.
"""
import asyncio
from uuid import UUID

from app.core.database import AsyncSessionLocal
from app.crud import user_crud, role_crud


async def assign_role_to_user(user_email: str, role_name: str):
    """Assign a role to a user."""
    async with AsyncSessionLocal() as db:
        # Get user
        user = await user_crud.get_by_email(db, email=user_email)
        if not user:
            print(f"❌ User not found: {user_email}")
            return

        # Get role
        role = await role_crud.get_by_name(db, name=role_name)
        if not role:
            print(f"❌ Role not found: {role_name}")
            return

        # Get user with roles
        user_with_roles = await user_crud.get_with_roles(db, id=user.id)

        # Check if already has role
        if role in user_with_roles.roles:
            print(f"⏭️  User {user_email} already has role {role_name}")
            return

        # Add role
        await user_crud.add_role(db, user=user_with_roles, role=role)

        # Update user quotas based on role defaults
        await user_crud.update(db, db_obj=user, obj_in={
            "daily_query_limit": role.default_daily_query_limit,
            "monthly_query_limit": role.default_monthly_query_limit,
            "daily_document_upload_limit": role.default_daily_document_limit,
            "max_document_size_mb": role.default_max_document_size_mb,
        })

        print(f"✅ Assigned role '{role_name}' to user '{user_email}'")
        print(f"   Quotas updated:")
        print(f"   - Daily query limit: {role.default_daily_query_limit}")
        print(f"   - Monthly query limit: {role.default_monthly_query_limit}")
        print(f"   - Daily document limit: {role.default_daily_document_limit}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python assign_role.py <user_email> <role_name>")
        print("Example: python assign_role.py admin@example.com admin")
        sys.exit(1)

    user_email = sys.argv[1]
    role_name = sys.argv[2]

    asyncio.run(assign_role_to_user(user_email, role_name))