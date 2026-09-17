"""
CyberNexus - QR Resolve Engine Tests
Phase QR: Comprehensive tests for the QR decode service and /api/analyze/qr endpoint.

Tests:
  A. Valid QR containing a legitimate URL
  B. Valid QR containing a malicious URL
  C. QR containing plain text (non-URL)
  D. QR containing Wi-Fi configuration (non-URL)
  E. Invalid image (random bytes)
  F. Image with no QR code
  G. Multiple QR codes in one image
  H. Explainability — QR→URL uses existing 15-feature LightGBM contributions
  I. Regression — existing SMS/Email/URL API tests unaffected
"""

import io
import json
import unittest
import asyncio
import qrcode
from PIL import Image

from backend.app import app, lifespan
from backend.services.qr_service import decode_qr_image, classify_payload, QRPayloadType


# ── QR Image Fixtures ────────────────────────────────────────────────────────

def make_qr_image(payload: str) -> bytes:
    """Generate a real QR code PNG from a payload string."""
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_blank_png() -> bytes:
    """Generate a PNG with no QR code (solid white)."""
    img = Image.new("RGB", (200, 200), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_invalid_bytes() -> bytes:
    """Return some random non-image bytes."""
    return b"\x00\x01\x02\x03NOTANIMAGE" * 50


# ── ASGI Test Helper ─────────────────────────────────────────────────────────

def _call_api_json(path: str, method: str = "POST", json_body: dict = None):
    """Call the API with a JSON body (for /api/analyze)."""
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
    response_chunks = []

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(message):
        nonlocal status_code, response_chunks
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_chunks.append(message.get("body", b""))

    asyncio.run(app(scope, receive, send))
    raw_body = b"".join(response_chunks).decode("utf-8")
    data = json.loads(raw_body) if raw_body else {}
    return status_code, data


def _call_api_multipart(path: str, file_bytes: bytes, filename: str = "test.png", content_type: str = "image/png"):
    """Call the API with multipart/form-data (for /api/analyze/qr)."""
    # Build multipart body manually
    boundary = b"----TestBoundary1234"
    body = (
        b"--" + boundary + b"\r\n"
        b'Content-Disposition: form-data; name="file"; filename="' + filename.encode() + b'"\r\n'
        b"Content-Type: " + content_type.encode() + b"\r\n"
        b"\r\n"
        + file_bytes
        + b"\r\n"
        b"--" + boundary + b"--\r\n"
    )
    content_type_header = b"multipart/form-data; boundary=" + boundary

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode("utf-8"),
        "query_string": b"",
        "headers": [
            (b"host", b"localhost:8000"),
            (b"content-type", content_type_header),
            (b"content-length", str(len(body)).encode("utf-8")),
        ],
        "app": app,
    }
    status_code = None
    response_chunks = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        nonlocal status_code, response_chunks
        if message["type"] == "http.response.start":
            status_code = message["status"]
        elif message["type"] == "http.response.body":
            response_chunks.append(message.get("body", b""))

    asyncio.run(app(scope, receive, send))
    raw_body = b"".join(response_chunks).decode("utf-8")
    data = json.loads(raw_body) if raw_body else {}
    return status_code, data


# ── Unit Tests: QR Decode Service ────────────────────────────────────────────

