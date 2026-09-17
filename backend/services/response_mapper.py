"""
CyberNexus - Progressive Disclosure Response Adapter
Phase 6D: Transforms model-grounded UnifiedExplanation into the unified CyberNexus API contract.
"""

from typing import Dict, Any, List, Optional, Literal
from ml.explainability.explanation_types import UnifiedExplanation


def compute_risk_score(
    predicted_class: int,
    calibrated_confidence: float,
    class_probabilities: Optional[Dict[str, float]] = None,
    benign_class_name: Optional[str] = None,
    risky_class_names: Optional[List[str]] = None,
) -> float:
    """
    Computes risk score (0.0 to 100.0) deterministically from calibrated probabilities.
    
    Binary rules:
    - Malicious prediction (class 1): risk_score = 100 * P(malicious)
    - Safe prediction (class 0): risk_score = 100 * (1 - P(safe))
    
    Multiclass rules:
    - If single benign class known: risk_score = 100 * (1 - P(benign))
    - If explicit risky classes known: risk_score = 100 * sum(P(risky))
    - If class semantics unavailable: raises ValueError (no guessing)
    """
    if class_probabilities is not None and len(class_probabilities) > 2:
        if benign_class_name is not None and benign_class_name in class_probabilities:
            p_benign = class_probabilities[benign_class_name]
            return round(100.0 * (1.0 - p_benign), 1)
        elif risky_class_names is not None:
            p_risky = sum(class_probabilities.get(c, 0.0) for c in risky_class_names)
            return round(100.0 * p_risky, 1)
        else:
            raise ValueError(
                "Multiclass model risk mapping requires explicit benign or risky class names; semantics cannot be guessed."
            )

    # Binary Channel Mapping
    p_pred = calibrated_confidence / 100.0
    if predicted_class == 1:
        # Predicted Malicious
        return round(100.0 * p_pred, 1)
    else:
        # Predicted Safe
        return round(100.0 * (1.0 - p_pred), 1)


def get_confidence_band(confidence: float) -> Literal["high", "medium", "low"]:
    """
    Derives confidence band using the locked presentation thresholds:
    < 0.65 -> low
    0.65 - 0.85 -> medium
    > 0.85 -> high
    """
    if confidence < 0.65:
        return "low"
    elif confidence <= 0.85:
        return "medium"
    else:
        return "high"


def build_confidence_breakdown(channel: str, predicted_class: int, p_pred: float) -> Dict[str, float]:
    """
    Constructs the exact 2-class calibrated probability breakdown for binary channels.
    """
    p_malicious = p_pred if predicted_class == 1 else (1.0 - p_pred)
    p_safe = 1.0 - p_malicious

    if channel == "sms":
        return {
            "ham": round(p_safe, 4),
            "spam": round(p_malicious, 4),
        }
    elif channel == "email":
        return {
            "legitimate": round(p_safe, 4),
            "phishing": round(p_malicious, 4),
        }
    elif channel == "url":
        return {
            "good": round(p_safe, 4),
            "bad": round(p_malicious, 4),
        }
    else:
        return {
            "safe": round(p_safe, 4),
            "malicious": round(p_malicious, 4),
        }


def build_tier2_flags(structural_signals: List[Any]) -> List[Dict[str, Any]]:
    """
    Maps structural signals into concise human-readable Tier 2 flags.
    """
    flags = []
    for sig in structural_signals:
        is_risk = sig.direction == "increases_risk"
        if sig.raw_value_display in ["true", "false"]:
            status_val = "warning" if (is_risk and sig.raw_value_display == "true") else ("true" if sig.raw_value_display == "true" else "false")
        else:
            status_val = "warning" if is_risk and abs(sig.contribution) > 0.05 else ("true" if sig.value > 0 else "false")

        flags.append({
            "label": sig.feature_label,
            "status": status_val,
            "detail": sig.description,
        })
    return flags


def build_reasons_and_indicators(
    verdict: str,
    predicted_class: int,
    structural_signals: List[Any],
    text_signals: Optional[Dict[str, List[Any]]] = None,
) -> tuple[List[str], List[str], str]:
    """
    Generates concise user-facing reasons, indicators, and recommendation from grounded signals.
    """
    reasons: List[str] = []
    indicators: List[str] = []

    is_threat = predicted_class == 1

    if is_threat:
        # 1. Reasons from top risk-increasing structural signals
        top_risk_structs = [s for s in structural_signals if s.direction == "increases_risk"]
        for s in top_risk_structs[:2]:
            reasons.append(f"{s.feature_label} indicates elevated risk: {s.description.lower()}.")
            indicators.append(s.feature_label)

        # 2. Reasons from top risk-increasing text signals
        if text_signals:
            pos_tokens = []
            for group in ["tokens", "subject", "body"]:
                if group in text_signals and text_signals[group]:
                    pos_tokens.extend([t.token for t in text_signals[group] if t.direction == "increases_risk"])
            if pos_tokens:
                reasons.append(f"Threat keywords detected: {', '.join(pos_tokens[:3])}.")
                indicators.append(f"Suspicious Tokens ({pos_tokens[0]})")

        if not reasons:
            reasons.append(f"Statistical anomalies in feature space match known {verdict.lower()} signatures.")
            indicators.append("Feature Anomaly Vector")

        recommendation = (
            "Do not interact with embedded links, download attachments, or provide sensitive credentials. "
            "Isolate or delete this message."
        )
    else:
        reasons = [
            "No anomalous structural or linguistic threat markers detected.",
            "All evaluated feature parameters align with baseline legitimate distributions."
        ]
        indicators = [
            "Neutral Linguistic Tone",
            "Baseline Structural Integrity"
        ]
        recommendation = "Content appears benign and safe to proceed. Maintain standard security awareness."

    return reasons, indicators, recommendation


