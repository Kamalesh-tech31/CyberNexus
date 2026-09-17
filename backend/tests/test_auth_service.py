"""
CyberNexus - Phase 6F-2B Auth Service Unit Tests
Tests for JWT verification, Supabase auth integration, and FastAPI dependency behavior.
"""

import unittest
from unittest.mock import MagicMock
import jwt as pyjwt
import time

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from backend.services.auth_service import (
    get_token_from_header,
    verify_supabase_jwt,
    get_current_user_optional,
    get_current_user_required,
    security_optional,
)


def _make_token(payload: dict, expired: bool = False) -> str:
    """Create a minimal signed JWT for testing using pyjwt."""
    if expired:
        payload = {**payload, "exp": int(time.time()) - 3600}
    else:
        payload = {**payload, "exp": int(time.time()) + 3600}
    return pyjwt.encode(payload, "secret", algorithm="HS256")


class TestGetTokenFromHeader(unittest.TestCase):
    """Tests for get_token_from_header helper."""

    def test_returns_none_when_no_credentials(self):
        self.assertIsNone(get_token_from_header(None))

    def test_returns_none_when_empty_credentials(self):
        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = ""
        self.assertIsNone(get_token_from_header(creds))

    def test_returns_stripped_token(self):
        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = "  my-test-token  "
        result = get_token_from_header(creds)
        self.assertEqual(result, "my-test-token")

    def test_returns_normal_token(self):
        creds = MagicMock(spec=HTTPAuthorizationCredentials)
        creds.credentials = "eyJhbGciOiJIUzI1NiJ9.payload.sig"
        result = get_token_from_header(creds)
        self.assertEqual(result, "eyJhbGciOiJIUzI1NiJ9.payload.sig")


class TestVerifySupabaseJWT(unittest.TestCase):
    """Tests for verify_supabase_jwt function."""

    def test_empty_token_raises_401(self):
        with self.assertRaises(HTTPException) as ctx:
            verify_supabase_jwt("")
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("empty", ctx.exception.detail.lower())

    def test_whitespace_token_raises_401(self):
        with self.assertRaises(HTTPException) as ctx:
            verify_supabase_jwt("   ")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_malformed_token_raises_401(self):
        """A totally bogus non-JWT string should raise 401."""
        with self.assertRaises(HTTPException) as ctx:
            verify_supabase_jwt("not-a-real-jwt-token-at-all")
        self.assertEqual(ctx.exception.status_code, 401)

    def test_unsigned_or_unverified_token_without_client_or_secret_rejected(self):
        """A token without Supabase client or local secret MUST be rejected (never accept unverified)."""
        token = _make_token({"sub": "unverified-user", "email": "unverified@example.com"})
        with self.assertRaises(HTTPException) as ctx:
            verify_supabase_jwt(token, supabase_client=None, jwt_secret=None)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("cryptographically", ctx.exception.detail.lower())

    def test_valid_jwt_with_secret_returns_user(self):
        """A properly formed JWT signed with the expected secret should return user dict."""
        secret = "test-secret-key-at-least-32-chars-long-for-hmac-sha256"
        payload = {"sub": "test-user-id-123", "email": "test@example.com", "exp": int(time.time()) + 3600}
        token = pyjwt.encode(payload, secret, algorithm="HS256")
        result = verify_supabase_jwt(token, supabase_client=None, jwt_secret=secret)
        self.assertEqual(result["id"], "test-user-id-123")
        self.assertEqual(result["email"], "test@example.com")

    def test_forged_signature_with_secret_rejected(self):
        """A token signed with wrong secret MUST raise 401."""
        secret = "correct-secret-key-at-least-32-chars-long-for-hmac-sha256"
        wrong_secret = "wrong-secret-key-at-least-32-chars-long-for-hmac-sha256"
        payload = {"sub": "forged-user", "email": "forged@example.com", "exp": int(time.time()) + 3600}
        token = pyjwt.encode(payload, wrong_secret, algorithm="HS256")
        with self.assertRaises(HTTPException) as ctx:
            verify_supabase_jwt(token, supabase_client=None, jwt_secret=secret)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("signature", ctx.exception.detail.lower())

    def test_valid_jwt_missing_sub_raises_401(self):
        """JWT without sub claim should raise 401."""
        secret = "test-secret-key-at-least-32-chars-long-for-hmac-sha256"
        token = pyjwt.encode({"email": "test@example.com", "exp": int(time.time()) + 3600}, secret, algorithm="HS256")
        with self.assertRaises(HTTPException) as ctx:
            verify_supabase_jwt(token, supabase_client=None, jwt_secret=secret)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("sub", ctx.exception.detail.lower())

    def test_supabase_client_auth_success_path(self):
        """When Supabase client.auth.get_user succeeds, its user dict is returned."""
        mock_client = MagicMock()
        mock_user = MagicMock()
        mock_user.id = "supabase-uid-456"
        mock_user.email = "supabase@example.com"
        mock_user.user_metadata = {"full_name": "Supabase User"}
        mock_user.app_metadata = {}
        mock_response = MagicMock()
        mock_response.user = mock_user
        mock_client.auth.get_user.return_value = mock_response

        token = "any-token-string-validated-by-supabase-api"
        result = verify_supabase_jwt(token, supabase_client=mock_client)
        self.assertEqual(result["id"], "supabase-uid-456")
        self.assertEqual(result["email"], "supabase@example.com")
        mock_client.auth.get_user.assert_called_once_with(token)

    def test_supabase_client_auth_rejected_raises_401(self):
        """When Supabase Auth explicitly rejects a token as invalid, raise 401."""
        mock_client = MagicMock()
        mock_client.auth.get_user.side_effect = Exception("invalid JWT: unable to parse or verify signature")

        with self.assertRaises(HTTPException) as ctx:
            verify_supabase_jwt("bad-token", supabase_client=mock_client)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("invalid or expired", ctx.exception.detail.lower())

    def test_expired_jwt_raises_401(self):
        """An expired JWT should raise 401 with 'expired' in the message."""
        secret = "test-secret-key-at-least-32-chars-long-for-hmac-sha256"
        token = pyjwt.encode(
            {"sub": "expired-user", "email": "expired@example.com", "exp": int(time.time()) - 3600},
            secret,
            algorithm="HS256"
        )
        with self.assertRaises(HTTPException) as ctx:
            verify_supabase_jwt(token, supabase_client=None, jwt_secret=secret)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIn("expired", ctx.exception.detail.lower())

    def test_user_metadata_defaults_to_empty_dict(self):
        """JWT without user_metadata/app_metadata fields returns empty dicts."""
        secret = "test-secret-key-at-least-32-chars-long-for-hmac-sha256"
        token = pyjwt.encode(
            {"sub": "bare-user", "email": "bare@example.com", "exp": int(time.time()) + 3600},
            secret,
            algorithm="HS256"
        )
        result = verify_supabase_jwt(token, supabase_client=None, jwt_secret=secret)
        self.assertIsInstance(result["user_metadata"], dict)
        self.assertIsInstance(result["app_metadata"], dict)


class TestAuthServiceSymbols(unittest.TestCase):
    """Sanity-check that auth_service exposes required symbols."""

    def test_required_symbols_importable(self):
        self.assertIsNotNone(get_current_user_optional)
        self.assertIsNotNone(get_current_user_required)
        self.assertIsNotNone(security_optional)

    def test_security_optional_auto_error_false(self):
        """HTTPBearer must be configured with auto_error=False for guest mode."""
        self.assertFalse(security_optional.auto_error)


if __name__ == "__main__":
    unittest.main()
