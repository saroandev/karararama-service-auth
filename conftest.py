"""
Pytest configuration and shared fixtures for testing.
"""
import asyncio
import os
from typing import AsyncGenerator, Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool, StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.security import jwt_handler, password_handler
from app.models import User, Role, Permission
from app.schemas import UserCreate

# Test database URL - using SQLite for testing
# Use file-based database instead of in-memory to avoid connection issues
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def test_engine():
    """Create a test database engine."""
    # Remove test db file if exists
    if os.path.exists("./test.db"):
        os.remove("./test.db")

    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=StaticPool,
        echo=False,
        connect_args={"check_same_thread": False}
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

    # Clean up test db file
    if os.path.exists("./test.db"):
        os.remove("./test.db")


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[TestClient, None]:
    """Create a test client with overridden database dependency."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        email="test@example.com",
        password_hash=password_handler.hash_password("testpassword123"),
        first_name="Test",
        last_name="User",
        is_active=True,
        is_verified=True,
        daily_query_limit=100,
        monthly_query_limit=1000,
        daily_document_upload_limit=10,
        max_document_size_mb=10,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def inactive_user(db_session: AsyncSession) -> User:
    """Create an inactive test user."""
    user = User(
        id=uuid4(),
        email="inactive@example.com",
        password_hash=password_handler.hash_password("testpassword123"),
        first_name="Inactive",
        last_name="User",
        is_active=False,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_role(db_session: AsyncSession) -> Role:
    """Create a test role."""
    role = Role(
        id=uuid4(),
        name="test_role",
        description="Test role",
        default_daily_query_limit=50,
        default_monthly_query_limit=500,
        default_daily_document_limit=5,
        default_max_document_size_mb=5,
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(role)
    return role


@pytest.fixture
async def admin_role(db_session: AsyncSession) -> Role:
    """Create an admin role with unlimited permissions."""
    role = Role(
        id=uuid4(),
        name="admin",
        description="Administrator role",
        default_daily_query_limit=None,  # Unlimited
        default_monthly_query_limit=None,
        default_daily_document_limit=None,
        default_max_document_size_mb=100,
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(role)
    return role


@pytest.fixture
async def admin_user(db_session: AsyncSession, admin_role: Role) -> User:
    """Create an admin user."""
    user = User(
        id=uuid4(),
        email="admin@example.com",
        password_hash=password_handler.hash_password("adminpassword123"),
        first_name="Admin",
        last_name="User",
        is_active=True,
        is_verified=True,
        daily_query_limit=None,  # Unlimited
        monthly_query_limit=None,
        daily_document_upload_limit=None,
        max_document_size_mb=100,
    )
    user.roles.append(admin_role)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_permission(db_session: AsyncSession, test_role: Role) -> Permission:
    """Create a test permission."""
    permission = Permission(
        id=uuid4(),
        resource="test_resource",
        action="test_action",
        description="Test permission",
    )
    permission.roles.append(test_role)
    db_session.add(permission)
    await db_session.commit()
    await db_session.refresh(permission)
    return permission


@pytest.fixture
def test_access_token(test_user: User) -> str:
    """Generate a test access token."""
    token_data = {
        "sub": str(test_user.id),
        "email": test_user.email,
        "roles": [],
        "permissions": [],
        "quotas": {
            "daily_query_limit": test_user.daily_query_limit,
            "monthly_query_limit": test_user.monthly_query_limit,
            "daily_document_limit": test_user.daily_document_upload_limit,
        }
    }
    return jwt_handler.create_access_token(token_data)


@pytest.fixture
def admin_access_token(admin_user: User) -> str:
    """Generate an admin access token."""
    token_data = {
        "sub": str(admin_user.id),
        "email": admin_user.email,
        "roles": ["admin"],
        "permissions": [],
        "quotas": {
            "daily_query_limit": None,
            "monthly_query_limit": None,
            "daily_document_limit": None,
        }
    }
    return jwt_handler.create_access_token(token_data)


@pytest.fixture
def auth_headers(test_access_token: str) -> dict:
    """Create authorization headers with test token."""
    return {"Authorization": f"Bearer {test_access_token}"}


@pytest.fixture
def admin_auth_headers(admin_access_token: str) -> dict:
    """Create authorization headers with admin token."""
    return {"Authorization": f"Bearer {admin_access_token}"}
