"""
CRUD operations for User model.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.crud.base import CRUDBase
from app.models import User, Role
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
        Create new user with hashed password and default 'guest' role.

        Args:
            db: Database session
            obj_in: User creation schema

        Returns:
            Created user instance
        """
        # Hash password
        hashed_password = password_handler.hash_password(obj_in.password)

        # Create user dict without password
        user_data = obj_in.model_dump(exclude={"password"})
        user_data["password_hash"] = hashed_password

        db_obj = User(**user_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)

        # Assign default 'guest' role
        result = await db.execute(
            select(Role).where(Role.name == "guest")
        )
        guest_role = result.scalar_one_or_none()

        if guest_role:
            # Reload user with roles relationship
            result = await db.execute(
                select(User)
                .where(User.id == db_obj.id)
                .options(selectinload(User.roles))
            )
            user_with_roles = result.scalar_one()
            user_with_roles.roles.append(guest_role)
            await db.commit()

        # Return user without roles loaded (for response serialization)
        await db.refresh(db_obj)
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
        role
    ) -> User:
        """
        Add role to user. Only adds if not already assigned.

        Args:
            db: Database session
            user: User instance
            role: Role instance

        Returns:
            Updated user instance
        """
        if role not in user.roles:
            user.roles.append(role)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    async def remove_role(
        self,
        db: AsyncSession,
        *,
        user: User,
        role
    ) -> User:
        """
        Remove role from user.

        Args:
            db: Database session
            user: User instance
            role: Role instance

        Returns:
            Updated user instance
        """
        user.roles.remove(role)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


# Create instance
user_crud = CRUDUser(User)