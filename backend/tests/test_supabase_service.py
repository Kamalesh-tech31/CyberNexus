"""
CyberNexus - Phase 6F-1 Supabase Service Unit & Integration Tests
Verifies Supabase client initialization, safe lifespan startup, fail-loud configuration behavior,
placeholder identity properties, and database foundation integrity.
"""

import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI

from backend.app import app, lifespan
from backend.services.supabase_service import (
    SupabaseService,
    SupabaseConfigError,
    SupabaseConnectionError,
    PLACEHOLDER_USER_ID,
    PLACEHOLDER_USER_EMAIL,
)


class TestSupabaseServiceFoundation(unittest.TestCase):
    """
    Unit test suite for Phase 6F-1 database foundation architecture (mocked/standalone).
    """

    def test_01_placeholder_user_constants(self):
        """
        Verify stable placeholder user ID and email format (Section 7).
        """
        self.assertEqual(PLACEHOLDER_USER_ID, "00000000-0000-0000-0000-000000000001")
        self.assertEqual(PLACEHOLDER_USER_EMAIL, "placeholder@cybernexus.local")

    def test_02_unconfigured_service_startup_safety(self):
        """
        Verify SupabaseService initializes safely without throwing when unconfigured (Section 15A).
        """
        service = SupabaseService(url="", service_role_key="")
        self.assertFalse(service.is_configured)
        self.assertIsNone(service.client)

    def test_03_unconfigured_service_raises_config_error(self):
        """
        Verify DB operations fail loudly with SupabaseConfigError when unconfigured at point of use (Section 15A).
        """
        service = SupabaseService(url="", service_role_key="")
        with self.assertRaises(SupabaseConfigError) as ctx:
            service.verify_connection()
        self.assertIn("Supabase is not configured", str(ctx.exception))

        with self.assertRaises(SupabaseConfigError):
            service.get_placeholder_user()

        with self.assertRaises(SupabaseConfigError):
            service.create_test_record()

    def test_04_fastapi_lifespan_starts_without_crashing(self):
        """
        Verify FastAPI application lifespan starts cleanly and sets app.state.supabase (Section 15A).
        """
        test_app = FastAPI(lifespan=lifespan)
        # Verify app initializes state during startup
        with patch("backend.app.MLService"):
            with patch("backend.app.SupabaseService") as MockService:
                mock_inst = MagicMock()
                MockService.return_value = mock_inst
                
                # Execute lifespan context
                import asyncio
                async def run_lifespan():
                    async with lifespan(test_app):
                        self.assertEqual(test_app.state.supabase, mock_inst)
                
                asyncio.run(run_lifespan())
                self.assertIsNone(test_app.state.supabase)

    @patch("backend.services.supabase_service.create_client")
    def test_05_mocked_supabase_operations(self, mock_create_client):
        """
        Verify SupabaseService query executions against mocked Supabase client.
        """
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        service = SupabaseService(
            url="https://valid-project-ref.supabase.co",
            service_role_key="valid-service-role-key-string"
        )
        self.assertTrue(service.is_configured)

        # 1. Test verify_connection
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_limit = MagicMock()
        mock_select.limit.return_value = mock_limit
        mock_limit.execute.return_value = MagicMock(data=[{"id": "test-id"}])

        self.assertTrue(service.verify_connection())

        # 2. Test get_placeholder_user
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[{
            "id": PLACEHOLDER_USER_ID,
            "email": PLACEHOLDER_USER_EMAIL,
            "role": "guest"
        }])

        user = service.get_placeholder_user()
        self.assertEqual(user["id"], PLACEHOLDER_USER_ID)
        self.assertEqual(user["email"], PLACEHOLDER_USER_EMAIL)

        # 3. Test create_test_record
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{
            "id": "rec-12345",
            "user_id": PLACEHOLDER_USER_ID,
            "status": "test_active"
        }])

        rec = service.create_test_record(user_id=PLACEHOLDER_USER_ID, status="test_active")
        self.assertEqual(rec["user_id"], PLACEHOLDER_USER_ID)
        self.assertEqual(rec["status"], "test_active")


class TestRealSupabaseIntegration(unittest.TestCase):
    """
    Genuine real-world integration test against configured Supabase database.
    NO MagicMock / patched create_client used here.
    """

    def setUp(self):
        self.service = SupabaseService()
        if not self.service.is_configured:
            self.skipTest("Supabase is not configured with valid real credentials.")
        # Skip if Phase 6F-2A schema not yet applied (placeholder user not seeded)
        try:
            self.service.get_placeholder_user()
        except Exception:
            self.skipTest("Placeholder user not found in database. Run Phase 6F-2A migration to seed it.")

    def test_real_supabase_e2e_lifecycle(self):
        """
        End-to-End Real Supabase Database Lifecycle Verification:
        1. Verify connection & retrieve placeholder user
        2. Insert test record referencing placeholder user_id
        3. Retrieve and verify inserted record
        4. Confirm invalid user_id foreign-key insert is rejected
        5. Clean up (delete) created test record
        """
        # 1. Verify connection & retrieve placeholder user
        self.assertTrue(self.service.verify_connection())
        user = self.service.get_placeholder_user()
        self.assertEqual(user["id"], PLACEHOLDER_USER_ID)
        self.assertEqual(user["email"], PLACEHOLDER_USER_EMAIL)

        # 2. Insert real test record into analysis_foundation_test
        test_status = "e2e_integration_test_active"
        record = self.service.create_test_record(user_id=PLACEHOLDER_USER_ID, status=test_status)
        record_id = record["id"]
        self.assertIsNotNone(record_id)
        self.assertEqual(record["user_id"], PLACEHOLDER_USER_ID)
        self.assertEqual(record["status"], test_status)

        try:
            # 3. Retrieve and verify inserted record
            fetched = self.service.get_test_record(record_id)
            self.assertEqual(fetched["id"], record_id)
            self.assertEqual(fetched["user_id"], PLACEHOLDER_USER_ID)
            self.assertEqual(fetched["status"], test_status)

            # 4. Attempt insert with invalid foreign key user_id and confirm rejection
            invalid_user_id = "99999999-9999-9999-9999-999999999999"
            with self.assertRaises(SupabaseConnectionError):
                self.service.create_test_record(user_id=invalid_user_id, status="invalid_fk_test")

        finally:
            # 5. Clean up (delete) the test record created
            deleted = self.service.delete_test_record(record_id)
            self.assertTrue(deleted)
            # Confirm deletion
            with self.assertRaises(SupabaseConnectionError):
                self.service.get_test_record(record_id)


if __name__ == "__main__":
    unittest.main()
