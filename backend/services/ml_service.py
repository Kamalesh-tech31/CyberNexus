"""
CyberNexus - ML Inference Singleton Service
Phase 6B: Integration wrapper managing in-memory singleton explainers and models.
"""

import os
from pathlib import Path
from typing import Optional

from ml.explainability.sms_explain import SMSExplainer
from ml.explainability.email_explain import EmailExplainer
from ml.explainability.url_explain import URLExplainer
from ml.explainability.explanation_types import UnifiedExplanation


class MLService:
    """
    Singleton ML Service managing in-memory calibrated models and explainers.
    Instantiated once during FastAPI application startup lifespan.
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            # Default to the project root directory
            base_dir = str(Path(__file__).resolve().parent.parent.parent)
        self.base_dir = base_dir

        # Instantiate explainers (loads models and vectorizers once into memory)
        self.sms_explainer = SMSExplainer(base_dir=self.base_dir)
        self.email_explainer = EmailExplainer(base_dir=self.base_dir)
        self.url_explainer = URLExplainer(base_dir=self.base_dir)

    def analyze_sms(self, message: str) -> UnifiedExplanation:
        """
        Execute model inference and model-grounded explainability for SMS.
        Operational threshold: 0.50.
        """
        return self.sms_explainer.explain(message)

    def analyze_email(self, subject: str = "", body: str = "") -> UnifiedExplanation:
        """
        Execute model inference and model-grounded explainability for Email.
        Operational threshold: 0.50.
        """
        return self.email_explainer.explain(subject=subject, body=body)

    def analyze_url(self, raw_url: str) -> UnifiedExplanation:
        """
        Execute model inference and model-grounded explainability for URL.
        Operational threshold: 0.2500 (raw) / 0.2526 (calibrated).
        """
        return self.url_explainer.explain(raw_url=raw_url)
