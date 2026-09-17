"""
CyberNexus - Account Management Router
Phase 6F-3: Authenticated Account Deletion and Cascade Data Cleanup.
"""

from typing import Dict, Any
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, status

from backend.services.auth_service import get_current_user_required

logger = logging.getLogger("cybernexus.account")
router = APIRouter(tags=["Account"])


@router.delete(
    "/account",
    summary="Delete user account and all data",
    description="Permanently deletes the authenticated user's account, Supabase Auth record, and all associated analysis history.",
)
def delete_user_account(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_required),
) -> Dict[str, Any]:
    """
    Permanently deletes user account and all owned application data.
    Strictly derives user identity from verified JWT.
    """
    supabase_service = getattr(request.app.state, "supabase", None)
    if not supabase_service or not supabase_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable.",
        )

    user_id = current_user["id"]
    try:
        # 1. Delete application data (sessions, messages, public.users)
        # Foreign key ON DELETE CASCADE will clean up sessions and messages
        supabase_service.delete_user_application_data(user_id=user_id)
    except Exception as app_err:
        logger.error(f"Application data deletion failed for user {user_id}: {str(app_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user application data.",
        )

    try:
        # 2. Delete Supabase Auth user via admin API
        # FAIL-CLOSED: if Auth deletion fails, do NOT report success
        supabase_service.delete_auth_user(user_id=user_id)
    except Exception as auth_err:
        logger.error(f"Supabase Auth user deletion failed for user {user_id}: {str(auth_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete authentication user record. Account deletion incomplete.",
        )

    return {
        "success": True,
        "message": "Account and all associated data permanently deleted.",
    }
