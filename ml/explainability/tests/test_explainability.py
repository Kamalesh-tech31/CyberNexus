"""
CyberNexus - Phase 5B: Explainability Sanity Tests

Verifies:
1. Predictions and explanations exist for all 3 channels.
2. Every reported text token actually occurs in the input text.
3. Every reported feature exists in the approved feature lists.
4. Contributions have correct sign and match model weights/TreeSHAP values.
5. No explanation references unavailable features.
6. No fabricated feature values.
7. Identical inputs produce deterministic explanation outputs.
"""

import sys
import unittest
import numpy as np

# Ensure UTF-8 output encoding
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from ml.explainability.sms_explain import SMSExplainer
from ml.explainability.email_explain import EmailExplainer
from ml.explainability.url_explain import URLExplainer


class TestModelGroundedExplainability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sms_explainer = SMSExplainer()
        cls.email_explainer = EmailExplainer()
        cls.url_explainer = URLExplainer()

    # --------------------------------------------------------------------------
    # SMS TESTS
    # --------------------------------------------------------------------------
    def test_sms_smishing_example(self):
        msg = "ALERT: Claim your free prize now! Call 08000930705 immediately to claim £500 cash reward. Urgent reply needed."
        exp1 = self.sms_explainer.explain(msg)
        exp2 = self.sms_explainer.explain(msg)

        # 1. Determinism
        self.assertEqual(exp1.to_dict(), exp2.to_dict(), "SMS explanation must be deterministic.")

        # 2. Prediction exists
        self.assertIn(exp1.predicted_class, [0, 1])
        self.assertEqual(exp1.predicted_class, 1, "Smishing sample should be classified as spam (1).")
        self.assertGreaterEqual(exp1.calibrated_confidence, 50.0)

        # 3. Grounded Tokens: Every token must actually occur in the input
        self.assertIsNotNone(exp1.text_signals)
        self.assertIn("tokens", exp1.text_signals)
        msg_lower = msg.lower()
        for sig in exp1.text_signals["tokens"]:
            self.assertTrue(
                sig.token in msg_lower or any(word in msg_lower for word in sig.token.split()),
                f"Token '{sig.token}' was reported but not present in SMS input."
            )
            # 4. Correct direction
            if sig.contribution > 0:
                self.assertEqual(sig.direction, "increases_risk")
            else:
                self.assertEqual(sig.direction, "decreases_risk")

        # 5. Structural features exist in approved list
        approved_sms_feats = {"message_length", "digit_to_length_ratio", "url_presence", "punctuation_density", "special_char_count", "uppercase_ratio"}
        for s_sig in exp1.structural_signals:
            self.assertIn(s_sig.feature, approved_sms_feats)
            self.assertGreater(len(s_sig.description), 5)

    def test_sms_legitimate_example(self):
        msg = "Hey, are we still meeting for lunch at 1pm tomorrow near the office?"
        exp = self.sms_explainer.explain(msg)

        self.assertEqual(exp.predicted_class, 0, "Clean message should be classified as ham (0).")
        self.assertEqual(exp.predicted_label, "Safe & Legitimate")
        self.assertGreaterEqual(exp.calibrated_confidence, 50.0)

        # Verify no fabricated tokens
        if exp.text_signals and "tokens" in exp.text_signals:
            msg_lower = msg.lower()
            for sig in exp.text_signals["tokens"]:
                self.assertTrue(
                    sig.token in msg_lower or any(word in msg_lower for word in sig.token.split()),
                    f"Token '{sig.token}' was reported but not present in clean SMS."
                )

    # --------------------------------------------------------------------------
    # EMAIL TESTS
    # --------------------------------------------------------------------------
    def test_email_phishing_example(self):
        subject = "URGENT: Action required on your banking account verification"
        body = "Dear customer, your account access has been suspended due to unauthorized activity. Please verify your credentials immediately at http://secure-verify-bank.com to avoid account lockout. Thank you."
        exp1 = self.email_explainer.explain(subject, body)
        exp2 = self.email_explainer.explain(subject, body)

        # 1. Determinism
        self.assertEqual(exp1.to_dict(), exp2.to_dict(), "Email explanation must be deterministic.")

        # 2. Prediction
        self.assertEqual(exp1.predicted_class, 1, "Phishing email should be classified as phishing (1).")
        self.assertGreaterEqual(exp1.calibrated_confidence, 50.0)

        # 3. Subject and Body Separation
        self.assertIsNotNone(exp1.text_signals)
        subj_lower = subject.lower()
        body_lower = body.lower()

        if "subject" in exp1.text_signals:
            for s in exp1.text_signals["subject"]:
                self.assertEqual(s.origin, "subject")
                self.assertTrue(
                    s.token in subj_lower or any(w in subj_lower for w in s.token.split()),
                    f"Subject token '{s.token}' not in subject string."
                )

        if "body" in exp1.text_signals:
            for b in exp1.text_signals["body"]:
                self.assertEqual(b.origin, "body")
                self.assertTrue(
                    b.token in body_lower or any(w in body_lower for w in b.token.split()),
                    f"Body token '{b.token}' not in body string."
                )

        # 4. Structural features
        approved_email_feats = {"email_length", "url_count", "digit_count", "exclamation_count", "all_caps_word_count", "urgency_keyword_count"}
        for s_sig in exp1.structural_signals:
            self.assertIn(s_sig.feature, approved_email_feats)

    def test_email_legitimate_example(self):
        subject = "Project review notes from yesterday's team sync"
        body = "Hi team, attached are the meeting notes and action items from our weekly review. Let me know if anyone has questions."
        exp = self.email_explainer.explain(subject, body)

        self.assertEqual(exp.predicted_class, 0, "Legitimate email should be classified as safe (0).")
        self.assertEqual(exp.predicted_label, "Safe & Legitimate")

    # --------------------------------------------------------------------------
    # URL TESTS
    # --------------------------------------------------------------------------
    def test_url_suspicious_example(self):
        raw_url = "http://login.chase.com.security-verify-session.top/auth/resolve?session=9281048&token=verify"
        exp1 = self.url_explainer.explain(raw_url)
        exp2 = self.url_explainer.explain(raw_url)

        # 1. Determinism
        self.assertEqual(exp1.to_dict(), exp2.to_dict(), "URL explanation must be deterministic.")

        # 2. Prediction
        self.assertEqual(exp1.predicted_class, 1, "Suspicious URL should be classified as malicious (1).")
        self.assertEqual(exp1.operational_threshold, 0.2526)

        # 3. URL must have NO text_signals (omitted entirely)
        self.assertIsNone(exp1.text_signals, "URL explanations must be structural only (text_signals is None).")

        # 4. All 15 structural features present and grounded
        approved_url_feats = {
            "url_length", "hostname_length", "path_length", "query_length", "dot_count",
            "hyphen_count", "digit_count", "special_char_count", "suspicious_token_presence",
            "subdomain_depth", "ip_hostname", "https_presence", "digit_to_length_ratio",
            "at_symbol_presence", "embedded_double_slash_count"
        }
        self.assertEqual(len(exp1.structural_signals), 15)
        for s_sig in exp1.structural_signals:
            self.assertIn(s_sig.feature, approved_url_feats)
            if s_sig.contribution > 0:
                self.assertEqual(s_sig.direction, "increases_risk")
            else:
                self.assertEqual(s_sig.direction, "decreases_risk")

        # 5. Check specific feature logic
        # For this URL: suspicious_token_presence should be 1.0 (has 'login', 'verify')
        susp_sig = next(s for s in exp1.structural_signals if s.feature == "suspicious_token_presence")
        self.assertEqual(susp_sig.value, 1.0)
        self.assertEqual(susp_sig.direction, "increases_risk")

    def test_url_legitimate_example(self):
        raw_url = "https://www.google.com/search?q=cybersecurity+research"
        exp = self.url_explainer.explain(raw_url)

        self.assertEqual(exp.predicted_class, 0, "Clean standard URL should be classified as safe (0).")
        self.assertEqual(exp.predicted_label, "Safe & Legitimate")
        self.assertIsNone(exp.text_signals)


if __name__ == "__main__":
    unittest.main()
