"""
Role listing endpoints for user-facing UI (invite, change-member-role).
"""
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_jwt_payload
from app.core.database import get_db
from app.core.security import JWTPayload
from app.crud import role_crud
from app.schemas import RoleResponse


router = APIRouter()


@router.get("", response_model=List[RoleResponse])
async def list_ui_roles(
    db: AsyncSession = Depends(get_db),
    _: JWTPayload = Depends(get_jwt_payload),
) -> List:
    """
    List roles assignable from the UI (ui_roles=true).

    Filters out system roles (admin, superuser, user, premium). Authenticated
    only — no specific permission required; used by invite and role-change
    dropdowns.
    """
    return await role_crud.get_ui_visible(db)
