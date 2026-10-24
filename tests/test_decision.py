"""Unit tests for CleanCheck decision logic and risk scoring matrix."""

import pytest
from backend.scoring import calculate_risk_score, determine_verdict


def test_decision_verified_scenario():
    """Matches bank record AND has low forensic risk -> VERIFIED."""
    checks = [
        {"name": "Error Level Analysis (ELA)", "score": 10.0, "flag": False},
        {"name": "Metadata & Software Signatures", "score": 10.0, "flag": False},
        {"name": "Duplicate & Reuse Detection", "score": 0.0, "flag": False},
        {"name": "Text & Format Consistency", "score": 5.0, "flag": False},
        {"name": "Layout & Noise Inconsistency", "score": 8.0, "flag": False},
        {"name": "Missing Required Information", "score": 0.0, "flag": False},
    ]
    parsed_data = {
        "amount": 750.0,
        "amount_formatted": "₹750.00",
        "txn_id": "428901928374",
        "status": "SUCCESS",
        "parse_confidence": 95,
        "missing_fields": [],
    }
    record_match = {
        "found": True,
        "matched": True,
        "mismatches": [],
        "details": {"txn_id": "428901928374", "amount": 750.0},
    }

    risk_score, rule_score, ml_score, _ = calculate_risk_score(checks, parsed_data)
    assert risk_score < 35.0

    verdict, reasons = determine_verdict(risk_score, record_match, parsed_data, checks)
    assert verdict == "VERIFIED"
    assert any("Trusted Record Confirmed" in r for r in reasons)


def test_decision_suspicious_amount_mismatch():
    """Screenshot claims ₹7,500 but bank ledger only received ₹750 -> SUSPICIOUS."""
    checks = [
        {"name": "Error Level Analysis (ELA)", "score": 65.0, "flag": True},
        {"name": "Metadata & Software Signatures", "score": 90.0, "flag": True},
        {"name": "Duplicate & Reuse Detection", "score": 0.0, "flag": False},
        {"name": "Text & Format Consistency", "score": 10.0, "flag": False},
        {"name": "Layout & Noise Inconsistency", "score": 40.0, "flag": False},
        {"name": "Missing Required Information", "score": 0.0, "flag": False},
    ]
    parsed_data = {
        "amount": 7500.0,
        "amount_formatted": "₹7,500.00",
        "txn_id": "428901928374",
        "status": "SUCCESS",
        "parse_confidence": 95,
    }
    record_match = {
        "found": True,
        "matched": False,
        "mismatches": [
            "Amount mismatch: Screenshot displays ₹7,500.00, but trusted ledger record has ₹750.00."
        ],
        "details": {"txn_id": "428901928374", "amount": 750.0},
    }

    risk_score, _, _, _ = calculate_risk_score(checks, parsed_data)
    verdict, reasons = determine_verdict(risk_score, record_match, parsed_data, checks)

    assert verdict == "SUSPICIOUS"
    assert any("mismatch" in r.lower() or "discrepancy" in r.lower() for r in reasons)


def test_decision_unverified_no_ledger_record():
    """No matching ledger record exists, and no strong fraud flag -> UNVERIFIED."""
    checks = [
        {"name": "Error Level Analysis (ELA)", "score": 12.0, "flag": False},
        {"name": "Metadata & Software Signatures", "score": 10.0, "flag": False},
        {"name": "Duplicate & Reuse Detection", "score": 0.0, "flag": False},
        {"name": "Text & Format Consistency", "score": 5.0, "flag": False},
        {"name": "Layout & Noise Inconsistency", "score": 5.0, "flag": False},
        {"name": "Missing Required Information", "score": 0.0, "flag": False},
    ]
    parsed_data = {
        "amount": 350.0,
        "amount_formatted": "₹350.00",
        "txn_id": "999999999999",  # Non-existent in ledger
        "status": "SUCCESS",
        "parse_confidence": 90,
    }
    record_match = {
        "found": False,
        "matched": False,
        "mismatches": ["Transaction ID '999999999999' was not found in trusted records."],
        "details": None,
    }

    risk_score, _, _, _ = calculate_risk_score(checks, parsed_data)
    verdict, reasons = determine_verdict(risk_score, record_match, parsed_data, checks)

    # Core Security Rule: A screenshot alone is NEVER proof of payment!
    assert verdict == "UNVERIFIED"
    assert any("No matching transaction record found" in r for r in reasons)
