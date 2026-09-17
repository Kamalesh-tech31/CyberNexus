"""
CyberNexus - FastAPI Application Entry Point
Phase 6F-1: Application setup with CORS middleware, lifespan MLService and SupabaseService initialization, and healthcheck.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

from backend.config import API_TITLE, API_VERSION, API_DESCRIPTION, ALLOWED_ORIGINS
from backend.schemas import HealthResponse
from backend.routers.analysis import router as analysis_router
from backend.routers.history import router as history_router
from backend.routers.account import router as account_router
from backend.services.ml_service import MLService
from backend.services.supabase_service import SupabaseService
from backend.services.auth_service import get_current_user_required


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Context Manager.
    Initializes MLService and SupabaseService once at application startup
    and stores them in app.state for request handlers.
    FastAPI starts successfully even if Supabase is unconfigured or unreachable.
    """
    app.state.ml_service = MLService()
    app.state.supabase = SupabaseService()
    yield
    # Clean up state on shutdown if necessary
    app.state.ml_service = None
    app.state.supabase = None


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    lifespan=lifespan,
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Healthcheck Endpoint
@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health_check() -> HealthResponse:
    """
    Healthcheck endpoint to verify API server availability.
    """
    return HealthResponse(status="ok", version=API_VERSION)

# Auth Verification Endpoint
@app.get("/api/auth/me", tags=["Auth"])
def get_authenticated_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user_required)
) -> Dict[str, Any]:
    """
    Returns the authenticated user's verified identity extracted strictly from Supabase JWT.
    """
    return {
        "id": current_user["id"],
        "email": current_user.get("email"),
        "authenticated": True,
    }

# Include Routers
app.include_router(analysis_router, prefix="/api")
app.include_router(history_router, prefix="/api")
app.include_router(account_router, prefix="/api")
