"""
CyberNexus - Progressive Disclosure Response Contract Tests
Phase 6D: Comprehensive verification of response mapping, Tier 1-3 structures, risk score math, and metadata integrity.
"""

import unittest
from backend.services.ml_service import MLService
from backend.services.response_mapper import (
    map_explanation_to_response,
    compute_risk_score,
    get_confidence_band,
    build_confidence_breakdown,
)


class TestResponseContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ml_service = MLService()

    def test_01_sms_response_tier1_tier2_tier3(self):
        """Verify SMS response contains Tier 1, Tier 2, and Tier 3 structures."""
        explanation = self.ml_service.analyze_sms(
            "ALERT: Claim your free prize now! Call 08000930705 immediately to claim £500 cash reward."
        )
        resp = map_explanation_to_response(explanation, resolved_channel="sms")

        # Top-level fields
        self.assertEqual(resp["channel"], "sms")
        self.assertEqual(resp["resolved_channel"], "sms")
        self.assertEqual(resp["prediction"], "Likely Smishing")
        self.assertIn("risk_score", resp)
        self.assertIn("confidence", resp)
        self.assertIn("reasons", resp)
        self.assertIn("indicators", resp)
        self.assertIn("recommendation", resp)

        # Tier 1
        self.assertIn("tier1", resp)
        self.assertEqual(resp["tier1"]["verdict"], "Likely Smishing")
        self.assertEqual(resp["tier1"]["confidence_band"], "high")
        self.assertGreater(resp["tier1"]["confidence"], 0.85)

        # Tier 2
        self.assertIn("tier2", resp)
        self.assertIn("flags", resp["tier2"])
        self.assertEqual(len(resp["tier2"]["flags"]), 6)
        self.assertIn("confidence_breakdown", resp["tier2"])
        self.assertEqual(set(resp["tier2"]["confidence_breakdown"].keys()), {"ham", "spam"})

        # Tier 3
        self.assertIn("tier3", resp)
        self.assertIn("feature_contributions", resp["tier3"])
        self.assertEqual(len(resp["tier3"]["feature_contributions"]), 6)
        self.assertIn("top_text_signals", resp["tier3"])
        self.assertGreater(len(resp["tier3"]["top_text_signals"]), 0)
        self.assertIn("model_metadata", resp["tier3"])

    def test_02_sms_structural_and_text_contributions(self):
        """Verify SMS contains real structural and text contributions."""
        explanation = self.ml_service.analyze_sms(
            "ALERT: Claim your free prize now! Call 08000930705 immediately."
        )
        resp = map_explanation_to_response(explanation, resolved_channel="sms")

        for fc in resp["tier3"]["feature_contributions"]:
            self.assertIn("feature", fc)
            self.assertIn("value", fc)
            self.assertIn("contribution", fc)
            self.assertIn("direction", fc)
            # Verify direction matches sign
            if fc["contribution"] > 0:
                self.assertEqual(fc["direction"], "increases_risk")
            else:
                self.assertEqual(fc["direction"], "decreases_risk")

        for ts in resp["tier3"]["top_text_signals"]:
            self.assertIn("token", ts)
            self.assertIn("weight", ts)

    def test_03_email_subject_body_source_preservation(self):
        """Verify Email preserves Subject vs Body source and contains real structural contributions."""
        explanation = self.ml_service.analyze_email(
            subject="URGENT: Suspicious activity on account",
            body="Dear customer, please verify your credentials at http://secure-portal.com immediately."
        )
        resp = map_explanation_to_response(explanation, resolved_channel="email")

        self.assertEqual(resp["channel"], "email")
        self.assertEqual(resp["tier1"]["verdict"], "Likely Phishing")
        self.assertEqual(len(resp["tier3"]["feature_contributions"]), 6)

        self.assertIn("top_text_signals", resp["tier3"])
        sources = [ts.get("source") for ts in resp["tier3"]["top_text_signals"]]
        self.assertIn("subject", sources)
        self.assertIn("body", sources)
        for ts in resp["tier3"]["top_text_signals"]:
            self.assertIn(ts["source"], ["subject", "body"])

        # Confidence breakdown for email
        self.assertEqual(set(resp["tier2"]["confidence_breakdown"].keys()), {"legitimate", "phishing"})

    def test_04_url_structural_only_no_fake_text_signals(self):
        """Verify URL contains 15 structural contributions and omits top_text_signals."""
        explanation = self.ml_service.analyze_url(
            "http://login.chase.com.security-verify-session.top/auth/resolve?token=verify"
        )
        resp = map_explanation_to_response(explanation, resolved_channel="url")

        self.assertEqual(resp["channel"], "url")
        self.assertEqual(resp["tier1"]["verdict"], "Malicious URL")
        self.assertEqual(len(resp["tier3"]["feature_contributions"]), 15)

        # URL has NO text signals; top_text_signals must NOT be present in tier3
        self.assertNotIn("top_text_signals", resp["tier3"])

        # Confidence breakdown for URL
        self.assertEqual(set(resp["tier2"]["confidence_breakdown"].keys()), {"good", "bad"})

    def test_05_confidence_equals_calibrated_model_probability(self):
        """Verify confidence equals calibrated model probability."""
        explanation = self.ml_service.analyze_sms("Hello, standard message for testing.")
        resp = map_explanation_to_response(explanation, resolved_channel="sms")

        expected_conf = round(explanation.calibrated_confidence / 100.0, 4)
        self.assertEqual(resp["confidence"], expected_conf)
        self.assertEqual(resp["tier1"]["confidence"], expected_conf)

    def test_06_confidence_breakdown_binary_no_fabricated_classes(self):
        """Verify binary channels have exactly 2 classes in confidence breakdown without fabricated 3rd class."""
        sms_exp = self.ml_service.analyze_sms("Hello")
        sms_resp = map_explanation_to_response(sms_exp, resolved_channel="sms")
        self.assertEqual(len(sms_resp["tier2"]["confidence_breakdown"]), 2)

        email_exp = self.ml_service.analyze_email("Meeting", "Team sync at 10am.")
        email_resp = map_explanation_to_response(email_exp, resolved_channel="email")
        self.assertEqual(len(email_resp["tier2"]["confidence_breakdown"]), 2)

        url_exp = self.ml_service.analyze_url("https://www.google.com")
        url_resp = map_explanation_to_response(url_exp, resolved_channel="url")
        self.assertEqual(len(url_resp["tier2"]["confidence_breakdown"]), 2)

    def test_07_direction_matches_contribution_sign(self):
        """Verify direction strictly matches contribution sign across all signals."""
        explanation = self.ml_service.analyze_url("https://paypal-update-billing.com/login")
        resp = map_explanation_to_response(explanation, resolved_channel="url")

        for sig in resp["tier3"]["feature_contributions"]:
            if sig["contribution"] > 0:
                self.assertEqual(sig["direction"], "increases_risk")
            else:
                self.assertEqual(sig["direction"], "decreases_risk")

    def test_08_risk_score_binary_malicious(self):
        """Verify binary malicious prediction: risk_score == 100 * P(malicious)."""
        score = compute_risk_score(predicted_class=1, calibrated_confidence=98.5)
        self.assertEqual(score, 98.5)

    def test_09_risk_score_binary_safe(self):
        """Verify binary safe prediction: risk_score == 100 * (1 - P(safe))."""
        score = compute_risk_score(predicted_class=0, calibrated_confidence=98.5)
        self.assertEqual(score, 1.5)

    def test_10_confidence_and_risk_score_differ_for_safe(self):
        """Verify confidence and risk_score legitimately differ for safe predictions."""
        explanation = self.ml_service.analyze_sms("Are you coming to dinner tonight?")
        resp = map_explanation_to_response(explanation, resolved_channel="sms")

        self.assertEqual(resp["prediction"], "Safe & Legitimate")
        self.assertGreater(resp["confidence"], 0.85)  # High confidence it is safe
        self.assertLess(resp["risk_score"], 15.0)     # Low risk score

    def test_11_multiclass_risk_score_mapping(self):
        """Verify multiclass risk mapping follows explicit benign/malicious class rules."""
        # 1. Single benign class
        probs_1 = {"benign": 0.80, "phishing": 0.15, "malware": 0.05}
        score_1 = compute_risk_score(
            predicted_class=0,
            calibrated_confidence=80.0,
            class_probabilities=probs_1,
            benign_class_name="benign"
        )
        self.assertEqual(score_1, 20.0)

        # 2. Explicit risky classes
        probs_2 = {"normal": 0.30, "defacement": 0.40, "phishing": 0.30}
        score_2 = compute_risk_score(
            predicted_class=1,
            calibrated_confidence=40.0,
            class_probabilities=probs_2,
            risky_class_names=["defacement", "phishing"]
        )
        self.assertEqual(score_2, 70.0)

        # 3. Multiclass without semantics must raise ValueError (no guessing)
        probs_3 = {"class_a": 0.5, "class_b": 0.3, "class_c": 0.2}
        with self.assertRaises(ValueError):
            compute_risk_score(
                predicted_class=0,
                calibrated_confidence=50.0,
                class_probabilities=probs_3
            )

    def test_12_confidence_band_boundaries(self):
        """Verify confidence band derivation on locked thresholds."""
        self.assertEqual(get_confidence_band(0.60), "low")
        self.assertEqual(get_confidence_band(0.6499), "low")
        self.assertEqual(get_confidence_band(0.65), "medium")
        self.assertEqual(get_confidence_band(0.80), "medium")
        self.assertEqual(get_confidence_band(0.85), "medium")
        self.assertEqual(get_confidence_band(0.8501), "high")
        self.assertEqual(get_confidence_band(0.99), "high")

    def test_13_metadata_grounded_in_artifacts(self):
        """Verify metadata values originate from actual artifacts and are not fabricated."""
        explanation = self.ml_service.analyze_url("https://example.com")
        resp = map_explanation_to_response(explanation, resolved_channel="url")

        meta = resp["tier3"]["model_metadata"]
        self.assertEqual(meta["model_version"], "v1.0-lgbm-champion")
        self.assertIn("Phishing Site Predict 100k", meta["trained_on"])
        self.assertIn("Confidence reflects predicted probability", meta["note"])


if __name__ == "__main__":
    unittest.main()
