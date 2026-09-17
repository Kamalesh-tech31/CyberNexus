"""
CyberNexus - Phase 5B: Model-Grounded Explainability Types and Contract

This module defines the unified, model-grounded explainability contract across:
- SMS (Logistic Regression + TF-IDF + 6 Structural)
- Email (Logistic Regression + Subject TF-IDF + Body TF-IDF + 6 Structural)
- URL (LightGBM + 15 Structural Lexical Features)
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict


# Channel-specific human-readable descriptions for structural features
SMS_STRUCTURAL_DESCRIPTIONS = {
    "message_length": "Overall character length of the message",
    "digit_to_length_ratio": "Proportion of numeric digits in the message",
    "url_presence": "Presence of embedded web links or domain references",
    "punctuation_density": "Frequency of attention-grabbing punctuation (!, ?, $, %)",
    "special_char_count": "Count of non-standard special characters and symbols",
    "uppercase_ratio": "Proportion of uppercase letters across the message",
}

EMAIL_STRUCTURAL_DESCRIPTIONS = {
    "email_length": "Overall character length of email body content",
    "url_count": "Total count of web links embedded in the email",
    "digit_count": "Total count of numeric digits across subject and body",
    "exclamation_count": "Total count of exclamation marks across subject and body",
    "all_caps_word_count": "Count of full-caps words (2+ letters) indicating urgency",
    "urgency_keyword_count": "Matches for high-risk urgency phrases ('action required', 'suspended', etc.)",
}

URL_STRUCTURAL_DESCRIPTIONS = {
    "url_length": "Overall character length of the full URL",
    "hostname_length": "Character length of the domain/hostname component",
    "path_length": "Character length of the directory path string",
    "query_length": "Character length of the URL parameter query string",
    "dot_count": "Total count of dots across the entire URL",
    "hyphen_count": "Total count of hyphens in the URL structure",
    "digit_count": "Total count of numeric digits in the URL",
    "special_char_count": "Count of special delimiter and encoding characters",
    "suspicious_token_presence": "Presence of high-risk phishing keywords ('login', 'verify', 'account', etc.)",
    "subdomain_depth": "Depth of subdomain hierarchy (number of subdomain dot levels)",
    "ip_hostname": "Use of raw numeric IP address instead of registered domain name",
    "https_presence": "Use of standard secure HTTPS protocol scheme",
    "digit_to_length_ratio": "Proportion of numeric digits in the full URL string",
    "at_symbol_presence": "Presence of '@' character used to obscure real destination in URL",
    "embedded_double_slash_count": "Occurrences of consecutive '//' in path after scheme delimiter",
}

STRUCTURAL_FEATURE_DESCRIPTIONS = {
    **SMS_STRUCTURAL_DESCRIPTIONS,
    **EMAIL_STRUCTURAL_DESCRIPTIONS,
    **URL_STRUCTURAL_DESCRIPTIONS,
}


@dataclass
class StructuralSignal:
    feature: str
    feature_label: str
    value: float
    raw_value_display: str
    contribution: float
    direction: str  # "increases_risk" | "decreases_risk"
    description: str


@dataclass
class TextSignal:
    token: str
    weight: float
    contribution: float
    direction: str  # "increases_risk" | "decreases_risk"
    origin: Optional[str] = None  # "subject" | "body" for Email, None for SMS


@dataclass
class ModelMetadata:
    channel: str
    model_name: str
    architecture: str
    calibration: str
    model_version: str
    trained_on: str
    operational_threshold: float
    note: str = "Confidence reflects predicted probability, not certainty. Feature contributions describe model behavior and do not prove intent."


@dataclass
class UnifiedExplanation:
    channel: str
    predicted_class: int
    predicted_label: str
    raw_score: float
    calibrated_confidence: float  # Percentage 0.0 - 100.0
    operational_threshold: float
    structural_signals: List[StructuralSignal]
    text_signals: Optional[Dict[str, List[TextSignal]]]  # Dict with 'subject' and 'body' for email, 'tokens' for SMS, None for URL
    model_metadata: ModelMetadata
    bias_term: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
