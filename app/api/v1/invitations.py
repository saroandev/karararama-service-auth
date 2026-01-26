"""
Invitation management endpoints.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.crud import invitation_crud, user_crud, role_crud
from app.models import User, Invitation
from app.schemas import InvitationPublicResponse
from app.models.invitation import InvitationStatus

router = APIRouter()


@router.get("/accept/{token}", response_model=InvitationPublicResponse)
async def accept_invitation(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Accept an invitation by token (PUBLIC endpoint - no auth required).

    If user with email exists:
        - Assigns organization and role from invitation
        - Marks invitation as accepted
        - Returns invitation details

    If user doesn't exist:
        - Returns invitation details with redirect instruction
        - Frontend should redirect to /register?invitation_token={token}

    Args:
        token: Invitation token (UUID string)
        db: Database session

    Returns:
        Public invitation details

    Raises:
        HTTPException: If token invalid, expired, or already used
    """
    # Get invitation by token
    invitation = await invitation_crud.get_by_token(db, token=token)

    if not invitation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Geçersiz davet tokeni"
        )

    # Check if invitation is valid (pending and not expired)
    if not invitation.is_valid:
        if invitation.status == InvitationStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu davet zaten kabul edilmiş"
            )
        elif invitation.status == InvitationStatus.EXPIRED or invitation.is_expired:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu davetin süresi dolmuş"
            )
        elif invitation.status == InvitationStatus.REVOKED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bu davet iptal edilmiş"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Geçersiz davet durumu"
            )

    # Check if user with this email already exists
    user = await user_crud.get_by_email(db, email=invitation.email)

    if user:
        # User exists - assign organization and role
        # Load user with roles
        stmt = select(User).where(User.id == user.id).options(selectinload(User.roles))
        result = await db.execute(stmt)
        user_with_roles = result.scalar_one()

        # Update user's organization
        user_with_roles.organization_id = invitation.organization_id
        db.add(user_with_roles)
        await db.commit()

        # Get the role from invitation
        role = await role_crud.get_by_name(db, name=invitation.role)
        if role:
            # Remove guest role if exists
            guest_roles = [r for r in user_with_roles.roles if r.name.lower() == "guest"]
            for guest_role in guest_roles:
                await user_crud.remove_role(db, user=user_with_roles, role=guest_role)

            # Add new role
            await user_crud.add_role(db, user=user_with_roles, role=role)

        # Mark invitation as accepted
        await invitation_crud.mark_accepted(db, invitation=invitation)

        print(f"✅ Davet kabul edildi:")
        print(f"   User: {user.email}")
        print(f"   Organization ID: {invitation.organization_id}")
        print(f"   Role: {invitation.role}")

        # Return public invitation details
        return InvitationPublicResponse(
            email=invitation.email,
            organization_id=invitation.organization_id,
            role=invitation.role,
            status=InvitationStatus.ACCEPTED,
            expires_at=invitation.expires_at
        )
    else:
        # User doesn't exist - return invitation details for registration
        print(f"ℹ️  Kullanıcı bulunamadı, kayıt sayfasına yönlendirilmeli:")
        print(f"   Email: {invitation.email}")
        print(f"   Token: {token}")
        print(f"   Redirect to: /register?invitation_token={token}")

        # Return invitation details (status still pending, frontend will handle redirect)
        return InvitationPublicResponse(
            email=invitation.email,
            organization_id=invitation.organization_id,
            role=invitation.role,
            status=invitation.status,
            expires_at=invitation.expires_at
        )
