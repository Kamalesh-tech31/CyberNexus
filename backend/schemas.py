"""
CyberNexus - API Request/Response Schemas
Phase 6D: Stable schemas for progressive-disclosure API contract.
"""

from typing import List, Dict, Optional, Any, Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    version: str


class AnalysisRequest(BaseModel):
    channel: str = Field(
        default="auto",
        description="Target analysis channel: 'auto', 'sms', 'email', 'url', 'qr'"
    )
    input: str = Field(
        default="",
        description="Input text, URL, or message body to analyze"
    )
    subject: Optional[str] = Field(
        default=None,
        description="Optional email subject line (Email channel only)"
    )


# ── Tier 1 Schemas ─────────────────────────────────────────────────────────

class Tier1Schema(BaseModel):
    verdict: str
    confidence: float
    confidence_band: Literal["high", "medium", "low"]
    summary: str


# ── Tier 2 Schemas ─────────────────────────────────────────────────────────

class Tier2FlagSchema(BaseModel):
    label: str
    status: str
    detail: str


class Tier2Schema(BaseModel):
    flags: List[Tier2FlagSchema]
    confidence_breakdown: Dict[str, float]


# ── Tier 3 Schemas ─────────────────────────────────────────────────────────

class FeatureContributionSchema(BaseModel):
    feature: str
    value: float
    contribution: float
    direction: Literal["increases_risk", "decreases_risk"]
    feature_label: Optional[str] = None
    raw_value_display: Optional[str] = None
    description: Optional[str] = None


class TextSignalItemSchema(BaseModel):
    token: str
    weight: float
    contribution: Optional[float] = None
    direction: Optional[Literal["increases_risk", "decreases_risk"]] = None
    source: Optional[Literal["subject", "body"]] = None


class ModelMetadataSummarySchema(BaseModel):
    model_name: Optional[str] = None
    architecture: Optional[str] = None
    calibration: Optional[str] = None
    model_version: str
    trained_on: str
    operational_threshold: Optional[float] = None
    note: str


class Tier3Schema(BaseModel):
    feature_contributions: List[FeatureContributionSchema]
    top_text_signals: Optional[List[TextSignalItemSchema]] = None
    bias_term: Optional[float] = None
    model_metadata: ModelMetadataSummarySchema


# ── Unified Progressive-Disclosure API Response ────────────────────────────

class AnalysisResponse(BaseModel):
    channel: str
    prediction: str
    risk_score: float
    confidence: float
    reasons: List[str]
    indicators: List[str]
    recommendation: str
    raw_input_ref: Optional[str] = None
    tier1: Tier1Schema
    tier2: Tier2Schema
    tier3: Tier3Schema
    resolved_channel: str
    # QR-specific fields (only present when channel == 'qr')
    qr_decoded_payload: Optional[str] = None
    qr_payload_type: Optional[str] = None
    qr_delegated_url: Optional[str] = None
    # Persistence & Versioning fields (Phase 6F-3)
    analysis_id: Optional[str] = None
    created_at: Optional[str] = None
    schema_version: Optional[str] = "1.0"


# ── QR Non-URL Response (no ML classification) ─────────────────────────────

class QRNonUrlResponse(BaseModel):
    """
    Response for QR codes that do not contain a URL payload.
    No ML classification is performed; the decoded payload is returned as-is.
    """
    channel: str = "qr"
    resolved_channel: str = "qr"
    qr_decoded_payload: str
    qr_payload_type: str
    prediction: str = "Non-URL QR Payload"
    risk_score: float = 0.0
    confidence: float = 0.0
    reasons: List[str]
    indicators: List[str] = []
    recommendation: str
    # Persistence & Versioning fields (Phase 6F-3)
    analysis_id: Optional[str] = None
    created_at: Optional[str] = None
    schema_version: Optional[str] = "1.0"


class QRMultipleCodeResponse(BaseModel):
    """
    Response when multiple QR codes are detected in one image.
    No single classification is provided.
    """
    channel: str = "qr"
    resolved_channel: str = "qr"
    prediction: str = "Multiple QR Codes Detected"
    qr_codes_detected: int
    qr_payloads: List[str]
    qr_payload_types: List[str]
    risk_score: float = 0.0
    confidence: float = 0.0
    reasons: List[str]
    indicators: List[str] = []
    recommendation: str
    # Persistence & Versioning fields (Phase 6F-3)
    analysis_id: Optional[str] = None
    created_at: Optional[str] = None
    schema_version: Optional[str] = "1.0"
