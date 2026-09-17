"""
CyberNexus - Analysis History Router
Phase 6F-3: Authenticated Analysis History Retrieval and Deletion.
"""

from typing import Dict, Any, List, Optional
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Query, status

from backend.services.auth_service import get_current_user_required

logger = logging.getLogger("cybernexus.history")
router = APIRouter(tags=["History"])


@router.get(
    "/history",
    summary="List analysis history",
    description="Returns a paginated list of past analysis sessions belonging to the authenticated user.",
)
def list_user_history(
    request: Request,
    limit: int = Query(50, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    current_user: Dict[str, Any] = Depends(get_current_user_required),
) -> List[Dict[str, Any]]:
    """
    Lists historical analysis sessions strictly owned by the verified token user_id.
    """
    supabase_service = getattr(request.app.state, "supabase", None)
    if not supabase_service or not supabase_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable.",
        )

    user_id = current_user["id"]
    try:
        sessions = supabase_service.get_user_history(user_id=user_id, limit=limit, offset=offset)
        return [
            {
                "analysis_id": s["id"],
                "title": s["title"],
                "channel": s["channel"],
                "created_at": s["created_at"],
                "updated_at": s.get("updated_at"),
            }
            for s in sessions
        ]
    except Exception as e:
        logger.error(f"Error listing history for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis history.",
        )


@router.get(
    "/history/{analysis_id}",
    summary="Get stored analysis detail",
    description="Retrieves a complete stored analysis session with user input, result, explanation, and metadata without re-executing ML inference.",
)
def get_user_analysis_detail(
    analysis_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_required),
) -> Dict[str, Any]:
    """
    Retrieves stored analysis for the authenticated user without rerunning ML.
    Safe ownership semantics: returns 404 if not found or owned by someone else.
    """
    supabase_service = getattr(request.app.state, "supabase", None)
    if not supabase_service or not supabase_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable.",
        )

    user_id = current_user["id"]
    try:
        analysis = supabase_service.get_user_analysis(user_id=user_id, session_id=analysis_id)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis record not found.",
            )
        return analysis
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching analysis {analysis_id} for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analysis record.",
        )


@router.delete(
    "/history/{analysis_id}",
    summary="Delete single analysis",
    description="Deletes an analysis session and cascades to its child messages. Must be owned by authenticated user.",
)
def delete_single_analysis(
    analysis_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_required),
) -> Dict[str, Any]:
    """
    Deletes a single analysis session owned strictly by authenticated user.
    """
    supabase_service = getattr(request.app.state, "supabase", None)
    if not supabase_service or not supabase_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable.",
        )

    user_id = current_user["id"]
    try:
        deleted = supabase_service.delete_user_analysis(user_id=user_id, session_id=analysis_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analysis record not found.",
            )
        return {
            "success": True,
            "message": "Analysis deleted successfully.",
            "analysis_id": analysis_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting analysis {analysis_id} for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete analysis record.",
        )


@router.delete(
    "/history",
    summary="Delete all analysis history",
    description="Deletes all analysis sessions and child messages belonging to the authenticated user.",
)
def delete_all_user_history(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user_required),
) -> Dict[str, Any]:
    """
    Deletes all analysis sessions for the authenticated user without affecting public.users or auth.users.
    """
    supabase_service = getattr(request.app.state, "supabase", None)
    if not supabase_service or not supabase_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is unavailable.",
        )

    user_id = current_user["id"]
    try:
        deleted_count = supabase_service.delete_user_history(user_id=user_id)
        return {
            "success": True,
            "message": "All analysis history deleted successfully.",
            "deleted_count": deleted_count,
        }
    except Exception as e:
        logger.error(f"Error clearing history for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear analysis history.",
        )
