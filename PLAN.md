# CleanCheck - Implementation Plan
**Tagline:** "Don't trust the screenshot. Verify the transaction."  
**Event:** Parakram Hackathon 26  
**Target Users:** Local shopkeepers, delivery partners, small businesses, online sellers  

---

## 1. Architecture Overview
CleanCheck is an end-to-end fake payment screenshot detection and verification engine. Its core principle is: **a screenshot alone is never proof of payment. Only a cryptographic or direct match with trusted transaction records can produce "Verified".**

The system operates across 5 distinct pipeline stages:
1. **Upload & Ingestion:** Image validation (PNG/JPG, ≤ 5 MB), hashing (SHA-256 + perceptual pHash), metadata sanitization.
2. **Vision & OCR Pipeline:** Image preprocessing (contrast enhancement, binarization, noise reduction), Tesseract OCR with bounding box & confidence extraction, and regex-driven semantic parsing (UTR/Txn ID, Amount, Date/Time, Sender, Receiver, App, Status).
3. **Forensic Analysis Engine:** 6 independent quantitative checks (0–100 risk score, flag, explanation):
   - *Error Level Analysis (ELA):* JPEG resave at Q90, amplified difference matrix, local variance and hotspot detection, heatmap generation.
   - *Metadata Tampering:* EXIF tag inspection for editing software (Photoshop, Canva, GIMP, Picsart, Snapseed, etc.).
   - *Duplicate & Reuse Detection:* Hamming distance on perceptual hashes (pHash) against historical records; same-UTR cross-check with mismatched amounts.
   - *Text Consistency & Syntactic Rules:* UTR 12-digit format, Indian currency formats, temporal plausibility, success keywords.
   - *Layout & Noise Inconsistency:* Variance of Laplacian & OCR confidence comparison between critical bounding boxes (Amount, UTR) vs background canvas.
   - *Missing Information:* Penalty scoring for omitted mandatory fields.
4. **Scoring Engine:**
   - Weighted forensic risk score based on configurable weights in `config.py`.
   - Secondary signal from a scikit-learn model trained on synthetic feature vectors.
   - Final blended risk score (0–100).
5. **Trusted Record Matching & Decision Logic:**
   - Abstract `TrustedRecordProvider` with `MockLedgerProvider` (SQLite table seeded with realistic transactions) and `RealProviderStub` (ready for authorized bank APIs).
   - Clear UI indication: *"Demo mode: simulated trusted records"*.
   - Decision states:
     - **Verified (Green):** Trusted record matches UTR + Amount + Date AND forensic risk < threshold.
     - **Suspicious (Red):** Risk ≥ 60 OR ledger mismatch (wrong amount/date) OR duplicate reuse detected.
     - **Unverified (Amber):** OCR failed / low confidence OR no trusted record found, without severe fraud indicators.

---

## 2. Implementation Phases

### Phase 1: Environment Setup & Core Dependencies
- Create `requirements.txt` (Flask, Pillow, opencv-python-headless, pytesseract, imagehash, numpy, scikit-learn, pytest).
- Install packages and configure Tesseract OCR path with automatic detection and fallbacks.
- Create `config.py` with forensic weights, decision thresholds, and file size limits.

### Phase 2: Database & Trusted Record Provider
- Create `backend/db.py`: SQLite schemas for `ledger` (trusted transactions) and `scans` (history, pHash, results).
- Seed realistic Indian payment transactions (UPI, Paytm, PhonePe, Google Pay, CRED).
- Create `backend/providers.py`:
  - `TrustedRecordProvider` (Abstract Base Class).
  - `MockLedgerProvider` with query matching, tolerance windows, and discrepancy reporting.
  - `RealProviderStub` demonstrating production banking API integration points.

### Phase 3: Vision, OCR & Forensic Analysis Engines
- Create `backend/ocr.py`: Image pre-processing (grayscale, thresholding, morphology), OCR execution via Tesseract with line/word level confidences and bounding boxes.
- Create `backend/parser.py`: Regex and heuristic parser extracting UPI reference/UTR, ₹ amounts, timestamps, sender/receiver, status, and app signatures.
- Create `backend/forensics.py`:
  - ELA generator (produces visual heatmap saved to static/output).
  - Metadata analyzer.
  - Perceptual hash calculation and duplicate detection.
  - Text & format consistency validator.
  - Visual noise & confidence anomaly analyzer.
  - Missing field checker.

### Phase 4: Machine Learning Model & Risk Scorer
- Create `scripts/train_model.py`: Generates synthetic training samples simulating genuine, edited, corrupted, and mismatched screenshots; trains a Random Forest / Logistic Regression classifier; saves `model.joblib`.
- Create `backend/scoring.py`: Combines rule-based weighted risk scores with the ML model's inference probability to produce the final calibrated risk score.

### Phase 5: REST API & Backend Orchestration
- Create `app.py` with Flask endpoints:
  - `POST /api/analyze`: Multipart upload, runs pipeline, generates ELA, returns complete analysis JSON.
  - `GET /api/history`: Returns previous scan logs with scores and verdicts.
  - `GET /api/ledger`: Retrieves trusted demo ledger entries.
  - `POST /api/ledger`: Allows testers to add custom transactions to simulate live payments.
  - `GET /api/samples`: Lists available pre-generated test samples.
  - `GET /api/health`: System health, tesseract status, and model status.
- Implement file cleanup: original uploads deleted immediately after analysis; only ELA heatmap and hashes stored.

### Phase 6: Frontend Development (Modern, Dynamic Single-Page App)
- Single-page interface served via Flask (`templates/index.html`, `static/style.css`, `static/app.js`).
- Design Aesthetics:
  - Sleek modern dark mode with glassmorphic cards, emerald/crimson/amber status glows.
  - Responsive, mobile-first layout suitable for shopkeepers and desk operators.
  - Interactive 5-stage progress animation during scanning (Upload → OCR → Forensics → Ledger Match → Verdict).
  - Prominent "Demo mode: simulated trusted records" badge.
  - Interactive Risk Gauge (0–100 SVG meter), color-coded verdict banner, detailed forensic scorecards.
  - Side-by-side interactive comparison: Original Preview vs. ELA Heatmap.
  - Tabs:
    1. **Check:** Upload / Drag-and-drop / "Try Sample" quick selector.
    2. **Scan History:** Filterable table of past scans.
    3. **Demo Ledger:** Live view of trusted records + form to insert simulated payments.

### Phase 7: Sample Generator & Automated Test Suite
- Create `scripts/generate_samples.py`:
  - Sample A: Genuine UPI screenshot matching a seeded ledger entry.
  - Sample B: Tampered screenshot (altered amount with font/noise mismatch).
  - Sample C: Duplicate re-upload test image.
  - Sample D: Non-payment random image (receipt or scenic image).
- Create automated tests with `pytest`:
  - `tests/test_parser.py`: Regex extraction tests on various payment formats.
  - `tests/test_decision.py`: Verified, Suspicious, Unverified decision matrix.
  - `tests/test_duplicates.py`: pHash Hamming distance and reuse detection.
  - `tests/test_api.py`: API endpoint response validation.

### Phase 8: Verification & Delivery
- Execute test suite (`pytest`).
- Run the server, trigger all sample flows, and verify all 3 outcomes (Verified, Suspicious, Unverified) visually and via API.
- Create comprehensive `README.md` with installation instructions, architecture diagram, 3-minute demo guide, and limitations disclosure.
