"""
CRUD operations for database models.
"""
from app.crud.user import CRUDUser, user_crud
from app.crud.role import CRUDRole, role_crud
from app.crud.permission import CRUDPermission, permission_crud

__all__ = [
    "CRUDUser",
    "user_crud",
    "CRUDRole",
    "role_crud",
    "CRUDPermission",
    "permission_crud",
]