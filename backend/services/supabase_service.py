"""
CyberNexus - Supabase Service Abstraction
Phase 6F-1: Managed Supabase client initialization, connection verification, and database foundation operations.

PLACEHOLDER / TEMPORARY — REPLACED BY REAL AUTH USER ID IN PHASE 6F-5.
"""

from typing import Any, Dict, Optional, List
import logging
from supabase import create_client, Client
from backend.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

logger = logging.getLogger("cybernexus.supabase")

# Stable Placeholder User ID (Section 7)
PLACEHOLDER_USER_ID = "00000000-0000-0000-0000-000000000001"
PLACEHOLDER_USER_EMAIL = "placeholder@cybernexus.local"


class SupabaseConfigError(Exception):
    """Raised when Supabase credentials are missing or invalid."""
    pass


class SupabaseConnectionError(Exception):
    """Raised when database connection or query fails."""
    pass


class SupabaseService:
    """
    Singleton service managing PostgREST communication with Supabase
    using the backend service-role key.
    """

    def __init__(self, url: Optional[str] = None, service_role_key: Optional[str] = None):
        self.url = url if url is not None else SUPABASE_URL
        self.service_role_key = service_role_key if service_role_key is not None else SUPABASE_SERVICE_ROLE_KEY
        self.client: Optional[Client] = None
        self.is_configured: bool = False

        # Safe initialization at startup (Section 15A)
        # FastAPI starts successfully even if Supabase is unconfigured or unreachable.
        if (
            self.url 
            and self.service_role_key 
            and self.url.startswith("http") 
            and "your-project-ref" not in self.url 
            and "example-project" not in self.url
        ):
            try:
                self.client = create_client(self.url, self.service_role_key)
                self.is_configured = True
            except Exception as e:
                logger.warning(f"Supabase client initialization deferred/failed: {str(e)}")
                self.is_configured = False
        else:
            logger.info("Supabase client initialized in unconfigured state (missing/placeholder credentials).")
            self.is_configured = False

    def _ensure_configured(self) -> None:
        """
        Enforces explicit failure at point of database use if Supabase is unconfigured (Section 15A).
        """
        if not self.is_configured or not self.client:
            raise SupabaseConfigError(
                "Supabase is not configured. Please set valid SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables."
            )

    def verify_connection(self) -> bool:
        """
        Verifies database connectivity by executing a lightweight query.
        """
        self._ensure_configured()
        try:
            # Query users table for existence check
            res = self.client.table("users").select("id").limit(1).execute()
            return True
        except Exception as e:
            raise SupabaseConnectionError(f"Failed to connect to Supabase database: {str(e)}")

    def get_placeholder_user(self) -> Dict[str, Any]:
        """
        Retrieves the stable placeholder user identity from the users table.
        PLACEHOLDER / TEMPORARY — REPLACED BY REAL AUTH USER ID IN PHASE 6F-5.
        """
        self._ensure_configured()
        try:
            res = self.client.table("users").select("*").eq("id", PLACEHOLDER_USER_ID).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise SupabaseConnectionError(f"Placeholder user '{PLACEHOLDER_USER_ID}' not found in database.")
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Error fetching placeholder user: {str(e)}")

    def create_test_record(self, user_id: str = PLACEHOLDER_USER_ID, status: str = "test_active") -> Dict[str, Any]:
        """
        Inserts a test record into the analysis_foundation_test table.
        Demonstrates foreign key integrity referencing user_id.
        """
        self._ensure_configured()
        try:
            res = self.client.table("analysis_foundation_test").insert({
                "user_id": user_id,
                "status": status,
            }).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise SupabaseConnectionError("Failed to insert test record into analysis_foundation_test.")
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Database error during insert: {str(e)}")

    def get_test_record(self, record_id: str) -> Dict[str, Any]:
        """
        Retrieves a record from analysis_foundation_test by primary key ID.
        """
        self._ensure_configured()
        try:
            res = self.client.table("analysis_foundation_test").select("*").eq("id", record_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise SupabaseConnectionError(f"Test record '{record_id}' not found.")
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Error fetching test record: {str(e)}")

    def delete_test_record(self, record_id: str) -> bool:
        """
        Deletes a record from analysis_foundation_test by primary key ID.
        """
        self._ensure_configured()
        try:
            res = self.client.table("analysis_foundation_test").delete().eq("id", record_id).execute()
            return True
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Error deleting test record: {str(e)}")

    # ── Phase 6F-3: Production Analysis Persistence & History ────────────────

    def ensure_user_exists(
        self,
        user_id: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Ensures a user record exists in public.users to maintain foreign key integrity.
        Uses idempotent UPSERT on conflict (id).
        """
        self._ensure_configured()
        try:
            user_data = {
                "id": user_id,
                "email": email or f"{user_id}@cybernexus.local",
                "role": "user",
            }
            if display_name:
                user_data["display_name"] = display_name
            res = self.client.table("users").upsert(user_data, on_conflict="id").execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            return user_data
        except Exception as e:
            logger.warning(f"Failed to upsert public.users record for {user_id}: {str(e)}")
            # If already exists or RLS prevents upsert, verify existence
            try:
                check = self.client.table("users").select("id").eq("id", user_id).limit(1).execute()
                if check.data and len(check.data) > 0:
                    return check.data[0]
            except Exception:
                pass
            raise SupabaseConnectionError(f"Unable to ensure user profile exists: {str(e)}")

    def create_analysis_session(
        self,
        user_id: str,
        channel: str,
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a persistent analysis session row owned strictly by the verified user_id.
        Enforces allowed channel check ('sms', 'email', 'url', 'qr').
        """
        self._ensure_configured()
        valid_channels = {"sms", "email", "url", "qr"}
        channel_clean = channel.lower().strip()
        if channel_clean not in valid_channels:
            raise ValueError(f"Invalid channel '{channel}'. Allowed: {valid_channels}")

        clean_title = (title or "New Security Analysis").strip()[:100]

        try:
            res = self.client.table("analysis_sessions").insert({
                "user_id": user_id,
                "channel": channel_clean,
                "title": clean_title,
            }).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise SupabaseConnectionError("Failed to insert session: empty response from database.")
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError, ValueError)):
                raise e
            raise SupabaseConnectionError(f"Database error creating analysis session: {str(e)}")

    def create_analysis_message(
        self,
        session_id: str,
        role: str,
        input_data: Optional[Dict[str, Any]] = None,
        result: Optional[Dict[str, Any]] = None,
        explanation: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Creates an analysis message row linked to a session.
        Roles allowed: 'user', 'assistant'.
        """
        self._ensure_configured()
        if role not in ("user", "assistant"):
            raise ValueError(f"Invalid role '{role}'. Allowed: 'user', 'assistant'.")

        try:
            payload = {
                "session_id": session_id,
                "role": role,
                "input": input_data or {},
                "result": result or {},
                "explanation": explanation or {},
                "metadata": metadata or {},
            }
            res = self.client.table("analysis_messages").insert(payload).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
            raise SupabaseConnectionError("Failed to insert message: empty response from database.")
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError, ValueError)):
                raise e
            raise SupabaseConnectionError(f"Database error creating analysis message: {str(e)}")

    def get_user_history(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Lists all analysis sessions belonging to the verified user_id, sorted newest first.
        Strictly enforces user isolation by filtering on user_id.
        """
        self._ensure_configured()
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)

        try:
            res = (
                self.client.table("analysis_sessions")
                .select("id, title, channel, created_at, updated_at")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(safe_offset, safe_offset + safe_limit - 1)
                .execute()
            )
            return res.data or []
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Database error fetching user history: {str(e)}")

    def get_user_analysis(
        self,
        user_id: str,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves a complete stored analysis session with its messages for the verified user_id.
        Returns None if session does not exist OR does not belong to user_id (safe ownership).
        Does NOT re-execute ML inference.
        """
        self._ensure_configured()
        try:
            # 1. Verify ownership & fetch session
            session_res = (
                self.client.table("analysis_sessions")
                .select("*")
                .eq("id", session_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if not session_res.data or len(session_res.data) == 0:
                return None

            session = session_res.data[0]

            # 2. Fetch associated messages in chronological order
            messages_res = (
                self.client.table("analysis_messages")
                .select("*")
                .eq("session_id", session_id)
                .order("created_at", desc=False)
                .execute()
            )
            messages = messages_res.data or []

            # Reconstruct stored user input and assistant response
            user_msg = next((m for m in messages if m.get("role") == "user"), None)
            assistant_msg = next((m for m in messages if m.get("role") == "assistant"), None)

            return {
                "analysis_id": session["id"],
                "session_id": session["id"],
                "user_id": session["user_id"],
                "title": session["title"],
                "channel": session["channel"],
                "created_at": session["created_at"],
                "updated_at": session.get("updated_at"),
                "input": user_msg.get("input", {}) if user_msg else {},
                "result": assistant_msg.get("result", {}) if assistant_msg else {},
                "explanation": assistant_msg.get("explanation", {}) if assistant_msg else {},
                "metadata": assistant_msg.get("metadata", {}) if assistant_msg else {},
                "messages": messages,
            }
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Database error retrieving user analysis: {str(e)}")

    def delete_user_analysis(
        self,
        user_id: str,
        session_id: str,
    ) -> bool:
        """
        Deletes a single analysis session owned strictly by verified user_id.
        Cascades deletion to child analysis_messages via database FK ON DELETE CASCADE.
        Returns True if deleted, False if not found or not owned.
        """
        self._ensure_configured()
        try:
            # First check ownership to return accurate status
            check = (
                self.client.table("analysis_sessions")
                .select("id")
                .eq("id", session_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if not check.data or len(check.data) == 0:
                return False

            res = (
                self.client.table("analysis_sessions")
                .delete()
                .eq("id", session_id)
                .eq("user_id", user_id)
                .execute()
            )
            return True
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Database error deleting analysis session: {str(e)}")

    def delete_user_history(self, user_id: str) -> int:
        """
        Deletes all analysis sessions owned by verified user_id.
        Child analysis_messages cascade delete automatically.
        Does NOT delete public.users or auth.users.
        Returns count of deleted sessions.
        """
        self._ensure_configured()
        try:
            res = (
                self.client.table("analysis_sessions")
                .delete()
                .eq("user_id", user_id)
                .execute()
            )
            return len(res.data) if res.data else 0
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Database error deleting user history: {str(e)}")

    def delete_user_application_data(self, user_id: str) -> bool:
        """
        Deletes user record from public.users.
        Database FK ON DELETE CASCADE cascades to analysis_sessions and analysis_messages.
        """
        self._ensure_configured()
        try:
            res = self.client.table("users").delete().eq("id", user_id).execute()
            return True
        except Exception as e:
            if isinstance(e, (SupabaseConfigError, SupabaseConnectionError)):
                raise e
            raise SupabaseConnectionError(f"Database error deleting user application data: {str(e)}")

    def delete_auth_user(self, user_id: str) -> bool:
        """
        Deletes the user from Supabase Auth using the privileged admin API.
        Foreign key constraint cascades to public.users and all analysis records.
        """
        self._ensure_configured()
        if not hasattr(self.client, "auth") or not hasattr(self.client.auth, "admin"):
            raise SupabaseConnectionError("Supabase admin auth API is not available on client.")
        try:
            self.client.auth.admin.delete_user(user_id)
            return True
        except Exception as e:
            raise SupabaseConnectionError(f"Supabase Admin API failed to delete user: {str(e)}")
