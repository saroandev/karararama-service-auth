"""
CRUD operations for Department.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate


class CRUDDepartment(CRUDBase[Department, DepartmentCreate, DepartmentUpdate]):
    """CRUD operations for Department."""

    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str
    ) -> Optional[Department]:
        """Get department by name."""
        result = await db.execute(
            select(Department).where(Department.name == name)
        )
        return result.scalar_one_or_none()

    async def get_all_ordered(self, db: AsyncSession) -> List[Department]:
        """Return all departments ordered by name."""
        result = await db.execute(
            select(Department).order_by(Department.name)
        )
        return list(result.scalars().all())


department_crud = CRUDDepartment(Department)
