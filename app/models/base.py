"""
Base model with common fields for all models.
"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, TypeDecorator, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID


class UUID(TypeDecorator):
    """Platform-independent UUID type.
    Uses PostgreSQL's UUID type on PostgreSQL, otherwise uses CHAR(36).
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, str):
                return value
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, str):
                from uuid import UUID as PyUUID
                return PyUUID(value)
            return value


class TimestampMixin:
    """Mixin to add created_at and updated_at fields."""

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class UUIDMixin:
    """Mixin to add UUID primary key."""

    id = Column(
        UUID(),
        primary_key=True,
        default=uuid4,
        unique=True,
        nullable=False
    )