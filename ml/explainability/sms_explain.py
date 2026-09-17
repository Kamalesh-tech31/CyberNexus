"""
CyberNexus - Phase 5B: SMS Model-Grounded Explainer
Channel: SMS (Logistic Regression C=5.0, balanced + Platt Sigmoid Calibration)

Computes exact linear contributions:
contribution = feature_value × coefficient
- positive contribution -> increases_risk (pushes toward Spam)
- negative contribution -> decreases_risk (pushes toward Ham)
"""

import os
import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from typing import Dict, Any, List

from ml.feature_engineering.sms.sms_features import extract_sms_structural_features
from ml.explainability.explanation_types import (
    StructuralSignal,
    TextSignal,
    ModelMetadata,
    UnifiedExplanation,
    SMS_STRUCTURAL_DESCRIPTIONS
)


class SMSExplainer:
    def __init__(self, base_dir: str = r"c:\Users\Digit\Desktop\CyberNexus"):
        self.base_dir = base_dir
        self.calibrated_model_path = os.path.join(base_dir, "ml", "models", "sms", "calibrated", "sms_calibrated_model.joblib")
        self.tfidf_path = os.path.join(base_dir, "ml", "feature_engineering", "artifacts", "sms", "sms_tfidf_vectorizer.joblib")
        self.scaler_path = os.path.join(base_dir, "ml", "feature_engineering", "artifacts", "sms", "sms_structural_scaler.joblib")
        
        # Load artifacts
        self.calibrated_model = joblib.load(self.calibrated_model_path)
        self.tfidf_vectorizer = joblib.load(self.tfidf_path)
        self.scaler = joblib.load(self.scaler_path)
        
        # Extract underlying Logistic Regression model and weights
        base_est = self.calibrated_model.estimator
        if hasattr(base_est, 'estimator'):
            self.base_lr = base_est.estimator
        else:
            self.base_lr = base_est
            
        self.coef = self.base_lr.coef_[0]  # shape: (4006,)
        self.intercept = float(self.base_lr.intercept_[0])
        
        # Vocabulary mapping: token -> column_idx (0 to 3999)
        self.vocab = self.tfidf_vectorizer.vocabulary_
        self.feature_names_text = self.tfidf_vectorizer.get_feature_names_out()
        self.structural_names = [
            "message_length",
            "digit_to_length_ratio",
            "url_presence",
            "punctuation_density",
            "special_char_count",
            "uppercase_ratio"
        ]

    def explain(self, message: str) -> UnifiedExplanation:
        # 1. Feature Extraction
        msg_series = pd.Series([message])
        
        # Text TF-IDF (4,000 features)
        X_tfidf = self.tfidf_vectorizer.transform(msg_series)
        
        # Structural features (6 features)
        df_struct = extract_sms_structural_features(msg_series)
        X_struct_scaled = self.scaler.transform(df_struct)
        
        # Stack full feature vector (4,006 features)
        X_full = sparse.hstack([X_tfidf, sparse.csr_matrix(X_struct_scaled)], format='csr')
        
        # 2. Prediction & Calibration
        raw_prob_spam = float(self.base_lr.predict_proba(X_full)[0, 1])
        calibrated_prob_spam = float(self.calibrated_model.predict_proba(X_full)[0, 1])
        
        # Decision threshold = 0.50
        operational_threshold = 0.50
        predicted_class = 1 if calibrated_prob_spam >= operational_threshold else 0
        predicted_label = "Likely Smishing" if predicted_class == 1 else "Safe & Legitimate"
        confidence_pct = round((calibrated_prob_spam if predicted_class == 1 else (1.0 - calibrated_prob_spam)) * 100.0, 1)

        # 3. Model-Grounded Text Signal Contributions
        # Find non-zero tokens present in this specific message
        cx = X_tfidf.tocoo()
        text_signals_raw = []
        for col_idx, tfidf_val in zip(cx.col, cx.data):
            token_name = self.feature_names_text[col_idx]
            token_coef = float(self.coef[col_idx])
            contrib = float(tfidf_val * token_coef)
            direction = "increases_risk" if contrib > 0 else "decreases_risk"
            text_signals_raw.append(TextSignal(
                token=token_name,
                weight=round(float(tfidf_val), 4),
                contribution=round(contrib, 4),
                direction=direction,
                origin=None
            ))
            
        # Top 5 risk-increasing and top 3 risk-decreasing
        pos_text = sorted([s for s in text_signals_raw if s.direction == "increases_risk"], key=lambda x: x.contribution, reverse=True)[:5]
        neg_text = sorted([s for s in text_signals_raw if s.direction == "decreases_risk"], key=lambda x: abs(x.contribution), reverse=True)[:3]
        selected_text_signals = pos_text + neg_text

        # 4. Model-Grounded Structural Signal Contributions
        # Structural coefficients start at index 4000
        structural_signals = []
        for i, feat_name in enumerate(self.structural_names):
            coef_idx = 4000 + i
            feat_coef = float(self.coef[coef_idx])
            raw_val = float(df_struct[feat_name].iloc[0])
            scaled_val = float(X_struct_scaled[0, i])
            contrib = float(scaled_val * feat_coef)
            direction = "increases_risk" if contrib > 0 else "decreases_risk"
            
            # Format display value cleanly
            if feat_name in ["url_presence"]:
                display_val = "true" if raw_val == 1.0 else "false"
            elif feat_name in ["digit_to_length_ratio", "punctuation_density", "uppercase_ratio"]:
                display_val = f"{raw_val:.2f}"
            else:
                display_val = f"{int(raw_val)}"
                
            structural_signals.append(StructuralSignal(
                feature=feat_name,
                feature_label=feat_name.replace("_", " ").title(),
                value=round(raw_val, 4),
                raw_value_display=display_val,
                contribution=round(contrib, 4),
                direction=direction,
                description=SMS_STRUCTURAL_DESCRIPTIONS.get(feat_name, "")
            ))
            
        # Sort structural signals by absolute contribution impact
        structural_signals.sort(key=lambda s: abs(s.contribution), reverse=True)

        # 5. Metadata
        metadata = ModelMetadata(
            channel="SMS",
            model_name="Logistic Regression",
            architecture="L2-regularized linear model (C=5.0, class_weight='balanced')",
            calibration="Sigmoid / Platt Scaling (CalibratedClassifierCV)",
            model_version="v1.0-lr-balanced",
            trained_on="UCI SMS Spam Collection v1 (3,610 normalized messages)",
            operational_threshold=operational_threshold
        )

        return UnifiedExplanation(
            channel="sms",
            predicted_class=predicted_class,
            predicted_label=predicted_label,
            raw_score=round(raw_prob_spam, 4),
            calibrated_confidence=confidence_pct,
            operational_threshold=operational_threshold,
            structural_signals=structural_signals,
            text_signals={"tokens": selected_text_signals} if selected_text_signals else None,
            model_metadata=metadata
        )