def map_explanation_to_response(
    explanation: UnifiedExplanation,
    resolved_channel: str,
    raw_input_ref: Optional[str] = None,
    analysis_id: Optional[str] = None,
    created_at: Optional[str] = None,
    schema_version: str = "1.0",
) -> Dict[str, Any]:
    """
    Adapts a UnifiedExplanation object into the unified CyberNexus progressive disclosure contract.
    Preserves all model-grounded structural contributions, text signal weights and directions,
    calibration info, operational thresholds, and optional persistence identifiers.
    """
    channel = explanation.channel
    predicted_class = explanation.predicted_class
    verdict = explanation.predicted_label
    confidence = round(explanation.calibrated_confidence / 100.0, 4)
    confidence_band = get_confidence_band(confidence)
    risk_score = compute_risk_score(predicted_class, explanation.calibrated_confidence)

    # Tier 1 Summary
    if predicted_class == 1:
        tier1_summary = f"The input was classified as {verdict.lower()} with {confidence * 100:.1f}% confidence based on anomalous threat markers."
    else:
        tier1_summary = f"The input was verified as safe and legitimate with {confidence * 100:.1f}% confidence."

    # Tier 2: Flags & Breakdown
    tier2_flags = build_tier2_flags(explanation.structural_signals)
    confidence_breakdown = build_confidence_breakdown(channel, predicted_class, confidence)

    # Tier 3: Feature contributions (Preserving all feature values, contributions, and directions)
    feature_contributions = [
        {
            "feature": sig.feature,
            "feature_label": getattr(sig, "feature_label", sig.feature.replace("_", " ").title()),
            "value": sig.value,
            "raw_value_display": getattr(sig, "raw_value_display", str(sig.value)),
            "contribution": sig.contribution,
            "direction": sig.direction,
            "description": getattr(sig, "description", ""),
        }
        for sig in explanation.structural_signals
    ]

    # Tier 3: Text signals (Email: with source; SMS: flat without source; URL: None/omitted)
    top_text_signals: Optional[List[Dict[str, Any]]] = None
    if channel == "email" and explanation.text_signals:
        top_text_signals = []
        for src in ["subject", "body"]:
            if src in explanation.text_signals and explanation.text_signals[src]:
                for ts in explanation.text_signals[src]:
                    top_text_signals.append({
                        "token": ts.token,
                        "weight": ts.weight,
                        "contribution": getattr(ts, "contribution", None),
                        "direction": getattr(ts, "direction", None),
                        "source": src,
                    })
    elif channel == "sms" and explanation.text_signals and "tokens" in explanation.text_signals:
        top_text_signals = [
            {
                "token": ts.token,
                "weight": ts.weight,
                "contribution": getattr(ts, "contribution", None),
                "direction": getattr(ts, "direction", None),
            }
            for ts in explanation.text_signals["tokens"]
        ]
    elif channel == "url":
        # URL has no text signals; section is omitted
        top_text_signals = None

    # Tier 3: Model Metadata (Preserving all architecture and calibration metadata)
    meta = explanation.model_metadata
    model_metadata = {
        "model_name": getattr(meta, "model_name", None),
        "architecture": getattr(meta, "architecture", None),
        "calibration": getattr(meta, "calibration", None),
        "model_version": meta.model_version,
        "trained_on": meta.trained_on,
        "operational_threshold": getattr(meta, "operational_threshold", explanation.operational_threshold),
        "note": meta.note,
    }

    # Reasons, Indicators, Recommendation
    reasons, indicators, recommendation = build_reasons_and_indicators(
        verdict=verdict,
        predicted_class=predicted_class,
        structural_signals=explanation.structural_signals,
        text_signals=explanation.text_signals,
    )

    # Assemble Tier 1, Tier 2, Tier 3
    tier1 = {
        "verdict": verdict,
        "confidence": confidence,
        "confidence_band": confidence_band,
        "summary": tier1_summary,
    }

    tier2 = {
        "flags": tier2_flags,
        "confidence_breakdown": confidence_breakdown,
    }

    tier3: Dict[str, Any] = {
        "feature_contributions": feature_contributions,
        "model_metadata": model_metadata,
    }
    if top_text_signals is not None:
        tier3["top_text_signals"] = top_text_signals

    # Propagate URL native bias term if present
    bias_term = getattr(explanation, "bias_term", None)
    if bias_term is not None:
        tier3["bias_term"] = bias_term

    # Assemble Unified Contract Response
    response: Dict[str, Any] = {
        "channel": channel,
        "prediction": verdict,
        "risk_score": risk_score,
        "confidence": confidence,
        "reasons": reasons,
        "indicators": indicators,
        "recommendation": recommendation,
        "raw_input_ref": raw_input_ref,
        "tier1": tier1,
        "tier2": tier2,
        "tier3": tier3,
        "resolved_channel": resolved_channel,
        "schema_version": schema_version,
    }

    if analysis_id is not None:
        response["analysis_id"] = analysis_id
    if created_at is not None:
        response["created_at"] = created_at

    return response
