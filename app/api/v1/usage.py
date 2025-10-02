"""
Usage tracking endpoints for service consumption.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.crud import user_crud
from app.crud.usage import usage_crud
from app.schemas.usage import UsageConsumeRequest, UsageConsumeResponse, UsageErrorResponse

router = APIRouter()


@router.post("/consume", response_model=UsageConsumeResponse)
async def consume_usage(
    usage_data: UsageConsumeRequest,
    db: AsyncSession = Depends(get_db)
) -> UsageConsumeResponse:
    """
    Record service usage and update user statistics.

    This endpoint is called by OCR service (and other services) to track usage.
    It checks quotas, creates usage log, and updates user statistics.

    Args:
        usage_data: Usage consumption data (user_id, service_type, tokens_used, etc.)
        db: Database session

    Returns:
        Usage consumption response with remaining credits/quotas

    Raises:
        HTTPException 404: User not found
        HTTPException 403: Insufficient credits
        HTTPException 429: Rate limit exceeded
    """
    # 1. Validate user exists
    user = await user_crud.get(db, id=usage_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    # 2. Check daily query limit
    if user.daily_query_limit is not None:
        daily_usage = await usage_crud.get_user_daily_usage(db, user_id=user.id)

        if daily_usage >= user.daily_query_limit:
            # Calculate reset time (midnight UTC)
            now = datetime.utcnow()
            tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "success": False,
                    "error": "Daily query limit exceeded",
                    "daily_limit": user.daily_query_limit,
                    "used_today": daily_usage,
                    "reset_time": tomorrow.isoformat() + "Z"
                }
            )

    # 3. Check monthly query limit
    if user.monthly_query_limit is not None:
        monthly_usage = await usage_crud.get_user_monthly_usage(db, user_id=user.id)

        if monthly_usage >= user.monthly_query_limit:
            # Calculate reset time (first day of next month)
            now = datetime.utcnow()
            if now.month == 12:
                reset_time = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                reset_time = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "success": False,
                    "error": "Monthly query limit exceeded",
                    "monthly_limit": user.monthly_query_limit,
                    "used_this_month": monthly_usage,
                    "reset_time": reset_time.isoformat() + "Z"
                }
            )

    # 4. Create usage log (idempotent - won't create duplicates)
    usage_log = await usage_crud.create_usage_log(db, obj_in=usage_data)

    # Only update user stats if this is a new log (not a duplicate)
    if usage_log:
        # 5. Update user statistics
        update_data = {
            "total_queries_used": user.total_queries_used + 1
        }

        # Update document upload count if it's a file upload operation
        if usage_data.service_type in ["ocr_text_file", "document_process"]:
            update_data["total_documents_uploaded"] = user.total_documents_uploaded + 1

        await user_crud.update(db, db_obj=user, obj_in=update_data)

    # 6. Calculate remaining credits/quotas
    remaining_credits = None
    if user.daily_query_limit is not None:
        current_daily_usage = await usage_crud.get_user_daily_usage(db, user_id=user.id)
        remaining_credits = max(0, user.daily_query_limit - current_daily_usage)

    # 7. Return success response
    return UsageConsumeResponse(
        success=True,
        remaining_credits=remaining_credits,
        credits_consumed=1,
        user_id=user.id,
        message="Usage recorded successfully"
    )


@router.get("/stats/{user_id}")
async def get_user_usage_stats(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get usage statistics for a user.

    Args:
        user_id: User ID (UUID)
        db: Database session

    Returns:
        User usage statistics

    Raises:
        HTTPException 404: User not found
    """
    from uuid import UUID

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )

    user = await user_crud.get(db, id=user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    daily_usage = await usage_crud.get_user_daily_usage(db, user_id=user_uuid)
    monthly_usage = await usage_crud.get_user_monthly_usage(db, user_id=user_uuid)
    total_tokens = await usage_crud.get_user_total_tokens(db, user_id=user_uuid)

    return {
        "user_id": str(user_uuid),
        "daily_usage": {
            "used": daily_usage,
            "limit": user.daily_query_limit,
            "remaining": user.daily_query_limit - daily_usage if user.daily_query_limit else None
        },
        "monthly_usage": {
            "used": monthly_usage,
            "limit": user.monthly_query_limit,
            "remaining": user.monthly_query_limit - monthly_usage if user.monthly_query_limit else None
        },
        "total_stats": {
            "total_queries": user.total_queries_used,
            "total_documents": user.total_documents_uploaded,
            "total_tokens": total_tokens
        }
    }
