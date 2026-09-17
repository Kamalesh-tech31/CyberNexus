"""
CyberNexus - Authentication & Supabase JWT Verification Service
Phase 6F-2B: Real Google Auth token validation and user identity resolution.

Provides FastAPI dependencies:
- get_current_user_optional: Extracts user identity if valid Authorization Bearer token is provided; returns None for guest requests.
- get_current_user_required: Requires valid Authorization Bearer token; raises HTTP 401 if missing, invalid, or expired.
"""

from typing import Optional, Dict, Any
import os
import logging
import jwt
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("cybernexus.auth")

security_optional = HTTPBearer(auto_error=False)


def get_token_from_header(auth_creds: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    """Extract token string from HTTPAuthorizationCredentials if present."""
    if not auth_creds or not auth_creds.credentials:
        return None
    return auth_creds.credentials.strip()


def verify_supabase_jwt(
    token: str,
    supabase_client: Optional[Any] = None,
    jwt_secret: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cryptographically verifies a Supabase access token (JWT).

    Verification hierarchy:
    1. Primary: Supabase Auth server verification via supabase_client.auth.get_user(token).
       Authoritatively validates signature, expiration, and user status against Supabase.
    2. Fallback: Local cryptographic signature verification with SUPABASE_JWT_SECRET
       using HMAC-SHA256 (HS256) or RS256 with full signature, exp, and sub verification.

    SECURITY ENFORCEMENT:
    - Never accepts unverified or unsigned tokens.
    - Never decodes without verifying cryptographic signatures.
    - Missing or invalid signatures immediately raise HTTP 401.

    Returns:
      {"id": str, "email": Optional[str], "app_metadata": dict, "user_metadata": dict}

    Raises:
      HTTPException(401) on invalid, malformed, forged, or expired token.
    """
    if not token or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clean_token = token.strip()
    secret = jwt_secret or os.getenv("SUPABASE_JWT_SECRET", "")

    # 1. Primary: Authoritative verification via Supabase Auth API
    if supabase_client and hasattr(supabase_client, "auth") and supabase_client.auth:
        try:
            user_response = supabase_client.auth.get_user(clean_token)
            if user_response and getattr(user_response, "user", None):
                sb_user = user_response.user
                user_id = str(sb_user.id)
                if not user_id:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Verified identity missing user ID.",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                return {
                    "id": user_id,
                    "email": getattr(sb_user, "email", None),
                    "user_metadata": getattr(sb_user, "user_metadata", {}) or {},
                    "app_metadata": getattr(sb_user, "app_metadata", {}) or {},
                }
        except HTTPException:
            raise
        except Exception as e:
            err_msg = str(e).lower()
            # If Supabase Auth explicitly rejects the token as invalid or expired
            if any(k in err_msg for k in ["invalid", "expired", "malformed", "jwt", "unauthorized", "signature"]):
                logger.warning(f"Supabase Auth rejected token: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired authorization token.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # Network or connection error reaching Supabase Auth
            logger.warning(f"Supabase auth.get_user connection failed, checking local secret: {str(e)}")

    # 2. Cryptographic local fallback: REQUIRES a configured signing secret
    if secret:
        try:
            payload = jwt.decode(
                clean_token,
                secret,
                algorithms=["HS256", "RS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                },
            )
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing subject claim (sub).",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return {
                "id": str(user_id),
                "email": payload.get("email"),
                "user_metadata": payload.get("user_metadata", {}) or {},
                "app_metadata": payload.get("app_metadata", {}) or {},
            }
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization token has expired.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid authorization token: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 3. If neither Supabase Auth nor local secret verified the token: REJECT
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to cryptographically verify authorization token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_optional(
    request: Request,
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(security_optional)
) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency for endpoints accessible by both Guests and Authenticated users.
    Returns:
      - dict of user data if valid token is provided.
      - None if no token is provided (Guest mode).
    Raises:
      - HTTPException(401) if token is provided but invalid/expired.
    """
    token = get_token_from_header(auth_creds)
    if not token:
        return None

    supabase_service = getattr(request.app.state, "supabase", None)
    client = supabase_service.client if supabase_service else None
    return verify_supabase_jwt(token, client)


async def get_current_user_required(
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
) -> Dict[str, Any]:
    """
    FastAPI dependency for protected endpoints requiring authenticated identity.
    Raises:
      - HTTPException(401) if user is not authenticated.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please sign in with Google.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
