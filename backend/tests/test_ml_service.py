"""
CyberNexus - ML Inference Service Unit Tests
Phase 6B: Verification of singleton initialization, channel inference, thresholding, and zero-reload execution.
"""

import unittest
import time
from unittest.mock import patch
import joblib

from backend.services.ml_service import MLService
from ml.explainability.explanation_types import UnifiedExplanation


class TestMLService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        start_t = time.perf_counter()
        cls.service = MLService()
        cls.init_time = time.perf_counter() - start_t

    def test_01_service_initialization(self):
        """Verify MLService initializes all three explainers once."""
        self.assertIsNotNone(self.service.sms_explainer)
        self.assertIsNotNone(self.service.email_explainer)
        self.assertIsNotNone(self.service.url_explainer)
        self.assertIsNotNone(self.service.sms_explainer.calibrated_model)
        self.assertIsNotNone(self.service.email_explainer.calibrated_model)
        self.assertIsNotNone(self.service.url_explainer.calibrated_model)

    def test_02_sms_inference(self):
        """Verify SMS inference produces model-grounded prediction."""
        msg = "ALERT: Claim your free prize now! Call 08000930705 immediately to claim £500 cash reward."
        res = self.service.analyze_sms(msg)
        self.assertIsInstance(res, UnifiedExplanation)
        self.assertEqual(res.channel, "sms")
        self.assertEqual(res.predicted_class, 1)
        self.assertEqual(res.predicted_label, "Likely Smishing")
        self.assertEqual(res.operational_threshold, 0.50)
        self.assertGreater(res.calibrated_confidence, 90.0)
        self.assertEqual(len(res.structural_signals), 6)
        self.assertIsNotNone(res.text_signals)
        self.assertIn("tokens", res.text_signals)
        self.assertGreater(len(res.text_signals["tokens"]), 0)

    def test_03_email_inference(self):
        """Verify Email inference produces model-grounded prediction with separate Subject/Body signals."""
        subj = "URGENT: Action required on your banking account verification"
        body = "Dear customer, your account access has been suspended due to unauthorized activity. Please verify your credentials immediately at http://secure-verify-bank.com to avoid account lockout. Thank you."
        res = self.service.analyze_email(subj, body)
        self.assertIsInstance(res, UnifiedExplanation)
        self.assertEqual(res.channel, "email")
        self.assertEqual(res.predicted_class, 1)
        self.assertEqual(res.predicted_label, "Likely Phishing")
        self.assertEqual(res.operational_threshold, 0.50)
        self.assertGreater(res.calibrated_confidence, 90.0)
        self.assertEqual(len(res.structural_signals), 6)
        self.assertIsNotNone(res.text_signals)
        self.assertIn("subject", res.text_signals)
        self.assertIn("body", res.text_signals)

    def test_04_url_inference(self):
        """Verify URL inference produces model-grounded prediction under locked 0.2526 threshold."""
        url = "http://login.chase.com.security-verify-session.top/auth/resolve?session=9281048&token=verify"
        res = self.service.analyze_url(url)
        self.assertIsInstance(res, UnifiedExplanation)
        self.assertEqual(res.channel, "url")
        self.assertEqual(res.predicted_class, 1)
        self.assertEqual(res.predicted_label, "Malicious URL")
        self.assertEqual(res.operational_threshold, 0.2526)
        self.assertGreater(res.calibrated_confidence, 90.0)
        self.assertEqual(len(res.structural_signals), 15)
        self.assertIsNone(res.text_signals)  # URL is structural only

    def test_05_zero_reload_runtime_verification(self):
        """
        Prove at runtime that inference calls do NOT reload models from disk or invoke joblib.load.
        """
        # Save memory IDs of models before inference calls
        sms_model_id = id(self.service.sms_explainer.calibrated_model)
        email_model_id = id(self.service.email_explainer.calibrated_model)
        url_model_id = id(self.service.url_explainer.calibrated_model)

        # Patch joblib.load to fail if called during inference
        with patch("joblib.load", side_effect=RuntimeError("joblib.load should NOT be called during inference")):
            res_sms = self.service.analyze_sms("Standard lunch meeting tomorrow at 12pm.")
            res_email = self.service.analyze_email("Meeting Agenda", "Attached is the roadmap for next quarter.")
            res_url = self.service.analyze_url("https://www.google.com/search?q=cybersecurity")

        # Verify predictions succeeded without calling joblib.load
        self.assertEqual(res_sms.predicted_class, 0)
        self.assertEqual(res_email.predicted_class, 0)
        self.assertEqual(res_url.predicted_class, 0)

        # Verify object IDs remain strictly identical (same in-memory instances)
        self.assertEqual(id(self.service.sms_explainer.calibrated_model), sms_model_id)
        self.assertEqual(id(self.service.email_explainer.calibrated_model), email_model_id)
        self.assertEqual(id(self.service.url_explainer.calibrated_model), url_model_id)


if __name__ == "__main__":
    unittest.main()
