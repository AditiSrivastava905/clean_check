"""Scoring and Decision Engine for CleanCheck

Blends rule-based forensic checks with a secondary machine learning model,
evaluates trusted record match status, and computes the authoritative verdict:
- Verified (Green)
- Suspicious (Red)
- Unverified (Amber)

NOTE: A screenshot alone is NEVER proof of payment. Only a match with trusted
transaction records can produce "Verified".
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
import joblib
import numpy as np

# Add root directory to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import (
    FORENSIC_WEIGHTS,
    ML_WEIGHT,
    MODEL_PATH,
    RISK_THRESHOLD_SUSPICIOUS,
    RISK_THRESHOLD_VERIFIED_MAX,
    RULE_WEIGHT,
)

logger = logging.getLogger("cleancheck.scoring")

# Global cached ML model
_CACHED_MODEL = None


def load_ml_model():
    """Loads the serialized scikit-learn classifier."""
    global _CACHED_MODEL
    if _CACHED_MODEL is not None:
        return _CACHED_MODEL
    if MODEL_PATH.exists():
        try:
            _CACHED_MODEL = joblib.load(MODEL_PATH)
            logger.info("Loaded scikit-learn risk classifier successfully.")
            return _CACHED_MODEL
        except Exception as e:
            logger.warning(f"Failed to load ML model: {e}")
    return None


def calculate_risk_score(
    checks: List[Dict[str, Any]],
    parsed_data: Dict[str, Any],
) -> Tuple[float, float, float, Dict[str, Any]]:
    """Calculates weighted rule score, secondary ML model score, and final blended risk.

    Returns:
        (final_risk_score, rule_score, ml_score, debug_features)
    """
    check_map = {c.get("name", ""): c for c in checks}

    ela_score = check_map.get("Error Level Analysis (ELA)", {}).get("score", 0.0)
    meta_check = check_map.get("Metadata & Software Signatures", {})
    meta_score = meta_check.get("score", 0.0)
    meta_flag = 1.0 if meta_check.get("flag", False) else 0.0

    dup_check = check_map.get("Duplicate & Reuse Detection", {})
    dup_score = dup_check.get("score", 0.0)
    dup_flag = 1.0 if dup_check.get("flag", False) else 0.0

    text_score = check_map.get("Text & Format Consistency", {}).get("score", 0.0)
    layout_score = check_map.get("Layout & Noise Inconsistency", {}).get("score", 0.0)
    missing_score = check_map.get("Missing Required Information", {}).get("score", 0.0)
    parse_completeness = float(parsed_data.get("parse_confidence", 0.0))

    # 1. Rule-Based Weighted Score
    weighted_sum = (
        FORENSIC_WEIGHTS.get("ela", 0.20) * ela_score
        + FORENSIC_WEIGHTS.get("metadata", 0.10) * meta_score
        + FORENSIC_WEIGHTS.get("duplicates", 0.25) * dup_score
        + FORENSIC_WEIGHTS.get("text_consistency", 0.20) * text_score
        + FORENSIC_WEIGHTS.get("layout_noise", 0.15) * layout_score
        + FORENSIC_WEIGHTS.get("missing_info", 0.10) * missing_score
    )
    total_weights = sum(FORENSIC_WEIGHTS.values())
    rule_score = round(weighted_sum / total_weights, 1) if total_weights > 0 else 0.0

    # 2. Machine Learning Secondary Signal
    # Note: Trained on synthetic feature distributions for demo/hackathon purposes.
    ml_model = load_ml_model()
    ml_score = rule_score  # Default fallback
    if ml_model is not None:
        try:
            features = np.array(
                [[
                    ela_score,
                    meta_flag,
                    dup_flag,
                    text_score,
                    layout_score,
                    missing_score,
                    parse_completeness,
                ]]
            )
            # Predict probability of class 1 (Fraud/Tampered)
            prob_fraud = float(ml_model.predict_proba(features)[0][1])
            ml_score = round(prob_fraud * 100.0, 1)
        except Exception as e:
            logger.warning(f"ML inference error: {e}")
            ml_score = rule_score

    # 3. Hybrid Blended Score
    final_risk = round((RULE_WEIGHT * rule_score) + (ML_WEIGHT * ml_score), 1)

    # Clamping boundaries
    final_risk = max(0.0, min(100.0, final_risk))

    debug_info = {
        "rule_score": rule_score,
        "ml_score": ml_score,
        "blend_weights": {"rule": RULE_WEIGHT, "ml": ML_WEIGHT},
        "ml_model_info": "Random Forest trained on synthetic forensic data for demo purposes",
    }

    return final_risk, rule_score, ml_score, debug_info


def determine_verdict(
    risk_score: float,
    record_match: Dict[str, Any],
    parsed_data: Dict[str, Any],
    checks: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """Evaluates authoritative verification state and returns verdict with reasons.

    Verdicts:
    - VERIFIED: Trusted record matched UTR + amount AND forensic risk < threshold.
    - SUSPICIOUS: Risk >= 60 OR ledger mismatch OR duplicate reuse detected.
    - UNVERIFIED: No trusted record found OR OCR low confidence, without strong fraud flags.

    ABSOLUTE RULE: A screenshot alone is NEVER proof of payment.
    Never return VERIFIED without trusted record match.
    """
    reasons: List[str] = []
    check_map = {c.get("name", ""): c for c in checks}

    dup_check = check_map.get("Duplicate & Reuse Detection", {})
    meta_check = check_map.get("Metadata & Software Signatures", {})
    text_check = check_map.get("Text & Format Consistency", {})
    ela_check = check_map.get("Error Level Analysis (ELA)", {})

    has_duplicate = dup_check.get("flag", False)
    has_meta_tamper = meta_check.get("flag", False)
    has_text_anomaly = text_check.get("flag", False)
    has_ela_spike = ela_check.get("flag", False)

    record_found = record_match.get("found", False)
    record_matched = record_match.get("matched", False)
    mismatches = record_match.get("mismatches", [])

    # Scenario 1: Severe Fraud Indicators -> SUSPICIOUS
    if has_duplicate:
        reasons.append(dup_check.get("detail", "Duplicate screenshot re-upload detected."))
    if has_meta_tamper:
        reasons.append(meta_check.get("detail", "Graphic editing tool signatures discovered in file metadata."))
    if has_ela_spike:
        reasons.append(ela_check.get("detail", "Digital splicing or pasted text anomalies found via Error Level Analysis."))

    # Scenario 2: Ledger Discrepancy -> SUSPICIOUS
    if record_found and not record_matched:
        for mm in mismatches:
            reasons.append(mm)
        reasons.append("Payment record discrepancy: the screenshot details conflict with verified bank records.")

    # High Risk Score Trigger
    if risk_score >= RISK_THRESHOLD_SUSPICIOUS:
        reasons.append(
            f"Overall forensic risk score is critically high ({risk_score}/100, threshold: {RISK_THRESHOLD_SUSPICIOUS})."
        )

    if reasons or has_duplicate or (record_found and not record_matched) or risk_score >= RISK_THRESHOLD_SUSPICIOUS:
        # If any strong fraud signal or discrepancy was found
        return "SUSPICIOUS", reasons

    # Scenario 3: Valid Trusted Record Match AND Low Forensic Risk -> VERIFIED
    if record_found and record_matched:
        if risk_score <= RISK_THRESHOLD_VERIFIED_MAX:
            amt = parsed_data.get("amount_formatted") or f"₹{parsed_data.get('amount')}"
            txn = parsed_data.get("txn_id")
            ver_reasons = [
                f"Trusted Record Confirmed: Transaction ID '{txn}' verified against bank ledger.",
                f"Amount verified: ₹{record_match.get('details', {}).get('amount', 0):,.2f} credited to merchant account.",
                f"Forensic integrity passed: low risk score ({risk_score}/100) with clean compression and layout.",
            ]
            return "VERIFIED", ver_reasons
        else:
            # Trusted record matched but forensic risk is in middle zone (35 - 60)
            return "SUSPICIOUS", [
                f"Ledger record found, but image exhibits elevated forensic risk ({risk_score}/100). Manual review advised."
            ]

    # Scenario 4: No Trusted Record Found or Incomplete OCR -> UNVERIFIED
    # Remember: Never return Verified without a trusted record match!
    unverified_reasons = []

    if not record_found:
        if parsed_data.get("txn_id"):
            unverified_reasons.append(
                f"No matching transaction record found in trusted ledger for UTR ID '{parsed_data.get('txn_id')}'. "
                "Money has not yet settled or screenshot may be fabricated."
            )
        else:
            unverified_reasons.append(
                "Unable to identify a valid UPI reference / UTR ID on screenshot to query trusted records."
            )

    if parsed_data.get("parse_confidence", 0) < 50:
        unverified_reasons.append(
            "Low OCR confidence: screenshot is blurry, cropped, or non-standard format."
        )

    unverified_reasons.append(
        "Core Security Rule: A screenshot alone is NEVER proof of payment. Only records in the bank ledger verify receipt of funds."
    )

    return "UNVERIFIED", unverified_reasons
