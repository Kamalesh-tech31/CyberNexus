"""
CyberNexus - QR Decode Service
Phase QR: Real QR code decoding using zxing-cpp + Pillow.

Accepts image bytes, decodes all QR codes found, classifies payload type.
Does NOT execute payloads, does NOT make network requests, does NOT use allowlists.
"""

from __future__ import annotations

import io
import re
import base64
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

from PIL import Image, UnidentifiedImageError
import zxingcpp


# ── Payload Type Classification ─────────────────────────────────────────────

class QRPayloadType(str, Enum):
    URL      = "url"
    WIFI     = "wifi"
    VCARD    = "vcard"
    MECARD   = "mecard"
    GEO      = "geo"
    MAILTO   = "mailto"
    TEL      = "tel"
    SMS_LINK = "sms_link"
    TEXT     = "text"


# Patterns for non-URL payload types (checked before URL)
_WIFI_RE    = re.compile(r'^WIFI:', re.IGNORECASE)
_VCARD_RE   = re.compile(r'^BEGIN:VCARD', re.IGNORECASE)
_MECARD_RE  = re.compile(r'^MECARD:', re.IGNORECASE)
_GEO_RE     = re.compile(r'^geo:', re.IGNORECASE)
_MAILTO_RE  = re.compile(r'^mailto:', re.IGNORECASE)
_TEL_RE     = re.compile(r'^tel:', re.IGNORECASE)
_SMS_RE     = re.compile(r'^smsto?:', re.IGNORECASE)
_URL_RE     = re.compile(
    r'^(https?://|ftp://|www\.)\S+$'
    r'|^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?'
    r'(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*'
    r'\.[a-zA-Z]{2,}(/\S*)?$',
    re.IGNORECASE,
)


def classify_payload(raw: str) -> QRPayloadType:
    """Determine the semantic type of a decoded QR string."""
    s = raw.strip()
    if _WIFI_RE.match(s):   return QRPayloadType.WIFI
    if _VCARD_RE.match(s):  return QRPayloadType.VCARD
    if _MECARD_RE.match(s): return QRPayloadType.MECARD
    if _GEO_RE.match(s):    return QRPayloadType.GEO
    if _MAILTO_RE.match(s): return QRPayloadType.MAILTO
    if _TEL_RE.match(s):    return QRPayloadType.TEL
    if _SMS_RE.match(s):    return QRPayloadType.SMS_LINK
    if _URL_RE.match(s):    return QRPayloadType.URL
    return QRPayloadType.TEXT


# ── Result Dataclasses ───────────────────────────────────────────────────────

@dataclass
class DecodedQR:
    """A single successfully decoded QR code from the image."""
    raw_payload: str
    payload_type: QRPayloadType
    format: str  # e.g. "QRCode", "DataMatrix", etc.


@dataclass
class QRDecodeResult:
    """
    Outcome of a QR decode attempt on one image.

    Exactly one of (codes, error) is meaningful:
      - codes is non-empty  → one or more codes decoded
      - error is set        → image problem (bad format, no QR, corrupt)
    """
    codes: List[DecodedQR]
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return len(self.codes) > 0 and self.error is None

    @property
    def multiple(self) -> bool:
        return len(self.codes) > 1


# ── Core Decode Function ─────────────────────────────────────────────────────

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB hard limit


def decode_qr_image(image_bytes: bytes) -> QRDecodeResult:
    """
    Attempt to decode all QR codes (and other 2D/1D barcodes) from raw image bytes.

    Args:
        image_bytes: Raw bytes of a PNG, JPEG, WEBP, BMP, or GIF image.

    Returns:
        QRDecodeResult with `codes` populated on success,
        or `error` string describing the failure (no exception raised).
    """
    if len(image_bytes) > _MAX_IMAGE_BYTES:
        return QRDecodeResult(
            codes=[],
            error=f"Image file too large ({len(image_bytes) // 1024} KB). Maximum allowed: 10 MB."
        )

    # 1. Decode image via Pillow
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()  # Force full read; catches truncated files
    except UnidentifiedImageError:
        return QRDecodeResult(
            codes=[],
            error="Unrecognised image format. Upload a PNG, JPEG, WEBP, or BMP file."
        )
    except Exception as exc:
        return QRDecodeResult(
            codes=[],
            error=f"Unable to open image: {exc!s}"
        )

    # 2. Convert to RGB for maximum zxing-cpp compatibility
    try:
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
    except Exception as exc:
        return QRDecodeResult(codes=[], error=f"Image conversion failed: {exc!s}")

    # 3. Run zxing-cpp decoder (reads all formats including QR, DataMatrix, etc.)
    try:
        results = zxingcpp.read_barcodes(img)
    except Exception as exc:
        return QRDecodeResult(codes=[], error=f"Barcode decoder error: {exc!s}")

    # Filter to valid, non-empty decoded results
    valid = [r for r in results if r.valid and r.text]

    if not valid:
        return QRDecodeResult(
            codes=[],
            error="No QR code detected in the uploaded image. Ensure the image contains a clear, unobstructed QR code."
        )

    # 4. Build decoded output
    decoded = []
    for r in valid:
        payload = r.text
        ptype   = classify_payload(payload)
        fmt     = str(r.format).replace("BarcodeFormat.", "")
        decoded.append(DecodedQR(raw_payload=payload, payload_type=ptype, format=fmt))

    return QRDecodeResult(codes=decoded)


def decode_qr_base64_or_bytes(data: Union[str, bytes]) -> QRDecodeResult:
    """
    Accepts raw image bytes or a string (which may be a base64 data URI or raw base64 string),
    and decodes QR codes.
    """
    if isinstance(data, bytes):
        return decode_qr_image(data)

    if not isinstance(data, str):
        return QRDecodeResult(codes=[], error="Invalid input type: expected bytes or base64 string.")

    cleaned = data.strip()
    if not cleaned:
        return QRDecodeResult(codes=[], error="Empty image data.")

    # Strip data URI header if present (e.g. data:image/png;base64,....)
    if "," in cleaned and cleaned.startswith("data:"):
        _, b64_part = cleaned.split(",", 1)
    else:
        b64_part = cleaned

    try:
        raw_bytes = base64.b64decode(b64_part, validate=True)
    except Exception as exc:
        return QRDecodeResult(codes=[], error=f"Invalid base64 encoding: {exc!s}")

    return decode_qr_image(raw_bytes)