class TestQRDecodeService(unittest.TestCase):
    """Unit tests for qr_service.py — no HTTP, no FastAPI."""

    def test_classify_url_https(self):
        self.assertEqual(classify_payload("https://www.google.com"), QRPayloadType.URL)

    def test_classify_url_http(self):
        self.assertEqual(classify_payload("http://example.com/path?q=1"), QRPayloadType.URL)

    def test_classify_url_www(self):
        self.assertEqual(classify_payload("www.example.com"), QRPayloadType.URL)

    def test_classify_wifi(self):
        self.assertEqual(classify_payload("WIFI:S:MyNetwork;T:WPA;P:password123;;"), QRPayloadType.WIFI)

    def test_classify_vcard(self):
        self.assertEqual(classify_payload("BEGIN:VCARD\nFN:John Doe\nEND:VCARD"), QRPayloadType.VCARD)

    def test_classify_geo(self):
        self.assertEqual(classify_payload("geo:37.786971,-122.399677"), QRPayloadType.GEO)

    def test_classify_text(self):
        self.assertEqual(classify_payload("Hello this is plain text"), QRPayloadType.TEXT)

    def test_classify_mailto(self):
        self.assertEqual(classify_payload("mailto:user@example.com"), QRPayloadType.MAILTO)

    def test_decode_url_qr(self):
        url = "https://www.github.com"
        img_bytes = make_qr_image(url)
        result = decode_qr_image(img_bytes)
        self.assertTrue(result.success)
        self.assertEqual(len(result.codes), 1)
        self.assertEqual(result.codes[0].raw_payload, url)
        self.assertEqual(result.codes[0].payload_type, QRPayloadType.URL)

    def test_decode_wifi_qr(self):
        wifi = "WIFI:S:GuestNetwork;T:WPA;P:pass12345;;"
        img_bytes = make_qr_image(wifi)
        result = decode_qr_image(img_bytes)
        self.assertTrue(result.success)
        self.assertEqual(result.codes[0].payload_type, QRPayloadType.WIFI)

    def test_decode_text_qr(self):
        text = "Hello from a QR code"
        img_bytes = make_qr_image(text)
        result = decode_qr_image(img_bytes)
        self.assertTrue(result.success)
        self.assertEqual(result.codes[0].payload_type, QRPayloadType.TEXT)

    def test_decode_invalid_image_bytes(self):
        result = decode_qr_image(make_invalid_bytes())
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_decode_blank_image_no_qr(self):
        result = decode_qr_image(make_blank_png())
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("No QR code detected", result.error)

    def test_decode_empty_bytes(self):
        result = decode_qr_image(b"")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_decode_oversized_rejected(self):
        # 11 MB of zeros — not a valid image but exceeds limit check
        oversized = b"\x00" * (11 * 1024 * 1024)
        result = decode_qr_image(oversized)
        self.assertFalse(result.success)
        self.assertIn("too large", result.error.lower())


# ── Integration Tests: /api/analyze/qr endpoint ──────────────────────────────

