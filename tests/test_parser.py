"""Unit tests for OCR text and UPI payment parser."""

import pytest
from backend.parser import (
    extract_amount,
    extract_txn_id,
    extract_datetime,
    extract_app_name,
    extract_status,
    parse_payment_details,
)


def test_extract_amount_standard_inr():
    text = "Paid ₹ 750.00 to Shop Easy"
    val, fmt = extract_amount(text)
    assert val == 750.0
    assert fmt == "₹750.00"


def test_extract_amount_comma_separated():
    text = "Payment of ₹ 1,250.50 completed successfully"
    val, fmt = extract_amount(text)
    assert val == 1250.50
    assert fmt == "₹1,250.50"


def test_extract_amount_rs_prefix():
    text = "Total Paid Rs. 500 to Merchant"
    val, fmt = extract_amount(text)
    assert val == 500.0


def test_extract_txn_id_12_digits():
    text = "UPI Ref ID: 428901928374\nGoogle Transaction ID: CICAgOCz_728Xw"
    utr = extract_txn_id(text)
    assert utr == "428901928374"


def test_extract_txn_id_spaced_digits():
    text = "UPI Reference No: 4289 0192 8374"
    utr = extract_txn_id(text)
    assert utr == "428901928374"


def test_extract_app_name_detection():
    assert extract_app_name("Google Pay transaction") == "Google Pay"
    assert extract_app_name("PhonePe payment to merchant@ybl") == "PhonePe"
    assert extract_app_name("Paid via Paytm wallet") == "Paytm"
    assert extract_app_name("BHIM UPI transfer") == "BHIM"


def test_extract_status_success_and_pending():
    assert extract_status("Payment Successful - Money sent") == "SUCCESS"
    assert extract_status("Payment completed successfully") == "SUCCESS"
    assert extract_status("Transaction pending with bank") == "PENDING"
    assert extract_status("Payment failed due to timeout") == "FAILED"


def test_parse_payment_details_completeness():
    ocr_result = {
        "raw_text": (
            "Google Pay\nPayment Successful\n₹ 750.00\n"
            "Paid to Shop Easy\nUPI Ref ID: 428901928374\n"
            "24 Oct 2026, 12:30 PM\nStatus: SUCCESS"
        ),
        "words": [{"text": "750", "conf": 90}],
    }
    parsed = parse_payment_details(ocr_result)
    assert parsed["amount"] == 750.0
    assert parsed["txn_id"] == "428901928374"
    assert parsed["status"] == "SUCCESS"
    assert parsed["app_name"] == "Google Pay"
    assert parsed["parse_confidence"] >= 80
    assert "amount" not in parsed["missing_fields"]
    assert "txn_id" not in parsed["missing_fields"]
