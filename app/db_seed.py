"""
Database seeding script for roles and permissions.
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.crud import role_crud, permission_crud
from app.schemas import RoleCreate, PermissionCreate


async def seed_permissions(db: AsyncSession):
    """Seed permissions into database."""
    permissions_data = [
        # Research permissions
        ("research", "query", "LLM sorgusu gönderme"),
        ("research", "history", "Sorgu geçmişini görüntüleme"),

        # Document permissions
        ("documents", "upload", "Belge yükleme"),
        ("documents", "read", "Belgeleri görüntüleme"),
        ("documents", "delete", "Belge silme"),

        # User permissions
        ("users", "read", "Kullanıcı bilgilerini görüntüleme"),
        ("users", "update", "Kullanıcı bilgilerini güncelleme"),
        ("users", "delete", "Kullanıcı silme"),

        # Admin permissions
        ("admin", "*", "Tüm admin işlemleri"),
    ]

    permissions = {}
    for resource, action, description in permissions_data:
        # Check if permission already exists
        existing = await permission_crud.get_by_resource_action(
            db, resource=resource, action=action
        )
        if not existing:
            perm_in = PermissionCreate(
                resource=resource,
                action=action,
                description=description
            )
            perm = await permission_crud.create(db, obj_in=perm_in)
            permissions[f"{resource}:{action}"] = perm
            print(f"✅ Created permission: {resource}:{action}")
        else:
            permissions[f"{resource}:{action}"] = existing
            print(f"⏭️  Permission already exists: {resource}:{action}")

    return permissions


async def seed_roles(db: AsyncSession, permissions: dict):
    """Seed roles into database."""
    roles_data = [
        {
            "name": "admin",
            "description": "Admin kullanıcı - sınırsız erişim",
            "default_daily_query_limit": None,  # Sınırsız
            "default_monthly_query_limit": None,
            "default_daily_document_limit": None,
            "default_max_document_size_mb": 100,
            "permissions": ["admin:*"]  # Admin has all permissions
        },
        {
            "name": "user",
            "description": "Normal kullanıcı",
            "default_daily_query_limit": 100,
            "default_monthly_query_limit": 3000,
            "default_daily_document_limit": 50,
            "default_max_document_size_mb": 10,
            "permissions": [
                "research:query",
                "research:history",
                "documents:upload",
                "documents:read",
                "documents:delete",
                "users:read",
                "users:update",
            ]
        },
        {
            "name": "demo",
            "description": "Demo kullanıcı - sınırlı erişim",
            "default_daily_query_limit": 10,  # Günde 10 sorgu
            "default_monthly_query_limit": 200,
            "default_daily_document_limit": 5,
            "default_max_document_size_mb": 5,
            "permissions": [
                "research:query",
                "research:history",
                "documents:upload",
                "documents:read",
                "users:read",
            ]
        },
        {
            "name": "guest",
            "description": "Misafir kullanıcı - çok sınırlı",
            "default_daily_query_limit": 3,  # Günde 3 sorgu
            "default_monthly_query_limit": 30,
            "default_daily_document_limit": 0,  # Belge yükleyemez
            "default_max_document_size_mb": 0,
            "permissions": [
                "research:query",
            ]
        },
    ]

    for role_data in roles_data:
        # Check if role already exists
        existing_role = await role_crud.get_by_name(db, name=role_data["name"])

        if not existing_role:
            # Create role
            role_in = RoleCreate(
                name=role_data["name"],
                description=role_data["description"],
                default_daily_query_limit=role_data["default_daily_query_limit"],
                default_monthly_query_limit=role_data["default_monthly_query_limit"],
                default_daily_document_limit=role_data["default_daily_document_limit"],
                default_max_document_size_mb=role_data["default_max_document_size_mb"],
            )
            role = await role_crud.create(db, obj_in=role_in)
            print(f"✅ Created role: {role.name}")
        else:
            role = existing_role
            print(f"⏭️  Role already exists: {role.name}")

        # Add permissions to role
        role_with_perms = await role_crud.get_with_permissions(db, id=role.id)
        for perm_key in role_data["permissions"]:
            if perm_key in permissions:
                perm = permissions[perm_key]
                if perm not in role_with_perms.permissions:
                    await role_crud.add_permission(db, role=role_with_perms, permission=perm)
                    print(f"  ➕ Added permission {perm_key} to {role.name}")


async def seed_database():
    """Main seeding function."""
    print("🌱 Starting database seeding...")

    async with AsyncSessionLocal() as db:
        try:
            # Seed permissions first
            print("\n📋 Seeding permissions...")
            permissions = await seed_permissions(db)

            # Then seed roles with permissions
            print("\n👥 Seeding roles...")
            await seed_roles(db, permissions)

            print("\n✅ Database seeding completed successfully!")

        except Exception as e:
            print(f"\n❌ Error during seeding: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed_database())