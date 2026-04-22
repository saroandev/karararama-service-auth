"""
CRUD operations for User model.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models import Role, User
from app.models.user import user_roles as user_roles_table
from app.schemas import UserCreate, UserUpdate
from app.core.security import password_handler


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    """CRUD operations for User model."""

    async def get_by_email(
        self,
        db: AsyncSession,
        *,
        email: str
    ) -> Optional[User]:
        """
        Get user by email.

        Args:
            db: Database session
            email: User email

        Returns:
            User instance or None
        """
        result = await db.execute(
            select(User)
            .where(User.email == email)
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def get_with_roles(
        self,
        db: AsyncSession,
        *,
        id: UUID
    ) -> Optional[User]:
        """
        Get user with roles loaded.

        Args:
            db: Database session
            id: User ID

        Returns:
            User instance with roles or None
        """
        result = await db.execute(
            select(User)
            .where(User.id == id)
            .options(selectinload(User.roles))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: UserCreate
    ) -> User:
        """
        Create new user with hashed password.

        Role assignment is handled by the register endpoint (personal org + owner)
        or by invitation acceptance flows — this method does not assign any role.
        """
        hashed_password = password_handler.hash_password(obj_in.password)

        user_data = obj_in.model_dump(exclude={"password", "password_confirm", "agree_kvkk", "agree_cookies", "agree_privacy"})
        user_data["password_hash"] = hashed_password

        from datetime import datetime, timedelta
        if obj_in.agree_kvkk:
            user_data["kvkk_consent_at"] = datetime.utcnow()
        if obj_in.agree_cookies:
            user_data["cookie_consent_at"] = datetime.utcnow()
        if obj_in.agree_privacy:
            user_data["privacy_consent_at"] = datetime.utcnow()

        # SaaS plan: new users start with 14-day free trial
        user_data["plan"] = "free_trial"
        user_data["trial_started_at"] = datetime.utcnow()
        user_data["trial_ends_at"] = datetime.utcnow() + timedelta(days=14)

        db_obj = User(**user_data)
        db.add(db_obj)
        await db.flush()
        return db_obj

    async def authenticate(
        self,
        db: AsyncSession,
        *,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate user by email and password.

        Args:
            db: Database session
            email: User email
            password: Plain text password

        Returns:
            User instance if authenticated, None otherwise
        """
        user = await self.get_by_email(db, email=email)
        if not user:
            return None
        if not password_handler.verify_password(password, user.password_hash):
            return None
        return user

    async def update_last_login(
        self,
        db: AsyncSession,
        *,
        user: User
    ) -> User:
        """
        Update user's last login timestamp.

        Args:
            db: Database session
            user: User instance

        Returns:
            Updated user instance
        """
        user.last_login_at = datetime.utcnow()
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def is_active(self, user: User) -> bool:
        """Check if user is active."""
        return user.is_active

    async def is_verified(self, user: User) -> bool:
        """Check if user email is verified."""
        return user.is_verified

    async def add_role(
        self,
        db: AsyncSession,
        *,
        user: User,
        role: Role,
        organization_id: UUID,
    ) -> User:
        """
        Grant role to user scoped to a specific organization.

        Uses an upsert so repeated calls are idempotent. Does not commit —
        caller is responsible for the transaction boundary.
        """
        stmt = (
            pg_insert(user_roles_table)
            .values(user_id=user.id, role_id=role.id, organization_id=organization_id)
            .on_conflict_do_nothing(
                index_elements=["user_id", "role_id", "organization_id"]
            )
        )
        await db.execute(stmt)
        return user

    async def remove_role(
        self,
        db: AsyncSession,
        *,
        user: User,
        role: Role,
        organization_id: UUID,
    ) -> User:
        """
        Revoke role from user in a specific organization.

        Does not commit — caller manages the transaction boundary.
        """
        stmt = delete(user_roles_table).where(
            user_roles_table.c.user_id == user.id,
            user_roles_table.c.role_id == role.id,
            user_roles_table.c.organization_id == organization_id,
        )
        await db.execute(stmt)
        return user


# Create instance
user_crud = CRUDUser(User)
