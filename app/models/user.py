"""
User model for authentication and user management.
"""
from datetime import datetime
from typing import List

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


# Association table for many-to-many relationship between users and roles
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", UUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime, default=datetime.utcnow, nullable=False),
)


class User(Base, UUIDMixin, TimestampMixin):
    """
    User model for authentication and user management.

    Attributes:
        id: Unique user identifier (UUID)
        email: User's email address (unique)
        password_hash: Hashed password
        first_name: User's first name
        last_name: User's last name
        is_active: Whether the user account is active
        is_verified: Whether the user's email is verified
        last_login_at: Last login timestamp
        daily_query_limit: Daily query limit (NULL = unlimited for admins)
        monthly_query_limit: Monthly query limit (NULL = unlimited)
        daily_document_upload_limit: Daily document upload limit
        max_document_size_mb: Maximum document size in MB
        total_queries_used: Total queries used (synced from Redis)
        total_documents_uploaded: Total documents uploaded
        roles: List of roles assigned to this user
        refresh_tokens: List of refresh tokens for this user
    """

    __tablename__ = "users"

    # Basic Information
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)

    # Account Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    # Quota Limits (NULL = unlimited, typically for admins)
    daily_query_limit = Column(Integer, nullable=True)
    monthly_query_limit = Column(Integer, nullable=True)
    daily_document_upload_limit = Column(Integer, nullable=True)
    max_document_size_mb = Column(Integer, default=10, nullable=False)

    # Usage Statistics (synced from Redis periodically)
    total_queries_used = Column(Integer, default=0, nullable=False)
    total_documents_uploaded = Column(Integer, default=0, nullable=False)

    # Relationships
    roles = relationship(
        "Role",
        secondary=user_roles,
        back_populates="users",
        lazy="selectin"
    )
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"

    @property
    def full_name(self) -> str:
        """Return user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.email

    @property
    def has_unlimited_queries(self) -> bool:
        """Check if user has unlimited query quota."""
        return self.daily_query_limit is None