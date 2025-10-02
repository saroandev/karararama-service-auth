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
        # Authentication permissions
        ("auth", "login", "Giriş yapma"),
        ("auth", "logout", "Çıkış yapma"),
        ("auth", "register", "Kayıt olma"),
        ("auth", "reset_password", "Şifre sıfırlama"),
        ("auth", "verify_email", "Email doğrulama"),
        ("auth", "refresh_token", "Token yenileme"),
        ("auth", "manage_2fa", "2FA yönetimi"),
        ("auth", "*", "Tüm auth işlemleri"),

        # User profile permissions
        ("users", "read", "Kullanıcı bilgilerini görüntüleme"),
        ("users", "update", "Kullanıcı bilgilerini güncelleme"),
        ("users", "delete", "Kullanıcı silme"),
        ("users", "change_password", "Şifre değiştirme"),
        ("users", "upload_avatar", "Avatar yükleme"),
        ("users", "manage_notifications", "Bildirim tercihlerini yönetme"),
        ("users", "manage_api_keys", "API key yönetimi"),
        ("users", "*", "Tüm user işlemleri"),

        # Document permissions
        ("documents", "upload", "Belge yükleme"),
        ("documents", "read", "Belgeleri görüntüleme"),
        ("documents", "delete", "Belge silme"),
        ("documents", "update", "Belge güncelleme"),
        ("documents", "download", "Belge indirme"),
        ("documents", "share", "Belge paylaşma"),
        ("documents", "tag", "Belge etiketleme"),
        ("documents", "search", "Belge arama"),
        ("documents", "edit_metadata", "Meta veri düzenleme"),
        ("documents", "bulk_operations", "Toplu işlemler"),
        ("documents", "manage_versions", "Versiyon yönetimi"),
        ("documents", "*", "Tüm document işlemleri"),

        # Research/Query permissions
        ("research", "query", "Sorgu gönderme"),
        ("research", "history", "Geçmiş görüntüleme"),
        ("research", "save", "Sorgu kaydetme"),
        ("research", "delete_saved", "Kayıtlı sorgu silme"),
        ("research", "export", "Sonuç dışa aktarma"),
        ("research", "advanced_search", "Gelişmiş arama"),
        ("research", "create_templates", "Şablon oluşturma"),
        ("research", "*", "Tüm research işlemleri"),

        # Usage & Analytics permissions
        ("usage", "view_own", "Kendi kullanımını görüntüleme"),
        ("usage", "view_tokens", "Token kullanımı görüntüleme"),
        ("usage", "view_quotas", "Kota bilgilerini görüntüleme"),
        ("usage", "export_reports", "Rapor dışa aktarma"),
        ("usage", "*", "Tüm usage işlemleri"),

        # Billing permissions
        ("billing", "view", "Fatura görüntüleme"),
        ("billing", "view_plan", "Plan görüntüleme"),
        ("billing", "change_plan", "Plan değiştirme"),
        ("billing", "manage_payment", "Ödeme yöntemi yönetme"),
        ("billing", "download_invoices", "Fatura indirme"),
        ("billing", "cancel_subscription", "Abonelik iptali"),
        ("billing", "*", "Tüm billing işlemleri"),

        # Notifications permissions
        ("notifications", "read", "Bildirimleri görüntüleme"),
        ("notifications", "mark_read", "Okundu işaretleme"),
        ("notifications", "delete", "Bildirim silme"),
        ("notifications", "manage_preferences", "Tercihleri yönetme"),
        ("notifications", "*", "Tüm notification işlemleri"),

        # Workspace permissions
        ("workspaces", "create", "Workspace oluşturma"),
        ("workspaces", "invite", "Üye davet etme"),
        ("workspaces", "remove_member", "Üye çıkarma"),
        ("workspaces", "delete", "Workspace silme"),
        ("workspaces", "manage_settings", "Ayarları yönetme"),
        ("workspaces", "*", "Tüm workspace işlemleri"),

        # Sharing permissions
        ("sharing", "create", "Paylaşım oluşturma"),
        ("sharing", "revoke", "Paylaşımı iptal etme"),
        ("sharing", "manage_permissions", "İzinleri yönetme"),
        ("sharing", "*", "Tüm sharing işlemleri"),

        # Comments permissions
        ("comments", "create", "Yorum yapma"),
        ("comments", "update", "Yorum güncelleme"),
        ("comments", "delete", "Yorum silme"),
        ("comments", "*", "Tüm comment işlemleri"),

        # Integrations permissions
        ("integrations", "view", "Entegrasyonları görüntüleme"),
        ("integrations", "create", "Entegrasyon ekleme"),
        ("integrations", "delete", "Entegrasyon silme"),
        ("integrations", "manage_webhooks", "Webhook yönetimi"),
        ("integrations", "manage_oauth", "OAuth yönetimi"),
        ("integrations", "*", "Tüm integration işlemleri"),

        # Data management permissions
        ("data", "export", "Veri dışa aktarma"),
        ("data", "import", "Veri içe aktarma"),
        ("data", "backup", "Veri yedekleme"),
        ("data", "request_deletion", "Veri silme talebi (GDPR)"),
        ("data", "*", "Tüm data işlemleri"),

        # Security permissions
        ("security", "view_sessions", "Oturumları görüntüleme"),
        ("security", "terminate_sessions", "Oturumları sonlandırma"),
        ("security", "view_login_history", "Giriş geçmişi"),
        ("security", "manage_2fa", "2FA yönetimi"),
        ("security", "view_audit_logs", "Güvenlik logları"),
        ("security", "*", "Tüm security işlemleri"),

        # Admin permissions
        ("admin", "view_users", "Tüm kullanıcıları görüntüleme"),
        ("admin", "manage_users", "Kullanıcı yönetimi"),
        ("admin", "manage_roles", "Rol yönetimi"),
        ("admin", "manage_permissions", "İzin yönetimi"),
        ("admin", "manage_settings", "Sistem ayarları"),
        ("admin", "view_logs", "Sistem logları"),
        ("admin", "view_analytics", "Kullanım istatistikleri"),
        ("admin", "bulk_operations", "Toplu işlemler"),
        ("admin", "maintenance", "Sistem bakımı"),
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
            "permissions": [
                "admin:*",
                "auth:*",
                "users:*",
                "documents:*",
                "research:*",
                "usage:*",
                "billing:*",
                "notifications:*",
                "workspaces:*",
                "sharing:*",
                "comments:*",
                "integrations:*",
                "data:*",
                "security:*"
            ]  # Admin has all permissions
        },
        {
            "name": "premium",
            "description": "Premium kullanıcı - gelişmiş özellikler",
            "default_daily_query_limit": 500,
            "default_monthly_query_limit": 15000,
            "default_daily_document_limit": 200,
            "default_max_document_size_mb": 50,
            "permissions": [
                # Auth
                "auth:login", "auth:logout", "auth:reset_password", "auth:manage_2fa",
                # Users
                "users:read", "users:update", "users:change_password", "users:upload_avatar",
                "users:manage_notifications", "users:manage_api_keys",
                # Documents - Full access
                "documents:upload", "documents:read", "documents:update", "documents:delete",
                "documents:download", "documents:share", "documents:tag", "documents:search",
                "documents:edit_metadata", "documents:bulk_operations", "documents:manage_versions",
                # Research - Full access
                "research:query", "research:history", "research:save", "research:delete_saved",
                "research:export", "research:advanced_search", "research:create_templates",
                # Usage
                "usage:view_own", "usage:view_tokens", "usage:view_quotas", "usage:export_reports",
                # Billing
                "billing:view", "billing:view_plan", "billing:change_plan",
                "billing:manage_payment", "billing:download_invoices",
                # Notifications
                "notifications:read", "notifications:mark_read", "notifications:delete",
                "notifications:manage_preferences",
                # Workspaces
                "workspaces:create", "workspaces:invite", "workspaces:remove_member",
                "workspaces:delete", "workspaces:manage_settings",
                # Sharing
                "sharing:create", "sharing:revoke", "sharing:manage_permissions",
                # Comments
                "comments:create", "comments:update", "comments:delete",
                # Integrations
                "integrations:view", "integrations:create", "integrations:delete",
                "integrations:manage_webhooks", "integrations:manage_oauth",
                # Data
                "data:export", "data:import", "data:backup", "data:request_deletion",
                # Security
                "security:view_sessions", "security:terminate_sessions",
                "security:view_login_history", "security:manage_2fa"
            ]
        },
        {
            "name": "user",
            "description": "Normal kullanıcı - standart özellikler",
            "default_daily_query_limit": 100,
            "default_monthly_query_limit": 3000,
            "default_daily_document_limit": 50,
            "default_max_document_size_mb": 10,
            "permissions": [
                # Auth
                "auth:login", "auth:logout", "auth:reset_password",
                # Users
                "users:read", "users:update", "users:change_password", "users:upload_avatar",
                "users:manage_notifications",
                # Documents - Basic operations
                "documents:upload", "documents:read", "documents:update", "documents:delete",
                "documents:download", "documents:search", "documents:tag",
                # Research - Basic
                "research:query", "research:history", "research:save", "research:delete_saved",
                # Usage
                "usage:view_own", "usage:view_tokens", "usage:view_quotas",
                # Billing
                "billing:view", "billing:view_plan", "billing:change_plan",
                # Notifications
                "notifications:read", "notifications:mark_read", "notifications:delete",
                "notifications:manage_preferences",
                # Sharing - Basic
                "sharing:create", "sharing:revoke",
                # Comments
                "comments:create", "comments:update", "comments:delete",
                # Data
                "data:export", "data:request_deletion",
                # Security
                "security:view_sessions", "security:terminate_sessions", "security:view_login_history"
            ]
        },
        {
            "name": "demo",
            "description": "Demo kullanıcı - sınırlı erişim",
            "default_daily_query_limit": 10,
            "default_monthly_query_limit": 200,
            "default_daily_document_limit": 5,
            "default_max_document_size_mb": 5,
            "permissions": [
                # Auth
                "auth:login", "auth:logout",
                # Users - Read only
                "users:read",
                # Documents - Limited
                "documents:upload", "documents:read", "documents:search",
                # Research - Limited
                "research:query", "research:history",
                # Usage
                "usage:view_own", "usage:view_quotas",
                # Notifications
                "notifications:read", "notifications:mark_read"
            ]
        },
        {
            "name": "guest",
            "description": "Misafir kullanıcı - çok sınırlı",
            "default_daily_query_limit": 3,
            "default_monthly_query_limit": 30,
            "default_daily_document_limit": 0,
            "default_max_document_size_mb": 0,
            "permissions": [
                # Auth
                "auth:login", "auth:logout",
                # Users - Read only
                "users:read",
                # Research - Only query
                "research:query",
                # Usage
                "usage:view_own"
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