"""
API v1 router.
"""
from fastapi import APIRouter

from app.api.v1 import auth, users, admin, usage, organizations, invitations

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(usage.router, prefix="/usage", tags=["usage"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(invitations.router, prefix="/invitations", tags=["invitations"])