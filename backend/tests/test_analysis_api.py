"""
CyberNexus - Channel Routing & Analysis API Unit Tests
Phase 6C: Tests covering auto-detect heuristics, explicit channel overrides, error handling, and real inference execution.
"""

import unittest
import asyncio
import json

from backend.app import app, lifespan
from backend.schemas import AnalysisRequest, AnalysisResponse
from backend.routers.analysis import detect_channel


class TestChannelRoutingAndAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize lifespan for testing
        cls.lifespan_ctx = lifespan(app)
        asyncio.run(cls.lifespan_ctx.__aenter__())

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.lifespan_ctx.__aexit__(None, None, None))

    @staticmethod
    def _call_api(path: str, method: str = "POST", json_body: dict = None):
        """Helper to invoke ASGI app directly without external dependencies."""
        body_bytes = json.dumps(json_body or {}).encode("utf-8")
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [
                (b"host", b"localhost:8000"),
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body_bytes)).encode("utf-8")),
            ],
            "app": app,
        }
        status_code = None
        headers = []
        response_chunks = []

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        async def send(message):
            nonlocal status_code, headers, response_chunks
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = message["headers"]
            elif message["type"] == "http.response.body":
                response_chunks.append(message.get("body", b""))

        asyncio.run(app(scope, receive, send))
        raw_body = b"".join(response_chunks).decode("utf-8")
        data = json.loads(raw_body) if raw_body else {}
        return status_code, data

    def test_01_detect_channel_heuristics(self):
        """Unit tests for standalone auto-detect heuristic rules."""
        # 1. Pure single-token URLs
        self.assertEqual(detect_channel("https://secure-login.bank.com/auth"), "url")
        self.assertEqual(detect_channel("http://my-test-site.xyz"), "url")
        self.assertEqual(detect_channel("www.google.com"), "url")
        self.assertEqual(detect_channel("example.com/path"), "url")
        self.assertEqual(detect_channel("https://test-link.com"), "url")
        self.assertEqual(detect_channel("https://test-link.com/path"), "url")

        # 2. Messages containing URLs (must NOT be classified as URL)
        self.assertEqual(detect_channel("https://test-link.com click here"), "sms")
        self.assertEqual(detect_channel("https://test-link.com\nPlease verify your account"), "sms")
        self.assertEqual(detect_channel("Hey, check https://test-link.com"), "sms")

        # 3. Emails
        self.assertEqual(
            detect_channel("Subject: Urgent Security Notice\nPlease verify your account immediately."),
            "email"
        )
        self.assertEqual(
            detect_channel("From: admin@company.com\nTo: user@company.com\n\nMeeting at 3pm today."),
            "email"
        )

        # 4. SMS (fallback / non-email structure)
        self.assertEqual(detect_channel("Contact me at user@example.com about tomorrow."), "sms")
        self.assertEqual(detect_channel("ALERT: Win £1000 cash now! Call 08000930705"), "sms")
        self.assertEqual(detect_channel("Hey, are you free for dinner tonight?"), "sms")

    def test_02_explicit_sms_api(self):
        """Verify explicit channel='sms' invokes SMSExplainer and returns real inference."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "sms",
            "input": "ALERT: Claim your free prize now! Call 08000930705 immediately."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "sms")
        self.assertEqual(data["resolved_channel"], "sms")
        self.assertEqual(data["prediction"], "Likely Smishing")
        self.assertEqual(data["tier1"]["verdict"], "Likely Smishing")
        self.assertEqual(data["tier1"]["confidence_band"], "high")
        self.assertGreater(data["confidence"], 0.90)
        self.assertGreater(data["risk_score"], 90.0)
        self.assertEqual(len(data["tier3"]["feature_contributions"]), 6)
        self.assertIn("top_text_signals", data["tier3"])
        self.assertGreater(len(data["tier3"]["top_text_signals"]), 0)

    def test_03_explicit_email_api(self):
        """Verify explicit channel='email' invokes EmailExplainer with subject/body."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "email",
            "subject": "URGENT: Account Suspension Warning",
            "input": "Dear user, your account has been flagged. Verify immediately at http://secure-bank.top."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "email")
        self.assertEqual(data["resolved_channel"], "email")
        self.assertEqual(data["prediction"], "Likely Phishing")
        self.assertEqual(data["tier1"]["verdict"], "Likely Phishing")
        self.assertGreater(data["confidence"], 0.90)
        self.assertGreater(data["risk_score"], 90.0)
        self.assertEqual(len(data["tier3"]["feature_contributions"]), 6)
        self.assertIn("top_text_signals", data["tier3"])
        # Verify subject/body sources are preserved
        sources = {t["source"] for t in data["tier3"]["top_text_signals"]}
        self.assertIn("subject", sources)
        self.assertIn("body", sources)

    def test_04_explicit_url_api(self):
        """Verify explicit channel='url' invokes URLExplainer under locked threshold."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "url",
            "input": "http://login.chase.com.security-verify-session.top/auth/resolve?token=verify"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "url")
        self.assertEqual(data["resolved_channel"], "url")
        self.assertEqual(data["prediction"], "Malicious URL")
        self.assertEqual(data["tier1"]["verdict"], "Malicious URL")
        self.assertGreater(data["confidence"], 0.90)
        self.assertGreater(data["risk_score"], 90.0)
        self.assertEqual(len(data["tier3"]["feature_contributions"]), 15)
        # URL has no text signals; section is omitted
        self.assertNotIn("top_text_signals", data["tier3"])

    def test_05_auto_detect_url_api(self):
        """Verify channel='auto' routes URL format to URL pipeline."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "auto",
            "input": "https://paypal-update-billing.com/login"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["resolved_channel"], "url")
        self.assertEqual(data["channel"], "url")

    def test_06_auto_detect_email_api(self):
        """Verify channel='auto' routes Email format to Email pipeline."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "auto",
            "input": "Subject: Invoice Overdue Notice\n\nPlease find attached the unpaid invoice for payment."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["resolved_channel"], "email")
        self.assertEqual(data["channel"], "email")

    def test_07_auto_detect_sms_api(self):
        """Verify channel='auto' falls back to SMS for general messages."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "auto",
            "input": "Hey mom, I will be home by 6pm for dinner."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["resolved_channel"], "sms")
        self.assertEqual(data["channel"], "sms")
        self.assertEqual(data["prediction"], "Safe & Legitimate")

    def test_08_explicit_override_of_auto(self):
        """Verify explicit channel override is honored even when content resembles another channel."""
        # Content looks like a URL, but channel is explicitly requested as 'sms'
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "sms",
            "input": "https://suspicious-link.com/click"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["resolved_channel"], "sms")
        self.assertEqual(data["channel"], "sms")

    def test_09_empty_input_error(self):
        """Verify empty input is rejected with HTTP 400."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "sms",
            "input": "   "
        })
        self.assertEqual(status, 400)
        self.assertIn("detail", data)
        self.assertIn("cannot be empty", data["detail"])

    def test_10_unsupported_channel_error(self):
        """Verify unsupported channel is rejected with HTTP 400."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "voice",
            "input": "Hello this is a voice call"
        })
        self.assertEqual(status, 400)
        self.assertIn("Unsupported channel", data["detail"])

    def test_11_qr_channel_api(self):
        """Verify QR channel via /api/analyze handles base64 image and returns controlled 422 for unprocessable image."""
        status, data = self._call_api("/api/analyze", json_body={
            "channel": "qr",
            "input": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAA..."
        })
        self.assertEqual(status, 422)
        self.assertIn("detail", data)


if __name__ == "__main__":
    unittest.main()
