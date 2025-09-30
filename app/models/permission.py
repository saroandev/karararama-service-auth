"""
Permission model for fine-grained access control.
"""
from typing import List

from sqlalchemy import Column, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Permission(Base, UUIDMixin, TimestampMixin):
    """
    Permission model for defining granular permissions.

    Attributes:
        id: Unique permission identifier (UUID)
        resource: Resource name (e.g., 'research', 'documents', 'users')
        action: Action name (e.g., 'query', 'upload', 'read', 'update', 'delete')
        description: Permission description
        roles: List of roles that have this permission
    """

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint('resource', 'action', name='_resource_action_uc'),
    )

    resource = Column(String(100), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    description = Column(Text, nullable=True)

    # Relationships
    roles = relationship(
        "Role",
        secondary="role_permissions",
        back_populates="permissions",
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, resource={self.resource}, action={self.action})>"

    @property
    def name(self) -> str:
        """Return permission name in format 'resource:action'."""
        return f"{self.resource}:{self.action}"