"""
CRUD operations for Permission model.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models import Permission
from app.schemas import PermissionCreate, PermissionUpdate


class CRUDPermission(CRUDBase[Permission, PermissionCreate, PermissionUpdate]):
    """CRUD operations for Permission model."""

    async def get_by_resource_action(
        self,
        db: AsyncSession,
        *,
        resource: str,
        action: str
    ) -> Optional[Permission]:
        """
        Get permission by resource and action.

        Args:
            db: Database session
            resource: Resource name (e.g., 'research', 'documents')
            action: Action name (e.g., 'query', 'upload')

        Returns:
            Permission instance or None
        """
        result = await db.execute(
            select(Permission)
            .where(
                Permission.resource == resource,
                Permission.action == action
            )
        )
        return result.scalar_one_or_none()


# Create instance
permission_crud = CRUDPermission(Permission)