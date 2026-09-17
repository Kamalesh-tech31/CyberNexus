"""
CyberNexus - Phase 5B: URL Model-Grounded Explainer
Channel: URL (LightGBM Champion + Platt Sigmoid Calibration)

Uses LightGBM native TreeSHAP prediction contribution:
booster_.predict(X_df, pred_contrib=True)
- positive contribution -> increases_risk (pushes raw margin toward Bad URL)
- negative contribution -> decreases_risk (pushes raw margin toward Good URL)

Operational threshold:
- Raw threshold: 0.2500
- Calibrated equivalent threshold: 0.2526
"""

import os
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, List

from ml.feature_engineering.url.url_features import extract_single_url_features
from ml.explainability.explanation_types import (
    StructuralSignal,
    ModelMetadata,
    UnifiedExplanation,
    URL_STRUCTURAL_DESCRIPTIONS
)


class URLExplainer:
    def __init__(self, base_dir: str = r"c:\Users\Digit\Desktop\CyberNexus"):
        self.base_dir = base_dir
        self.calibrated_model_path = os.path.join(base_dir, "ml", "models", "url", "calibrated", "url_calibrated_model.joblib")
        
        # Load calibrated model
        self.calibrated_model = joblib.load(self.calibrated_model_path)
        
        # Extract underlying LightGBM model and booster
        base_est = self.calibrated_model.estimator
        if hasattr(base_est, 'estimator'):
            self.base_lgbm = base_est.estimator
        else:
            self.base_lgbm = base_est
            
        self.booster = self.base_lgbm.booster_
        self.feature_names = [
            "url_length",
            "hostname_length",
            "path_length",
            "query_length",
            "dot_count",
            "hyphen_count",
            "digit_count",
            "special_char_count",
            "subdomain_depth",
            "https_presence",
            "ip_hostname",
            "suspicious_token_presence",
            "at_symbol_presence",
            "embedded_double_slash_count",
            "digit_to_length_ratio"
        ]

    def explain(self, raw_url: str) -> UnifiedExplanation:
        # 1. Feature Extraction (15 structural features)
        feat_dict = extract_single_url_features(raw_url)
        df_feats = pd.DataFrame([feat_dict])[self.feature_names]

        # 2. Prediction & Calibration
        raw_prob_bad = float(self.base_lgbm.predict_proba(df_feats)[0, 1])
        calibrated_prob_bad = float(self.calibrated_model.predict_proba(df_feats)[0, 1])
        
        # Locked operational threshold
        operational_threshold_raw = 0.2500
        operational_threshold_calib = 0.2526
        
        predicted_class = 1 if calibrated_prob_bad >= operational_threshold_calib else 0
        predicted_label = "Malicious URL" if predicted_class == 1 else "Safe & Legitimate"
        confidence_pct = round((calibrated_prob_bad if predicted_class == 1 else (1.0 - calibrated_prob_bad)) * 100.0, 1)

        # 3. Model-Grounded Prediction Contributions (Native LightGBM TreeSHAP)
        # Returns array of shape (1, 16): 15 feature contributions + 1 bias term
        contribs = self.booster.predict(df_feats, pred_contrib=True)[0]
        feature_contribs = contribs[:15]
        bias_term = float(contribs[15])

        structural_signals = []
        for i, feat_name in enumerate(self.feature_names):
            raw_val = float(feat_dict[feat_name])
            contrib_val = float(feature_contribs[i])
            direction = "increases_risk" if contrib_val > 0 else "decreases_risk"
            
            # Clean display representation
            if feat_name in ["suspicious_token_presence", "ip_hostname", "https_presence", "at_symbol_presence"]:
                display_val = "true" if raw_val == 1.0 else "false"
            elif feat_name in ["digit_to_length_ratio"]:
                display_val = f"{raw_val:.2f}"
            else:
                display_val = f"{int(raw_val)}"

            structural_signals.append(StructuralSignal(
                feature=feat_name,
                feature_label=feat_name.replace("_", " ").title(),
                value=round(raw_val, 4),
                raw_value_display=display_val,
                contribution=round(contrib_val, 4),
                direction=direction,
                description=URL_STRUCTURAL_DESCRIPTIONS.get(feat_name, "")
            ))

        # Sort by absolute contribution impact
        structural_signals.sort(key=lambda s: abs(s.contribution), reverse=True)

        # 4. Metadata
        metadata = ModelMetadata(
            channel="URL",
            model_name="LightGBM",
            architecture="Gradient Boosted Decision Tree (n_est=200, lr=0.1, leaves=63)",
            calibration="Sigmoid / Platt Scaling (CalibratedClassifierCV)",
            model_version="v1.0-lgbm-champion",
            trained_on="Phishing Site Predict 100k Stratified Sample (70,000 train URLs)",
            operational_threshold=operational_threshold_calib,
            note="Confidence reflects predicted probability, not certainty. URL analysis is based on static lexical structure without live network or external WHOIS/DNS queries."
        )

        return UnifiedExplanation(
            channel="url",
            predicted_class=predicted_class,
            predicted_label=predicted_label,
            raw_score=round(raw_prob_bad, 4),
            calibrated_confidence=confidence_pct,
            operational_threshold=operational_threshold_calib,
            structural_signals=structural_signals,
            text_signals=None,  # URL channel is structural only, text_signals omitted
            model_metadata=metadata,
            bias_term=round(bias_term, 4),
        )
