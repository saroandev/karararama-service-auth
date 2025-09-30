"""
Role model for role-based access control (RBAC).
"""
from datetime import datetime
from typing import List

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


# Association table for many-to-many relationship between roles and permissions
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", UUID(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    Column("granted_at", DateTime, default=datetime.utcnow, nullable=False),
)


class Role(Base, UUIDMixin, TimestampMixin):
    """
    Role model for defining user roles and their default quotas.

    Attributes:
        id: Unique role identifier (UUID)
        name: Role name (e.g., 'admin', 'user', 'demo', 'guest')
        description: Role description
        default_daily_query_limit: Default daily query limit for this role
        default_monthly_query_limit: Default monthly query limit
        default_daily_document_limit: Default daily document upload limit
        default_max_document_size_mb: Default max document size in MB
        permissions: List of permissions assigned to this role
        users: List of users with this role
    """

    __tablename__ = "roles"

    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Default Quota Limits for this role (NULL = unlimited)
    default_daily_query_limit = Column(Integer, nullable=True)
    default_monthly_query_limit = Column(Integer, nullable=True)
    default_daily_document_limit = Column(Integer, nullable=True)
    default_max_document_size_mb = Column(Integer, default=10, nullable=False)

    # Relationships
    permissions = relationship(
        "Permission",
        secondary=role_permissions,
        back_populates="roles",
        lazy="selectin"
    )
    users = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name})>"

    @property
    def is_admin(self) -> bool:
        """Check if this is an admin role."""
        return self.name.lower() == "admin"