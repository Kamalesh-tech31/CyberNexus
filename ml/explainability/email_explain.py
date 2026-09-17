"""
CyberNexus - Phase 5B: Email Model-Grounded Explainer
Channel: Email (Logistic Regression C=10.0 + Platt Sigmoid Calibration)

Computes exact linear contributions:
- Subject TF-IDF (indices 0..2999)
- Body TF-IDF (indices 3000..9999)
- 6 Structural features (indices 10000..10005)

Strictly separates Subject and Body text signals.
"""

import os
import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from typing import Dict, Any, List, Optional

from ml.feature_engineering.email.email_features import extract_email_structural_features
from ml.explainability.explanation_types import (
    StructuralSignal,
    TextSignal,
    ModelMetadata,
    UnifiedExplanation,
    EMAIL_STRUCTURAL_DESCRIPTIONS
)


class EmailExplainer:
    def __init__(self, base_dir: str = r"c:\Users\Digit\Desktop\CyberNexus"):
        self.base_dir = base_dir
        self.calibrated_model_path = os.path.join(base_dir, "ml", "models", "email", "calibrated", "email_calibrated_model.joblib")
        self.subject_tfidf_path = os.path.join(base_dir, "ml", "feature_engineering", "artifacts", "email", "email_subject_tfidf_vectorizer.joblib")
        self.body_tfidf_path = os.path.join(base_dir, "ml", "feature_engineering", "artifacts", "email", "email_body_tfidf_vectorizer.joblib")
        self.scaler_path = os.path.join(base_dir, "ml", "feature_engineering", "artifacts", "email", "email_structural_scaler.joblib")
        
        # Load artifacts
        self.calibrated_model = joblib.load(self.calibrated_model_path)
        self.subject_vectorizer = joblib.load(self.subject_tfidf_path)
        self.body_vectorizer = joblib.load(self.body_tfidf_path)
        self.scaler = joblib.load(self.scaler_path)
        
        # Extract underlying Logistic Regression model and weights
        base_est = self.calibrated_model.estimator
        if hasattr(base_est, 'estimator'):
            self.base_lr = base_est.estimator
        else:
            self.base_lr = base_est
            
        self.coef = self.base_lr.coef_[0]  # shape: (10006,)
        self.intercept = float(self.base_lr.intercept_[0])
        
        self.subject_features = self.subject_vectorizer.get_feature_names_out()
        self.body_features = self.body_vectorizer.get_feature_names_out()
        self.structural_names = [
            "email_length",
            "url_count",
            "digit_count",
            "exclamation_count",
            "all_caps_word_count",
            "urgency_keyword_count"
        ]

    def explain(self, subject: str = "", body: str = "") -> UnifiedExplanation:
        # Handle single text inputs if subject/body were passed as combined
        if not subject and "\n\n" in body:
            parts = body.split("\n\n", 1)
            subject = parts[0].replace("Subject:", "").strip()
            body = parts[1].strip()
            
        df_input = pd.DataFrame([{
            "subject": str(subject or ""),
            "body": str(body or "")
        }])

        # 1. Feature Extraction
        # Subject TF-IDF (3,000 features)
        X_subj = self.subject_vectorizer.transform(df_input['subject'])
        
        # Body TF-IDF (7,000 features)
        X_body = self.body_vectorizer.transform(df_input['body'])
        
        # Structural features (6 features)
        df_struct = extract_email_structural_features(df_input)
        X_struct_scaled = self.scaler.transform(df_struct)
        
        # Stack full feature matrix (10,006 features)
        X_full = sparse.hstack([X_subj, X_body, sparse.csr_matrix(X_struct_scaled)], format='csr')

        # 2. Prediction & Calibration
        raw_prob_phish = float(self.base_lr.predict_proba(X_full)[0, 1])
        calibrated_prob_phish = float(self.calibrated_model.predict_proba(X_full)[0, 1])
        
        # Decision threshold = 0.50
        operational_threshold = 0.50
        predicted_class = 1 if calibrated_prob_phish >= operational_threshold else 0
        predicted_label = "Likely Phishing" if predicted_class == 1 else "Safe & Legitimate"
        confidence_pct = round((calibrated_prob_phish if predicted_class == 1 else (1.0 - calibrated_prob_phish)) * 100.0, 1)

        # 3. Model-Grounded Subject Text Contributions (Indices 0..2999)
        cx_subj = X_subj.tocoo()
        subj_signals_raw = []
        for col_idx, tfidf_val in zip(cx_subj.col, cx_subj.data):
            token_name = self.subject_features[col_idx]
            coef_val = float(self.coef[col_idx])
            contrib = float(tfidf_val * coef_val)
            direction = "increases_risk" if contrib > 0 else "decreases_risk"
            subj_signals_raw.append(TextSignal(
                token=token_name,
                weight=round(float(tfidf_val), 4),
                contribution=round(contrib, 4),
                direction=direction,
                origin="subject"
            ))
        pos_subj = sorted([s for s in subj_signals_raw if s.direction == "increases_risk"], key=lambda x: x.contribution, reverse=True)[:5]
        neg_subj = sorted([s for s in subj_signals_raw if s.direction == "decreases_risk"], key=lambda x: abs(x.contribution), reverse=True)[:3]
        selected_subj_signals = pos_subj + neg_subj

        # 4. Model-Grounded Body Text Contributions (Indices 3000..9999)
        cx_body = X_body.tocoo()
        body_signals_raw = []
        for col_idx, tfidf_val in zip(cx_body.col, cx_body.data):
            token_name = self.body_features[col_idx]
            coef_val = float(self.coef[3000 + col_idx])
            contrib = float(tfidf_val * coef_val)
            direction = "increases_risk" if contrib > 0 else "decreases_risk"
            body_signals_raw.append(TextSignal(
                token=token_name,
                weight=round(float(tfidf_val), 4),
                contribution=round(contrib, 4),
                direction=direction,
                origin="body"
            ))
        pos_body = sorted([s for s in body_signals_raw if s.direction == "increases_risk"], key=lambda x: x.contribution, reverse=True)[:5]
        neg_body = sorted([s for s in body_signals_raw if s.direction == "decreases_risk"], key=lambda x: abs(x.contribution), reverse=True)[:3]
        selected_body_signals = pos_body + neg_body

        text_signals_grouped = {}
        if selected_subj_signals:
            text_signals_grouped["subject"] = selected_subj_signals
        if selected_body_signals:
            text_signals_grouped["body"] = selected_body_signals

        # 5. Model-Grounded Structural Signal Contributions (Indices 10000..10005)
        structural_signals = []
        for i, feat_name in enumerate(self.structural_names):
            coef_idx = 10000 + i
            feat_coef = float(self.coef[coef_idx])
            raw_val = float(df_struct[feat_name].iloc[0])
            scaled_val = float(X_struct_scaled[0, i])
            contrib = float(scaled_val * feat_coef)
            direction = "increases_risk" if contrib > 0 else "decreases_risk"
            
            display_val = f"{int(raw_val)}"
                
            structural_signals.append(StructuralSignal(
                feature=feat_name,
                feature_label=feat_name.replace("_", " ").title(),
                value=round(raw_val, 4),
                raw_value_display=display_val,
                contribution=round(contrib, 4),
                direction=direction,
                description=EMAIL_STRUCTURAL_DESCRIPTIONS.get(feat_name, "")
            ))
            
        structural_signals.sort(key=lambda s: abs(s.contribution), reverse=True)

        # 6. Metadata
        metadata = ModelMetadata(
            channel="Email",
            model_name="Logistic Regression",
            architecture="L2-regularized linear model (C=10.0, class_weight=None)",
            calibration="Sigmoid / Platt Scaling (CalibratedClassifierCV)",
            model_version="v1.0-lr-c10",
            trained_on="Combined 6-Source Corpus (57,320 normalized emails)",
            operational_threshold=operational_threshold
        )

        return UnifiedExplanation(
            channel="email",
            predicted_class=predicted_class,
            predicted_label=predicted_label,
            raw_score=round(raw_prob_phish, 4),
            calibrated_confidence=confidence_pct,
            operational_threshold=operational_threshold,
            structural_signals=structural_signals,
            text_signals=text_signals_grouped if text_signals_grouped else None,
            model_metadata=metadata
        )
