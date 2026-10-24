"""Parser Module for CleanCheck

Parses raw OCR text from UPI and bank payment screenshots to extract
structured transaction fields (Amount, UTR / Transaction ID, Date/Time,
Sender, Receiver, Status, App name).
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def extract_amount(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Extracts payment amount in INR from text."""
    # Pattern 1: Explicit currency symbol or code followed by numbers
    # e.g., ₹ 750, ₹750.00, ₹1,250.50, Rs. 500, INR 1200
    p1 = r"(?:₹|Rs\.?|INR)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)"
    matches = re.findall(p1, text, re.IGNORECASE)

    candidates = []
    for m in matches:
        clean = m.replace(",", "").strip()
        try:
            val = float(clean)
            if 0.50 <= val <= 200000.0:  # Sensible UPI transaction range
                candidates.append((val, m))
        except ValueError:
            continue

    if candidates:
        # Prioritize largest reasonable or prominent candidate
        val, raw = candidates[0]
        return val, f"₹{val:,.2f}"

    # Pattern 2: Standalone decimals like 750.00 or 1250.00 following keywords like Paid, Total, Sent
    p2 = r"(?:paid|sent|transfer|amount|total)\s*(?:of)?\s*(?:₹|Rs\.?)?\s*([0-9]+(?:\.[0-9]{2})?)"
    m2 = re.search(p2, text, re.IGNORECASE)
    if m2:
        try:
            val = float(m2.group(1))
            if 0.50 <= val <= 200000.0:
                return val, f"₹{val:,.2f}"
        except ValueError:
            pass

    return None, None




def extract_txn_id(text: str) -> Optional[str]:
    """Extracts UPI Reference Number / UTR ID or Bank Transaction ID.

    Standard Indian UPI UTR is a 12-digit numeric identifier (e.g., 428901928374).
    Often preceded by keywords like 'UPI Ref ID', 'UTR', 'Txn ID', 'Google Transaction ID'.
    """
    # Pattern A: Preceded by explicit reference label
    label_patterns = [
        r"(?:UPI\s*(?:Ref|Reference)\s*(?:ID|No|Number)?|UTR(?:\s*No)?|Txn\s*ID|Transaction\s*ID|Google\s*Transaction\s*ID|Ref\s*No\.?)\s*[:#-]?\s*([0-9]{12})",
        r"(?:UPI\s*(?:Ref|Reference)\s*(?:ID|No)?|UTR)\s*[:#-]?\s*([0-9]{4}\s+[0-9]{4}\s+[0-9]{4})",  # Spaced 4289 0192 8374
        r"(?:UPI\s*Ref|UTR|Txn\s*ID)[:\s]+([A-Za-z0-9]{10,22})",
    ]

    for pat in label_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            candidate = match.group(1).replace(" ", "").strip()
            # If 12 digits, ideal UTR
            if candidate.isdigit() and len(candidate) == 12:
                return candidate
            if len(candidate) >= 10:
                return candidate

    # Pattern B: Search for any standalone 12-digit number (common UPI UTR format starting with 3, 4, 5, or 6)
    digits_12 = re.findall(r"\b([3-6][0-9]{11})\b", text)
    if digits_12:
        return digits_12[0]

    # Pattern C: Any 12 consecutive digits
    fallback_12 = re.findall(r"\b([0-9]{12})\b", text)
    if fallback_12:
        return fallback_12[0]

    return None


