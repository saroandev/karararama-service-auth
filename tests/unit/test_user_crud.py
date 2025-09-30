"""
Unit tests for User CRUD operations.
"""
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.user import user_crud
from app.models import User, Role
from app.schemas import UserCreate, UserUpdate
from app.core.security import password_handler


@pytest.mark.unit
class TestUserCRUD:
    """Test User CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession):
        """Test creating a new user."""
        user_in = UserCreate(
            email="newuser@example.com",
            password="securepassword123",
            first_name="New",
            last_name="User",
        )

        user = await user_crud.create(db_session, obj_in=user_in)

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.first_name == "New"
        assert user.last_name == "User"
        assert user.is_active is True
        assert user.is_verified is False
        # Password should be hashed
        assert user.password_hash != "securepassword123"
        assert password_handler.verify_password("securepassword123", user.password_hash)

    @pytest.mark.asyncio
    async def test_get_user_by_id(self, db_session: AsyncSession, test_user: User):
        """Test getting user by ID."""
        user = await user_crud.get(db_session, id=test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, db_session: AsyncSession):
        """Test getting non-existent user by ID."""
        random_id = uuid4()
        user = await user_crud.get(db_session, id=random_id)

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_by_email(self, db_session: AsyncSession, test_user: User):
        """Test getting user by email."""
        user = await user_crud.get_by_email(db_session, email=test_user.email)

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, db_session: AsyncSession):
        """Test getting non-existent user by email."""
        user = await user_crud.get_by_email(db_session, email="nonexistent@example.com")

        assert user is None

    @pytest.mark.asyncio
    async def test_get_user_with_roles(self, db_session: AsyncSession, test_user: User, test_role: Role):
        """Test getting user with roles loaded."""
        # Add role to user
        test_user.roles.append(test_role)
        db_session.add(test_user)
        await db_session.commit()

        user = await user_crud.get_with_roles(db_session, id=test_user.id)

        assert user is not None
        assert len(user.roles) == 1
        assert user.roles[0].name == test_role.name

    @pytest.mark.asyncio
    async def test_update_user(self, db_session: AsyncSession, test_user: User):
        """Test updating user information."""
        update_data = UserUpdate(
            first_name="Updated",
            last_name="Name",
        )

        updated_user = await user_crud.update(db_session, db_obj=test_user, obj_in=update_data)

        assert updated_user.first_name == "Updated"
        assert updated_user.last_name == "Name"
        assert updated_user.email == test_user.email  # Email unchanged

    @pytest.mark.asyncio
    async def test_delete_user(self, db_session: AsyncSession, test_user: User):
        """Test deleting a user."""
        user_id = test_user.id

        await user_crud.delete(db_session, id=user_id)

        # Verify user is deleted
        deleted_user = await user_crud.get(db_session, id=user_id)
        assert deleted_user is None

    @pytest.mark.asyncio
    async def test_authenticate_success(self, db_session: AsyncSession, test_user: User):
        """Test successful user authentication."""
        user = await user_crud.authenticate(
            db_session,
            email=test_user.email,
            password="testpassword123"
        )

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self, db_session: AsyncSession, test_user: User):
        """Test authentication with wrong password."""
        user = await user_crud.authenticate(
            db_session,
            email=test_user.email,
            password="wrongpassword"
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self, db_session: AsyncSession):
        """Test authentication with non-existent user."""
        user = await user_crud.authenticate(
            db_session,
            email="nonexistent@example.com",
            password="somepassword"
        )

        assert user is None

    @pytest.mark.asyncio
    async def test_update_last_login(self, db_session: AsyncSession, test_user: User):
        """Test updating user's last login timestamp."""
        original_last_login = test_user.last_login_at

        updated_user = await user_crud.update_last_login(db_session, user=test_user)

        assert updated_user.last_login_at is not None
        assert updated_user.last_login_at != original_last_login

    @pytest.mark.asyncio
    async def test_is_active(self, db_session: AsyncSession, test_user: User, inactive_user: User):
        """Test checking if user is active."""
        assert await user_crud.is_active(test_user) is True
        assert await user_crud.is_active(inactive_user) is False

    @pytest.mark.asyncio
    async def test_is_verified(self, db_session: AsyncSession):
        """Test checking if user email is verified."""
        # Create unverified user
        user_in = UserCreate(
            email="unverified@example.com",
            password="password123",
        )
        user = await user_crud.create(db_session, obj_in=user_in)

        assert await user_crud.is_verified(user) is False

        # Verify user
        user.is_verified = True
        db_session.add(user)
        await db_session.commit()

        assert await user_crud.is_verified(user) is True

    @pytest.mark.asyncio
    async def test_add_role(self, db_session: AsyncSession, test_user: User, test_role: Role):
        """Test adding role to user."""
        updated_user = await user_crud.add_role(db_session, user=test_user, role=test_role)

        assert len(updated_user.roles) == 1
        assert updated_user.roles[0].id == test_role.id
        assert updated_user.roles[0].name == test_role.name

    @pytest.mark.asyncio
    async def test_remove_role(self, db_session: AsyncSession, test_user: User, test_role: Role):
        """Test removing role from user."""
        # First add the role
        test_user.roles.append(test_role)
        db_session.add(test_user)
        await db_session.commit()
        await db_session.refresh(test_user)

        assert len(test_user.roles) == 1

        # Now remove it
        updated_user = await user_crud.remove_role(db_session, user=test_user, role=test_role)

        assert len(updated_user.roles) == 0

    @pytest.mark.asyncio
    async def test_get_multi_users(self, db_session: AsyncSession, test_user: User):
        """Test getting multiple users."""
        # Create additional users
        for i in range(3):
            user_in = UserCreate(
                email=f"user{i}@example.com",
                password="password123",
            )
            await user_crud.create(db_session, obj_in=user_in)

        users = await user_crud.get_multi(db_session, skip=0, limit=10)

        assert len(users) >= 4  # test_user + 3 new users

    @pytest.mark.asyncio
    async def test_get_multi_users_with_pagination(self, db_session: AsyncSession):
        """Test getting users with pagination."""
        # Create multiple users
        for i in range(5):
            user_in = UserCreate(
                email=f"pagination{i}@example.com",
                password="password123",
            )
            await user_crud.create(db_session, obj_in=user_in)

        # Get first page
        page1 = await user_crud.get_multi(db_session, skip=0, limit=2)
        assert len(page1) == 2

        # Get second page
        page2 = await user_crud.get_multi(db_session, skip=2, limit=2)
        assert len(page2) == 2

        # Ensure pages are different
        assert page1[0].id != page2[0].id
