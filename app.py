"""CleanCheck Web Application & REST API Server

Detects fake payment screenshots (UPI / bank transfer) and verifies transactions
against trusted records.

Tagline: "Don't trust the screenshot. Verify the transaction."
Event: Parakram Hackathon 26
"""

import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent))
from config import (
    ALLOWED_EXTENSIONS,
    MAX_CONTENT_LENGTH,
    OUTPUT_DIR,
    SAMPLES_DIR,
    SECRET_KEY,
    STATIC_DIR,
    UPLOAD_DIR,
)
from backend.db import (
    get_all_scans,
    get_ledger_records,
    init_db,
    insert_ledger_record,
    log_scan_result,
)
from backend.forensics import run_all_forensic_checks
from backend.ocr import is_tesseract_available, run_ocr
from backend.parser import parse_payment_details
from backend.providers import MockLedgerProvider, RealProviderStub
from backend.scoring import calculate_risk_score, determine_verdict, load_ml_model

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cleancheck.app")

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

# Initialize database schema and seeded records on startup
init_db()

# Preload ML model
load_ml_model()

# Active trusted record provider (Default: MockLedgerProvider for hackathon demo)
_RECORD_PROVIDER = MockLedgerProvider()


def allowed_file(filename: str) -> bool:
    """Validates uploaded file extensions."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    """Serves the single-page responsive application."""
    return render_template("index.html")


@app.route("/api/health", methods=["GET"])
def health_check():
    """System health, OCR status, ML status, and active provider mode."""
    records = get_ledger_records(limit=10)
    return jsonify(
        {
            "status": "online",
            "service": "CleanCheck Engine",
            "tagline": "Don't trust the screenshot. Verify the transaction.",
            "version": "1.0.0-hackathon26",
            "tesseract_available": is_tesseract_available(),
            "model_loaded": load_ml_model() is not None,
            "provider_mode": "demo" if _RECORD_PROVIDER.is_demo() else "production",
            "provider_name": _RECORD_PROVIDER.__class__.__name__,
            "ledger_records_count": len(records),
        }
    )


@app.route("/api/analyze", methods=["POST"])
def analyze_screenshot():
    """Analyzes an uploaded payment screenshot.

    Executes 5-stage verification:
    1. Validation & temporary ingestion
    2. Vision & OCR extraction
    3. Multi-layer Forensic Checks (ELA, Metadata, Duplicates, Text, Layout Noise, Missing Info)
    4. Trusted Record Matching via MockLedgerProvider
    5. Hybrid Scoring (Rule + Scikit-Learn Model) & Authoritative Verdict
    
    Security: Original uploaded image is deleted immediately after analysis.
    """
    if "image" not in request.files:
        return jsonify({"success": False, "error": "No image file provided in upload."}), 400

    file = request.files["image"]
    if file.filename == "":
        return jsonify({"success": False, "error": "Empty filename submitted."}), 400

    if not allowed_file(file.filename):
        return (
            jsonify(
                {
                    "success": False,
                    "error": f"Invalid file format. Supported extensions: {', '.join(ALLOWED_EXTENSIONS)}",
                }
            ),
            400,
        )

    scan_id = str(uuid.uuid4())
    safe_name = secure_filename(file.filename)
    extension = safe_name.rsplit(".", 1)[1].lower() if "." in safe_name else "png"
    temp_filename = f"{scan_id}_orig.{extension}"
    temp_path = UPLOAD_DIR / temp_filename

    # Save uploaded file temporarily for inspection
    file.save(temp_path)

    try:
        # Step 1: Optical Character Recognition
        ocr_result = run_ocr(temp_path)

        # Step 2: Semantic Parsing (Amount, UTR ID, Date, Parties, Status)
        parsed_data = parse_payment_details(ocr_result)

        # Step 3: Forensic Analysis (6 quantitative checks + ELA Heatmap)
        ela_filename = f"ela_{scan_id}.jpg"
        checks, phash_str = run_all_forensic_checks(
            image_path=temp_path,
            parsed_data=parsed_data,
            ocr_result=ocr_result,
            output_filename=ela_filename,
        )

        # Step 4: Trusted Record Matching (Lookup against simulated bank ledger)
        record_match = _RECORD_PROVIDER.lookup(
            txn_id=parsed_data.get("txn_id"),
            amount=parsed_data.get("amount"),
            date_str=parsed_data.get("datetime"),
        )

        # Step 5: Hybrid Risk Scoring & Authoritative Verdict
        final_risk, rule_score, ml_score, debug_info = calculate_risk_score(checks, parsed_data)
        verdict, verdict_reasons = determine_verdict(final_risk, record_match, parsed_data, checks)

        # Step 6: Log scan to database
        scan_log = {
            "scan_id": scan_id,
            "phash": phash_str,
            "extracted_txn_id": parsed_data.get("txn_id"),
            "extracted_amount": parsed_data.get("amount"),
            "extracted_date": parsed_data.get("datetime"),
            "extracted_sender": parsed_data.get("sender"),
            "extracted_receiver": parsed_data.get("receiver"),
            "extracted_app": parsed_data.get("app_name"),
            "risk_score": final_risk,
            "verdict": verdict,
            "verdict_reasons": verdict_reasons,
            "checks_json": checks,
            "match_json": record_match,
            "ela_image_name": ela_filename,
        }
        log_scan_result(scan_log)

        # Response payload
        response = {
            "success": True,
            "scan_id": scan_id,
            "status": verdict,  # VERIFIED | SUSPICIOUS | UNVERIFIED
            "risk_score": final_risk,
            "rule_score": rule_score,
            "ml_score": ml_score,
            "verdict_reasons": verdict_reasons,
            "extracted": parsed_data,
            "checks": checks,
            "record_match": record_match,
            "ela_image_url": f"/static/output/{ela_filename}",
            "mode": "demo" if _RECORD_PROVIDER.is_demo() else "production",
            "provider_name": record_match.get("provider_name"),
            "debug": debug_info,
        }
        return jsonify(response)

    except Exception as e:
        logger.error(f"Analysis failed for scan {scan_id}: {e}", exc_info=True)
        return jsonify({"success": False, "error": f"Internal analysis error: {str(e)}"}), 500

    finally:
        # NON-FUNCTIONAL PRIVACY REQUIREMENT:
        # Securely delete the uploaded original screenshot after analysis.
        # Only perceptual hash, results, and generated ELA heatmap are retained.
        if temp_path.exists():
            try:
                temp_path.unlink()
                logger.info(f"Deleted original upload artifact: {temp_path.name}")
            except Exception as e:
                logger.warning(f"Failed to delete temp upload: {e}")


@app.route("/api/history", methods=["GET"])
def get_history():
    """Retrieves previous scan history."""
    scans = get_all_scans(limit=30)
    return jsonify({"success": True, "scans": scans})


@app.route("/api/ledger", methods=["GET", "POST"])
def manage_ledger():
    """GET: Lists trusted records in demo ledger.

    POST: Inserts a new trusted transaction record so testers can simulate
    'money received' in the merchant bank account.
    """
    if request.method == "POST":
        data = request.get_json() or {}
        txn_id = str(data.get("txn_id", "")).strip()
        amount_raw = data.get("amount")

        if not txn_id:
            return jsonify({"success": False, "error": "Transaction/UTR ID is required."}), 400

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError("Amount must be positive.")
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Valid positive amount is required."}), 400

        try:
            record_id = insert_ledger_record(
                {
                    "txn_id": txn_id,
                    "amount": amount,
                    "payer_name": data.get("payer_name", "Demo Customer"),
                    "payer_vpa": data.get("payer_vpa", "customer@upi"),
                    "payee_vpa": data.get("payee_vpa", "shopeasy@hdfcbank"),
                    "timestamp": data.get("timestamp"),
                    "notes": data.get("notes", "Tester inserted entry"),
                }
            )
            return jsonify(
                {
                    "success": True,
                    "message": f"Transaction '{txn_id}' added to trusted records ledger.",
                    "id": record_id,
                }
            )
        except Exception as e:
            return jsonify({"success": False, "error": f"Failed to add ledger entry: {str(e)}"}), 400

    # GET request
    records = get_ledger_records(limit=60)
    return jsonify(
        {
            "success": True,
            "mode": "demo",
            "notice": "Demo mode: simulated trusted records",
            "records": records,
        }
    )


@app.route("/api/samples", methods=["GET"])
def list_samples():
    """Lists pre-generated test samples available for one-click testing."""
    sample_files = [
        {
            "id": "sample_genuine.png",
            "title": "Genuine Google Pay Receipt",
            "expected": "VERIFIED",
            "expected_color": "emerald",
            "desc": "Valid ₹750 payment matching seeded bank ledger entry (UTR: 428901928374). Clean compression.",
            "url": "/samples/sample_genuine.png",
        },
        {
            "id": "sample_tampered.png",
            "title": "Tampered / Forged Amount Screenshot",
            "expected": "SUSPICIOUS",
            "expected_color": "crimson",
            "desc": "Altered amount ₹7,500 vs ₹750 in ledger, spliced noise patch, and Photoshop signature in metadata.",
            "url": "/samples/sample_tampered.png",
        },
        {
            "id": "sample_duplicate.png",
            "title": "Duplicate Screenshot Re-upload",
            "expected": "SUSPICIOUS",
            "expected_color": "crimson",
            "desc": "Re-submission of identical screenshot hash to test duplicate fraud detection.",
            "url": "/samples/sample_duplicate.png",
        },
        {
            "id": "sample_non_payment.png",
            "title": "Non-Payment Image / Store Banner",
            "expected": "UNVERIFIED",
            "expected_color": "amber",
            "desc": "Store offer poster with no UPI reference or transaction details. Demonstrates default distrust.",
            "url": "/samples/sample_non_payment.png",
        },
    ]
    return jsonify({"success": True, "samples": sample_files})


@app.route("/samples/<path:filename>")
def serve_sample(filename):
    """Serves sample image files."""
    return send_from_directory(str(SAMPLES_DIR), filename)


@app.route("/static/output/<path:filename>")
def serve_output(filename):
    """Serves generated ELA heatmap image files."""
    return send_from_directory(str(OUTPUT_DIR), filename)


if __name__ == "__main__":
    logger.info("Starting CleanCheck server on http://127.0.0.1:5000")
    print("\n" + "=" * 60)
    print("  CleanCheck Prototype - Parakram Hackathon 26")
    print("  'Don't trust the screenshot. Verify the transaction.'")
    print("  Running at: http://127.0.0.1:5000")
    print("=" * 60 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
