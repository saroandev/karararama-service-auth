"""
Usage log model for tracking service usage.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, UUID


class UsageLog(Base, UUIDMixin):
    """
    Usage log model for tracking service usage and consumption.

    Attributes:
        id: Unique log identifier (UUID)
        user_id: User who consumed the service
        service_type: Type of service consumed (ocr_text, ocr_structured, etc.)
        tokens_used: Number of tokens used in the operation
        processing_time: Processing time in seconds
        created_at: When the log was created in our system
        extra_data: Additional metadata (filename, file_size, model, etc.)
    """

    __tablename__ = "usage_logs"

    user_id = Column(UUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    service_type = Column(String(50), nullable=False, index=True)
    tokens_used = Column(Integer, default=0, nullable=False)
    processing_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    extra_data = Column(JSONB, nullable=True)

    # Relationship
    user = relationship("User", foreign_keys=[user_id], lazy="select")

    # Unique constraint to prevent duplicate records
    __table_args__ = (
        UniqueConstraint('user_id', 'created_at', 'service_type', name='uq_usage_log'),
        Index('idx_usage_user_time', 'user_id', 'created_at'),
        Index('idx_usage_service_type', 'service_type'),
    )

    def __repr__(self) -> str:
        return f"<UsageLog(id={self.id}, user_id={self.user_id}, service={self.service_type})>"
