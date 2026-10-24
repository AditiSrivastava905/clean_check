"""CleanCheck Configuration Module

Defines system-wide thresholds, forensic scoring weights, paths,
and engine parameters for the CleanCheck prototype.
"""

import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent
IS_VERCEL = bool(os.environ.get("VERCEL"))

STATIC_DIR = BASE_DIR / "static"
SAMPLES_DIR = BASE_DIR / "samples"
MODELS_DIR = BASE_DIR / "backend" / "models"

if IS_VERCEL:
    # Vercel serverless only allows writing to /tmp
    UPLOAD_DIR = Path("/tmp/uploads")
    OUTPUT_DIR = Path("/tmp/output")
    DB_PATH = Path("/tmp/cleancheck.db")
else:
    UPLOAD_DIR = STATIC_DIR / "uploads"
    OUTPUT_DIR = STATIC_DIR / "output"
    DB_PATH = BASE_DIR / "cleancheck.db"

# Ensure runtime directories exist
for path in (UPLOAD_DIR, OUTPUT_DIR, SAMPLES_DIR, MODELS_DIR):
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# Web & Security settings
SECRET_KEY = os.environ.get("CLEANCHECK_SECRET", "cleancheck-hackathon-2026-secret-key")
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB maximum file upload
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

# Forensic Analysis Weights (Normalized to sum to 1.0 or used in weighted average)
FORENSIC_WEIGHTS = {
    "ela": 0.20,              # Error Level Analysis compression variance
    "metadata": 0.10,         # Editing software exif tags / signatures
    "duplicates": 0.25,       # pHash collision or re-used UTR ID
    "text_consistency": 0.20, # UPI reference 12-digit, valid amounts, dates
    "layout_noise": 0.15,     # Noise/sharpness disparity around key text
    "missing_info": 0.10,     # Penalties for unparsed mandatory fields
}

# Decision & Risk Thresholds
RISK_THRESHOLD_SUSPICIOUS = 60.0  # Overall risk >= 60 -> Suspicious
RISK_THRESHOLD_VERIFIED_MAX = 35.0 # Max risk allowed for a "Verified" result
PHASH_HAMMING_THRESHOLD = 6      # Perceptual hash distance threshold for duplicate images
DATE_TOLERANCE_DAYS = 2          # Allowable difference between screenshot date and ledger entry

# Error Level Analysis parameters
ELA_JPEG_QUALITY = 90
ELA_SCALE_MULTIPLIER = 15

# Machine Learning Hybrid Blending
# Final Risk Score = (RULE_WEIGHT * Rule_Score) + (ML_WEIGHT * ML_Score)
RULE_WEIGHT = 0.70
ML_WEIGHT = 0.30
MODEL_PATH = MODELS_DIR / "risk_classifier.joblib"

# Tesseract OCR Executable Paths (Checked in order of priority on Windows)
TESSERACT_SEARCH_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    r"tesseract",
]
