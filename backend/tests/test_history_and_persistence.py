"""
CyberNexus - Phase 6F-3 History, Persistence, and Ownership Unit Tests
Tests covering:
- Guest analysis no-write behavior across all channels
- Authenticated analysis persistence (session, user message, assistant message)
- Explainability and metadata preservation in stored records
- Safe ownership isolation (users cannot view or delete another's records)
- History retrieval without ML re-execution
- History deletion (single and all)
- Account deletion with cascade cleanup
- Compensating rollback on persistence failure
"""

import unittest
import asyncio
import json
from unittest.mock import MagicMock, patch

from backend.app import app, lifespan
from backend.services.supabase_service import SupabaseService


class TestHistoryAndPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lifespan_ctx = lifespan(app)
        asyncio.run(cls.lifespan_ctx.__aenter__())

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.lifespan_ctx.__aexit__(None, None, None))

    @staticmethod
    def _call_api(path: str, method: str = "POST", json_body: dict = None, token: str = None):
        """Helper to invoke ASGI app directly with optional Bearer token."""
        body_bytes = json.dumps(json_body or {}).encode("utf-8") if json_body is not None else b""
        headers = [
            (b"host", b"localhost:8000"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body_bytes)).encode("utf-8")),
        ]
        if token:
            headers.append((b"authorization", f"Bearer {token}".encode("utf-8")))

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": headers,
            "app": app,
        }
        status_code = None
        resp_headers = []
        response_chunks = []

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        async def send(message):
            nonlocal status_code, resp_headers, response_chunks
            if message["type"] == "http.response.start":
                status_code = message["status"]
                resp_headers = message["headers"]
            elif message["type"] == "http.response.body":
                response_chunks.append(message.get("body", b""))

        asyncio.run(app(scope, receive, send))
        raw_body = b"".join(response_chunks).decode("utf-8")
        try:
            data = json.loads(raw_body)
        except Exception:
            data = raw_body
        return status_code, data

    # ── 1. GUEST MODE: ZERO WRITES TO DATABASE ──────────────────────────────

    def test_01_guest_sms_analysis_no_database_writes(self):
        """Guest SMS analysis returns result with schema_version, analysis_id=None, and 0 DB writes."""
        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        app.state.supabase = mock_supabase

        status, data = self._call_api("/api/analyze", json_body={
            "channel": "sms",
            "input": "Urgent: Your account is locked. Text BACK to verify."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "sms")
        self.assertEqual(data["schema_version"], "1.0")
        self.assertIsNone(data.get("analysis_id"))
        mock_supabase.create_analysis_session.assert_not_called()
        mock_supabase.create_analysis_message.assert_not_called()

    def test_02_guest_email_analysis_no_database_writes(self):
        """Guest Email analysis returns result with schema_version, analysis_id=None, and 0 DB writes."""
        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        app.state.supabase = mock_supabase

        status, data = self._call_api("/api/analyze", json_body={
            "channel": "email",
            "subject": "Account Notice",
            "input": "Dear customer, please review the attached document immediately."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "email")
        self.assertEqual(data["schema_version"], "1.0")
        self.assertIsNone(data.get("analysis_id"))
        mock_supabase.create_analysis_session.assert_not_called()

    def test_03_guest_url_analysis_no_database_writes(self):
        """Guest URL analysis returns result with schema_version, analysis_id=None, and 0 DB writes."""
        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        app.state.supabase = mock_supabase

        status, data = self._call_api("/api/analyze", json_body={
            "channel": "url",
            "input": "https://google.com"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "url")
        self.assertEqual(data["schema_version"], "1.0")
        self.assertIsNone(data.get("analysis_id"))
        mock_supabase.create_analysis_session.assert_not_called()

    def test_04_guest_autodetect_analysis_no_database_writes(self):
        """Guest Auto Detect analysis performs ML, detects channel, and does 0 DB writes."""
        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        app.state.supabase = mock_supabase

        status, data = self._call_api("/api/analyze", json_body={
            "channel": "auto",
            "input": "https://apple.com"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["resolved_channel"], "url")
        self.assertEqual(data["schema_version"], "1.0")
        self.assertIsNone(data.get("analysis_id"))
        mock_supabase.create_analysis_session.assert_not_called()

    # ── 2. AUTHENTICATED PERSISTENCE ────────────────────────────────────────

    @patch("backend.routers.analysis.get_current_user_optional")
    def test_05_authenticated_sms_analysis_persists_session_and_messages(self, mock_auth):
        """Authenticated SMS analysis creates session, user message, and assistant message with full explainability."""
        user_id = "user-1111-2222-3333-4444"
        mock_auth.return_value = {"id": user_id, "email": "alice@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.create_analysis_session.return_value = {
            "id": "session-sms-001",
            "user_id": user_id,
            "channel": "sms",
            "title": "Urgent Security Alert",
            "created_at": "2026-09-13T22:00:00Z",
        }
        app.state.supabase = mock_supabase

        # We must override FastAPI dependency in app
        from backend.services.auth_service import get_current_user_optional
        app.dependency_overrides[get_current_user_optional] = lambda: {"id": user_id, "email": "alice@example.com"}

        try:
            status, data = self._call_api("/api/analyze", json_body={
                "channel": "sms",
                "input": "Urgent: Your account is locked. Verify at http://scam.ru"
            }, token="valid-mock-token")
            self.assertEqual(status, 200)
            self.assertEqual(data["analysis_id"], "session-sms-001")
            self.assertEqual(data["created_at"], "2026-09-13T22:00:00Z")
            self.assertEqual(data["schema_version"], "1.0")

            # Check DB calls
            mock_supabase.create_analysis_session.assert_called_once()
            self.assertEqual(mock_supabase.create_analysis_message.call_count, 2)
            # User message
            call_user = mock_supabase.create_analysis_message.call_args_list[0]
            self.assertEqual(call_user[1]["role"], "user")
            # Assistant message
            call_assistant = mock_supabase.create_analysis_message.call_args_list[1]
            self.assertEqual(call_assistant[1]["role"], "assistant")
            self.assertIn("prediction", call_assistant[1]["result"])
            self.assertIn("tier3", call_assistant[1]["explanation"])
        finally:
            app.dependency_overrides.pop(get_current_user_optional, None)

    # ── 3. HISTORY API & OWNERSHIP ISOLATION ─────────────────────────────────

    def test_06_guest_history_endpoints_rejected_with_401(self):
        """Guests accessing history or account endpoints are rejected with HTTP 401."""
        status1, _ = self._call_api("/api/history", method="GET")
        self.assertEqual(status1, 401)

        status2, _ = self._call_api("/api/history/some-id", method="GET")
        self.assertEqual(status2, 401)

        status3, _ = self._call_api("/api/history/some-id", method="DELETE")
        self.assertEqual(status3, 401)

        status4, _ = self._call_api("/api/history", method="DELETE")
        self.assertEqual(status4, 401)

        status5, _ = self._call_api("/api/account", method="DELETE")
        self.assertEqual(status5, 401)

    def test_07_authenticated_list_history(self):
        """Authenticated user lists their own analysis history."""
        user_id = "user-auth-123"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "test@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.get_user_history.return_value = [
            {"id": "sess-1", "title": "Phishing Analysis", "channel": "email", "created_at": "2026-09-13T20:00:00Z"},
            {"id": "sess-2", "title": "Google URL Check", "channel": "url", "created_at": "2026-09-13T21:00:00Z"},
        ]
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/history", method="GET")
            self.assertEqual(status, 200)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["analysis_id"], "sess-1")
            self.assertEqual(data[1]["channel"], "url")
            mock_supabase.get_user_history.assert_called_once_with(user_id=user_id, limit=50, offset=0)
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    def test_08_authenticated_get_own_analysis_detail_without_ml(self):
        """Retrieves complete stored analysis from DB without re-executing ML."""
        user_id = "user-auth-123"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "test@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.get_user_analysis.return_value = {
            "analysis_id": "sess-1",
            "title": "Phishing Analysis",
            "channel": "email",
            "created_at": "2026-09-13T20:00:00Z",
            "input": {"input": "Suspicious email text"},
            "result": {"prediction": "Likely Phishing", "risk_score": 92.5},
            "explanation": {"tier3": {"feature_contributions": []}},
            "metadata": {"schema_version": "1.0"},
        }
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/history/sess-1", method="GET")
            self.assertEqual(status, 200)
            self.assertEqual(data["analysis_id"], "sess-1")
            self.assertEqual(data["result"]["prediction"], "Likely Phishing")
            mock_supabase.get_user_analysis.assert_called_once_with(user_id=user_id, session_id="sess-1")
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    def test_09_user_cannot_access_unowned_analysis(self):
        """Accessing another user's analysis returns 404 without leaking existence."""
        user_id = "user-auth-123"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "test@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        # get_user_analysis returns None when ownership check fails
        mock_supabase.get_user_analysis.return_value = None
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/history/other-users-sess", method="GET")
            self.assertEqual(status, 404)
            self.assertIn("not found", data["detail"].lower())
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    def test_10_delete_own_analysis_success(self):
        """User can delete their own analysis session."""
        user_id = "user-auth-123"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "test@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.delete_user_analysis.return_value = True
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/history/my-session", method="DELETE")
            self.assertEqual(status, 200)
            self.assertTrue(data["success"])
            self.assertEqual(data["analysis_id"], "my-session")
            mock_supabase.delete_user_analysis.assert_called_once_with(user_id=user_id, session_id="my-session")
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    def test_11_user_cannot_delete_unowned_analysis(self):
        """Deleting an analysis belonging to another user returns 404."""
        user_id = "user-auth-123"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "test@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        # delete_user_analysis returns False when ownership check fails
        mock_supabase.delete_user_analysis.return_value = False
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/history/unowned-session", method="DELETE")
            self.assertEqual(status, 404)
            self.assertIn("not found", data["detail"].lower())
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    def test_12_delete_all_user_history(self):
        """User can delete all their analysis sessions."""
        user_id = "user-auth-123"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "test@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.delete_user_history.return_value = 5
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/history", method="DELETE")
            self.assertEqual(status, 200)
            self.assertTrue(data["success"])
            self.assertEqual(data["deleted_count"], 5)
            mock_supabase.delete_user_history.assert_called_once_with(user_id=user_id)
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    # ── 4. ACCOUNT DELETION ─────────────────────────────────────────────────

    def test_13_authenticated_account_deletion(self):
        """Authenticated account deletion triggers application cleanup and auth user deletion."""
        user_id = "user-delete-999"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "delete@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.delete_user_application_data.return_value = True
        mock_supabase.delete_auth_user.return_value = True
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/account", method="DELETE")
            self.assertEqual(status, 200)
            self.assertTrue(data["success"])
            self.assertIn("permanently deleted", data["message"])
            mock_supabase.delete_user_application_data.assert_called_once_with(user_id=user_id)
            mock_supabase.delete_auth_user.assert_called_once_with(user_id=user_id)
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    def test_13b_account_deletion_fails_when_application_data_fails(self):
        """Account deletion fails with HTTP 500 when application data cleanup fails."""
        user_id = "user-delete-err1"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "err1@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.delete_user_application_data.side_effect = Exception("DB transaction error")
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/account", method="DELETE")
            self.assertEqual(status, 500)
            self.assertIn("failed to delete user application data", data["detail"].lower())
            mock_supabase.delete_auth_user.assert_not_called()
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    def test_13c_account_deletion_fails_closed_when_auth_delete_fails(self):
        """Account deletion fails closed with HTTP 500 if Supabase Auth user deletion fails."""
        user_id = "user-delete-err2"
        from backend.services.auth_service import get_current_user_required
        app.dependency_overrides[get_current_user_required] = lambda: {"id": user_id, "email": "err2@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.delete_user_application_data.return_value = True
        mock_supabase.delete_auth_user.side_effect = Exception("Supabase Auth API Admin timeout")
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/account", method="DELETE")
            self.assertNotEqual(status, 200)
            self.assertEqual(status, 500)
            self.assertIn("failed to delete authentication user record", data["detail"].lower())
            mock_supabase.delete_user_application_data.assert_called_once_with(user_id=user_id)
            mock_supabase.delete_auth_user.assert_called_once_with(user_id=user_id)
        finally:
            app.dependency_overrides.pop(get_current_user_required, None)

    # ── 5. COMPENSATING ROLLBACK ON PERSISTENCE FAILURE ──────────────────────

    def test_14_compensating_rollback_on_persistence_failure(self):
        """If message creation fails after session creation, compensating cleanup deletes the session."""
        user_id = "user-transact-123"
        from backend.services.auth_service import get_current_user_optional
        app.dependency_overrides[get_current_user_optional] = lambda: {"id": user_id, "email": "bob@example.com"}

        mock_supabase = MagicMock(spec=SupabaseService)
        mock_supabase.is_configured = True
        mock_supabase.create_analysis_session.return_value = {
            "id": "transact-sess-1",
            "user_id": user_id,
            "created_at": "2026-09-13T22:00:00Z",
        }
        # Simulate failure inserting message
        mock_supabase.create_analysis_message.side_effect = Exception("DB Connection Timeout")
        app.state.supabase = mock_supabase

        try:
            status, data = self._call_api("/api/analyze", json_body={
                "channel": "sms",
                "input": "Verify your identity immediately."
            })
            self.assertEqual(status, 500)
            self.assertIn("persistence to user database failed", data["detail"])
            # Verify compensating cleanup was invoked
            mock_supabase.delete_user_analysis.assert_called_once_with(user_id, "transact-sess-1")
        finally:
            app.dependency_overrides.pop(get_current_user_optional, None)


if __name__ == "__main__":
    unittest.main()