def extract_datetime(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts transaction date and time from text.

    Returns:
        (iso_datetime_str, raw_matched_str)
    """
    # Pattern 1: e.g. "24 Oct 2026, 12:30 PM" or "24 Oct 2026 12:30:15"
    p1 = r"([0-9]{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+[0-9]{4}(?:,?\s+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\s*(?:AM|PM)?)?)"
    m1 = re.search(p1, text, re.IGNORECASE)
    if m1:
        raw = m1.group(1).strip()
        return _normalize_date_string(raw), raw

    # Pattern 2: ISO or standard e.g. "2026-10-24 12:30:15" or "2026-10-24"
    p2 = r"([0-9]{4}-[0-9]{2}-[0-9]{2}(?:\s+[0-9]{2}:[0-9]{2}:[0-9]{2})?)"
    m2 = re.search(p2, text)
    if m2:
        raw = m2.group(1).strip()
        return raw, raw

    # Pattern 3: e.g. "24/10/2026" or "24-10-2026"
    p3 = r"([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4}(?:\s+[0-9]{1,2}:[0-9]{2}(?:\s*(?:AM|PM))?)?)"
    m3 = re.search(p3, text, re.IGNORECASE)
    if m3:
        raw = m3.group(1).strip()
        return _normalize_date_string(raw), raw

    # Pattern 4: "Today, 12:30 PM" or "Yesterday, 04:15 PM"
    p4 = r"((?:Today|Yesterday),?\s+[0-9]{1,2}:[0-9]{2}\s*(?:AM|PM)?)"
    m4 = re.search(p4, text, re.IGNORECASE)
    if m4:
        raw = m4.group(1).strip()
        now = datetime.now()
        date_part = now.strftime("%Y-%m-%d")
        return f"{date_part} {raw}", raw

    return None, None


def _normalize_date_string(raw_date: str) -> str:
    """Helper to convert varied date formats to ISO-like YYYY-MM-DD string."""
    formats = [
        "%d %b %Y, %I:%M %p",
        "%d %B %Y, %I:%M %p",
        "%d %b %Y %I:%M %p",
        "%d %B %Y %I:%M %p",
        "%d %b %Y",
        "%d %B %Y",
        "%d/%m/%Y, %I:%M %p",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
        "%d-%m-%Y",
    ]
    cleaned = re.sub(r"\s+", " ", raw_date).strip()
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S") if "M" in fmt or "H" in fmt else dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return cleaned


def extract_app_name(text: str) -> str:
    """Detects payment application based on app-specific strings, VPAs, and headers."""
    t_lower = text.lower()

    if "google pay" in t_lower or "gpay" in t_lower or "@okaxis" in t_lower or "@okhdfcbank" in t_lower or "@okicici" in t_lower or "@oksbi" in t_lower:
        return "Google Pay"
    if "phonepe" in t_lower or "@ybl" in t_lower or "@ibl" in t_lower or "@axl" in t_lower:
        return "PhonePe"
    if "paytm" in t_lower or "@paytm" in t_lower:
        return "Paytm"
    if "cred" in t_lower or "cred pay" in t_lower:
        return "CRED"
    if "bhim" in t_lower or "bhim upi" in t_lower:
        return "BHIM"
    if "amazon pay" in t_lower or "@apl" in t_lower:
        return "Amazon Pay"
    if "upi" in t_lower or "unified payments" in t_lower:
        return "UPI"

    return "UPI / Bank Transfer"


def extract_parties(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts sender (payer) and receiver (payee) names or VPA identifiers."""
    sender = None
    receiver = None

    # Receiver patterns
    rx_pats = [
        r"(?:Paid\s+to|To|Receiver|Credited\s+to|Merchant)[:\s]+([A-Za-z0-9\s&.]{3,35})",
        r"([a-zA-Z0-9.\-_]+@[a-zA-Z]+)",  # UPI ID
    ]
    for p in rx_pats:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Exclude false positives like "Google Pay"
            if len(val) > 2 and val.lower() not in {"google pay", "phonepe", "paytm", "bhim", "success"}:
                receiver = val
                break

    # Sender patterns
    tx_pats = [
        r"(?:From|Paid\s+by|Debited\s+from|Sender)[:\s]+([A-Za-z0-9\s&.]{3,35})",
        r"(?:Account|A/c|Bank)[:\s]+([A-Za-z0-9\s]{3,25})",
    ]
    for p in tx_pats:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if len(val) > 2 and val.lower() not in {"success", "completed", "paid"}:
                sender = val
                break

    return sender, receiver


def extract_status(text: str) -> str:
    """Detects payment status."""
    t_lower = text.lower()
    if any(k in t_lower for k in ["success", "successful", "payment successful", "completed", "paid successfully"]):
        return "SUCCESS"
    if any(k in t_lower for k in ["pending", "processing", "in progress"]):
        return "PENDING"
    if any(k in t_lower for k in ["failed", "declined", "unsuccessful", "payment failed"]):
        return "FAILED"
    return "UNKNOWN"


def parse_payment_details(ocr_result: Dict[str, Any]) -> Dict[str, Any]:
    """Main parsing orchestrator that converts OCR output into a structured record."""
    raw_text = ocr_result.get("raw_text", "")
    words = ocr_result.get("words", [])

    amount_val, amount_str = extract_amount(raw_text)
    txn_id = extract_txn_id(raw_text)
    dt_iso, dt_raw = extract_datetime(raw_text)
    app_name = extract_app_name(raw_text)
    sender, receiver = extract_parties(raw_text)
    status = extract_status(raw_text)

    # Calculate parse completeness / confidence score
    score = 0
    if amount_val is not None:
        score += 30
    if txn_id is not None:
        score += 35
    if dt_iso is not None:
        score += 15
    if status == "SUCCESS":
        score += 10
    if app_name:
        score += 5
    if sender or receiver:
        score += 5

    # Check for missing critical fields
    missing_fields = []
    if amount_val is None:
        missing_fields.append("amount")
    if txn_id is None:
        missing_fields.append("txn_id")
    if dt_iso is None and dt_raw is None:
        missing_fields.append("datetime")
    if status == "UNKNOWN":
        missing_fields.append("status")

    return {
        "amount": amount_val,
        "amount_formatted": amount_str,
        "txn_id": txn_id,
        "datetime": dt_iso or dt_raw,
        "datetime_raw": dt_raw,
        "app_name": app_name,
        "sender": sender or "Not specified",
        "receiver": receiver or "Merchant / Payee",
        "status": status,
        "parse_confidence": score,
        "missing_fields": missing_fields,
        "words_count": len(words),
        "raw_text_snippet": raw_text[:300].strip() if raw_text else "",
    }
