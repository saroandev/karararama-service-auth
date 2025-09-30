"""
CRUD operations for Role model.
"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models import Role, Permission
from app.schemas import RoleCreate, RoleUpdate


class CRUDRole(CRUDBase[Role, RoleCreate, RoleUpdate]):
    """CRUD operations for Role model."""

    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str
    ) -> Optional[Role]:
        """
        Get role by name.

        Args:
            db: Database session
            name: Role name

        Returns:
            Role instance or None
        """
        result = await db.execute(
            select(Role)
            .where(Role.name == name)
            .options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def get_with_permissions(
        self,
        db: AsyncSession,
        *,
        id: UUID
    ) -> Optional[Role]:
        """
        Get role with permissions loaded.

        Args:
            db: Database session
            id: Role ID

        Returns:
            Role instance with permissions or None
        """
        result = await db.execute(
            select(Role)
            .where(Role.id == id)
            .options(selectinload(Role.permissions))
        )
        return result.scalar_one_or_none()

    async def add_permission(
        self,
        db: AsyncSession,
        *,
        role: Role,
        permission: Permission
    ) -> Role:
        """
        Add permission to role.

        Args:
            db: Database session
            role: Role instance
            permission: Permission instance

        Returns:
            Updated role instance
        """
        if permission not in role.permissions:
            role.permissions.append(permission)
            db.add(role)
            await db.commit()
            await db.refresh(role)
        return role

    async def remove_permission(
        self,
        db: AsyncSession,
        *,
        role: Role,
        permission: Permission
    ) -> Role:
        """
        Remove permission from role.

        Args:
            db: Database session
            role: Role instance
            permission: Permission instance

        Returns:
            Updated role instance
        """
        if permission in role.permissions:
            role.permissions.remove(permission)
            db.add(role)
            await db.commit()
            await db.refresh(role)
        return role


# Create instance
role_crud = CRUDRole(Role)