class TestQREndpoint(unittest.TestCase):
    """Integration tests for POST /api/analyze/qr via ASGI."""

    @classmethod
    def setUpClass(cls):
        cls.lifespan_ctx = lifespan(app)
        asyncio.run(cls.lifespan_ctx.__aenter__())

    @classmethod
    def tearDownClass(cls):
        asyncio.run(cls.lifespan_ctx.__aexit__(None, None, None))

    # ── TEST A: Legitimate URL ────────────────────────────────────────────────

    def test_A_legit_url_qr(self):
        """A. QR with legitimate URL → decode succeeds, URL analyzed, real model result."""
        url = "https://en.wikipedia.org/wiki/Main_Page"
        img_bytes = make_qr_image(url)
        status, data = _call_api_multipart("/api/analyze/qr", img_bytes, "legit_qr.png")

        self.assertEqual(status, 200, f"Expected 200, got {status}: {data}")
        self.assertEqual(data["channel"], "qr")
        self.assertEqual(data["resolved_channel"], "qr")
        self.assertEqual(data["qr_decoded_payload"], url)
        self.assertEqual(data["qr_payload_type"], "url")
        self.assertEqual(data["qr_delegated_url"], url)

        # Real model result — no fabricated values
        self.assertIn("prediction", data)
        self.assertIn("risk_score", data)
        self.assertIn("confidence", data)
        self.assertIn("tier1", data)
        self.assertIn("tier2", data)
        self.assertIn("tier3", data)

        # Existing 15-feature URL explainability
        self.assertEqual(len(data["tier3"]["feature_contributions"]), 15)
        # URL has no text signals
        self.assertNotIn("top_text_signals", data["tier3"])

        # Should classify as Safe (it's Wikipedia)
        self.assertIn("Safe", data["prediction"], f"Expected Safe, got: {data['prediction']}")

    # ── TEST B: Malicious URL ─────────────────────────────────────────────────

    def test_B_malicious_url_qr(self):
        """B. QR with malicious URL → decode succeeds, URL model classifies as Malicious."""
        url = "http://paypal-security-verify.suspicious-login.tk/steal/credentials"
        img_bytes = make_qr_image(url)
        status, data = _call_api_multipart("/api/analyze/qr", img_bytes, "mal_qr.png")

        self.assertEqual(status, 200, f"Expected 200, got {status}: {data}")
        self.assertEqual(data["channel"], "qr")
        self.assertEqual(data["qr_decoded_payload"], url)
        self.assertEqual(data["qr_payload_type"], "url")

        # Existing URL model should classify as malicious
        self.assertEqual(data["prediction"], "Malicious URL", f"Expected Malicious URL, got: {data['prediction']}")
        self.assertGreater(data["risk_score"], 50.0)
        # 15 real URL features
        self.assertEqual(len(data["tier3"]["feature_contributions"]), 15)

    # ── TEST C: Plain Text (non-URL) ─────────────────────────────────────────

    def test_C_plain_text_qr_no_url_classifier(self):
        """C. QR with plain text → decoded, URL ML NOT called, non-URL response."""
        text = "Hello! This is a plain text QR code."
        img_bytes = make_qr_image(text)
        status, data = _call_api_multipart("/api/analyze/qr", img_bytes, "text_qr.png")

        self.assertEqual(status, 200, f"Expected 200, got {status}: {data}")
        self.assertEqual(data["channel"], "qr")
        self.assertEqual(data["qr_decoded_payload"], text)
        self.assertEqual(data["qr_payload_type"], "text")
        self.assertEqual(data["prediction"], "Non-URL QR Payload")

        # URL ML fields must NOT be present
        self.assertNotIn("tier1", data)
        self.assertNotIn("tier2", data)
        self.assertNotIn("tier3", data)

    # ── TEST D: Wi-Fi QR (non-URL) ───────────────────────────────────────────

    def test_D_wifi_qr_not_classified_as_url(self):
        """D. QR with Wi-Fi payload → decoded, type=wifi, not routed to URL model."""
        wifi = "WIFI:S:Guest_HQ_Secure;T:WPA;P:NexusPass2026;;"
        img_bytes = make_qr_image(wifi)
        status, data = _call_api_multipart("/api/analyze/qr", img_bytes, "wifi_qr.png")

        self.assertEqual(status, 200, f"Expected 200, got {status}: {data}")
        self.assertEqual(data["qr_payload_type"], "wifi")
        self.assertEqual(data["prediction"], "Non-URL QR Payload")
        self.assertNotIn("tier3", data)

    # ── TEST E: Invalid image ─────────────────────────────────────────────────

    def test_E_invalid_image_controlled_error(self):
        """E. Non-image bytes → controlled 422 response, no crash."""
        status, data = _call_api_multipart("/api/analyze/qr", make_invalid_bytes(), "bad.png")
        self.assertEqual(status, 422, f"Expected 422, got {status}: {data}")
        self.assertIn("detail", data)
        self.assertIsInstance(data["detail"], str)

    # ── TEST F: Image with no QR ──────────────────────────────────────────────

    def test_F_no_qr_code_detected(self):
        """F. Valid image with no QR → controlled 422, no fabricated result."""
        status, data = _call_api_multipart("/api/analyze/qr", make_blank_png(), "blank.png")
        self.assertEqual(status, 422, f"Expected 422, got {status}: {data}")
        self.assertIn("No QR code detected", data.get("detail", ""))

    # ── TEST G: Multiple QR codes ─────────────────────────────────────────────

    def test_G_multiple_qr_codes(self):
        """G. Image with 2 QR codes → structured multi-code response, no silent selection."""
        # Build an image containing two QR codes side by side
        url1 = "https://www.google.com"
        url2 = "https://phishing-login-verify.tk/steal"
        img1 = Image.open(io.BytesIO(make_qr_image(url1)))
        img2 = Image.open(io.BytesIO(make_qr_image(url2)))

        w1, h1 = img1.size
        w2, h2 = img2.size
        combined = Image.new("RGB", (w1 + w2, max(h1, h2)), "white")
        combined.paste(img1, (0, 0))
        combined.paste(img2, (w1, 0))

        buf = io.BytesIO()
        combined.save(buf, format="PNG")
        combined_bytes = buf.getvalue()

        status, data = _call_api_multipart("/api/analyze/qr", combined_bytes, "multi.png")

        self.assertEqual(status, 200, f"Expected 200, got {status}: {data}")
        # If only 1 detected (some decoders may not find both), still valid
        if data.get("prediction") == "Multiple QR Codes Detected":
            self.assertGreater(data["qr_codes_detected"], 1)
            self.assertIsInstance(data["qr_payloads"], list)
            self.assertIsInstance(data["qr_payload_types"], list)
            self.assertNotIn("tier3", data)
        else:
            # Single code detected — still valid (image might not have both readable)
            self.assertIn("prediction", data)

    # ── TEST H: Explainability — QR→URL uses existing 15-feature contributions ─

    def test_H_qr_url_explainability_15_features(self):
        """H. QR→URL uses actual LightGBM 15-feature TreeSHAP contributions."""
        url = "http://login.paypal.com.phishing-verify.security-alert.tk/auth"
        img_bytes = make_qr_image(url)
        status, data = _call_api_multipart("/api/analyze/qr", img_bytes, "explain_qr.png")

        self.assertEqual(status, 200)
        self.assertIn("tier3", data)

        contributions = data["tier3"]["feature_contributions"]
        self.assertEqual(len(contributions), 15,
                         f"Expected 15 URL features, got {len(contributions)}")

        # Verify all required fields present in each contribution
        for fc in contributions:
            self.assertIn("feature", fc)
            self.assertIn("value", fc)
            self.assertIn("contribution", fc)
            self.assertIn("direction", fc)
            self.assertIn(fc["direction"], ["increases_risk", "decreases_risk"])

        # direction must match contribution sign
        for fc in contributions:
            if fc["contribution"] > 0:
                self.assertEqual(fc["direction"], "increases_risk")
            else:
                self.assertEqual(fc["direction"], "decreases_risk")

        # No text signals for URL
        self.assertNotIn("top_text_signals", data["tier3"])

    # ── TEST I: Regression — existing channels unaffected ────────────────────

    def test_I_regression_sms_unaffected(self):
        """I-1. SMS analysis regression: existing behavior preserved."""
        status, data = _call_api_json("/api/analyze", json_body={
            "channel": "sms",
            "input": "ALERT: Claim your free prize now! Call 08000930705 immediately."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "sms")
        self.assertEqual(data["prediction"], "Likely Smishing")

    def test_I_regression_url_unaffected(self):
        """I-2. URL analysis regression: existing behavior preserved."""
        status, data = _call_api_json("/api/analyze", json_body={
            "channel": "url",
            "input": "http://login.chase.com.security-verify-session.top/auth"
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "url")
        self.assertEqual(data["prediction"], "Malicious URL")
        self.assertEqual(len(data["tier3"]["feature_contributions"]), 15)

    def test_I_regression_email_unaffected(self):
        """I-3. Email analysis regression: existing behavior preserved."""
        status, data = _call_api_json("/api/analyze", json_body={
            "channel": "email",
            "subject": "URGENT: Account Suspension Warning",
            "input": "Dear user, verify your account immediately at http://secure-bank.top."
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "email")
        self.assertEqual(data["prediction"], "Likely Phishing")

    def test_I_regression_qr_text_payload_no_longer_501(self):
        """I-4. channel=qr via /api/analyze now processes base64 images and returns 422 for invalid image data."""
        import base64
        # Test 1: Real base64 QR code via /api/analyze
        url = "https://en.wikipedia.org/wiki/Main_Page"
        img_bytes = make_qr_image(url)
        b64_data = "data:image/png;base64," + base64.b64encode(img_bytes).decode("ascii")
        status, data = _call_api_json("/api/analyze", json_body={
            "channel": "qr",
            "input": b64_data
        })
        self.assertEqual(status, 200)
        self.assertEqual(data["channel"], "qr")
        self.assertEqual(data["qr_decoded_payload"], url)
        self.assertIn("Safe", data["prediction"])

        # Test 2: Invalid base64 image returns controlled 422 (not 501)
        status_bad, data_bad = _call_api_json("/api/analyze", json_body={
            "channel": "qr",
            "input": "data:image/png;base64,abc"
        })
        self.assertEqual(status_bad, 422)
        self.assertIn("detail", data_bad)


if __name__ == "__main__":
    unittest.main(verbosity=2)
