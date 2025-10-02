"""
CRUD operations for usage logs.
"""
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.crud.base import CRUDBase
from app.models.usage_log import UsageLog
from app.schemas.usage import UsageConsumeRequest


class CRUDUsage(CRUDBase[UsageLog, UsageConsumeRequest, UsageConsumeRequest]):
    """CRUD operations for usage logs."""

    async def create_usage_log(
        self,
        db: AsyncSession,
        *,
        obj_in: UsageConsumeRequest
    ) -> Optional[UsageLog]:
        """
        Create a new usage log entry.
        Returns None if duplicate entry exists (idempotent behavior).

        Args:
            db: Database session
            obj_in: Usage consumption data

        Returns:
            Created UsageLog instance or None if duplicate
        """
        try:
            usage_log = UsageLog(
                user_id=obj_in.user_id,
                service_type=obj_in.service_type,
                tokens_used=obj_in.tokens_used,
                processing_time=obj_in.processing_time,
                extra_data=obj_in.metadata
            )
            db.add(usage_log)
            await db.commit()
            await db.refresh(usage_log)
            return usage_log
        except IntegrityError:
            # Duplicate entry, rollback and return None
            await db.rollback()
            return None

    async def get_user_daily_usage(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        date: Optional[datetime] = None
    ) -> int:
        """
        Get user's daily usage count.

        Args:
            db: Database session
            user_id: User ID
            date: Date to check (defaults to today)

        Returns:
            Number of queries used today
        """
        if date is None:
            date = datetime.utcnow()

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        result = await db.execute(
            select(func.count(UsageLog.id))
            .where(
                and_(
                    UsageLog.user_id == user_id,
                    UsageLog.created_at >= start_of_day,
                    UsageLog.created_at < end_of_day
                )
            )
        )
        return result.scalar() or 0

    async def get_user_monthly_usage(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        date: Optional[datetime] = None
    ) -> int:
        """
        Get user's monthly usage count.

        Args:
            db: Database session
            user_id: User ID
            date: Date to check (defaults to current month)

        Returns:
            Number of queries used this month
        """
        if date is None:
            date = datetime.utcnow()

        start_of_month = date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if date.month == 12:
            end_of_month = start_of_month.replace(year=date.year + 1, month=1)
        else:
            end_of_month = start_of_month.replace(month=date.month + 1)

        result = await db.execute(
            select(func.count(UsageLog.id))
            .where(
                and_(
                    UsageLog.user_id == user_id,
                    UsageLog.created_at >= start_of_month,
                    UsageLog.created_at < end_of_month
                )
            )
        )
        return result.scalar() or 0

    async def get_user_total_tokens(
        self,
        db: AsyncSession,
        *,
        user_id: UUID
    ) -> int:
        """
        Get user's total tokens used across all time.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            Total tokens used
        """
        result = await db.execute(
            select(func.sum(UsageLog.tokens_used))
            .where(UsageLog.user_id == user_id)
        )
        return result.scalar() or 0

    async def get_user_logs(
        self,
        db: AsyncSession,
        *,
        user_id: UUID,
        skip: int = 0,
        limit: int = 100
    ) -> List[UsageLog]:
        """
        Get user's usage logs with pagination.

        Args:
            db: Database session
            user_id: User ID
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of usage logs
        """
        result = await db.execute(
            select(UsageLog)
            .where(UsageLog.user_id == user_id)
            .order_by(UsageLog.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())


# Global instance
usage_crud = CRUDUsage(UsageLog)
