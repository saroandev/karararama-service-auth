"""
Department endpoints.

Departments are system-wide reference data seeded via app/db_seed.py.
There is no organization or user-level partitioning.
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.crud import department_crud
from app.models import User
from app.schemas import DepartmentResponse

router = APIRouter()


@router.get("/", response_model=List[DepartmentResponse])
async def list_departments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """List all departments (alphabetical)."""
    return await department_crud.get_all_ordered(db)
