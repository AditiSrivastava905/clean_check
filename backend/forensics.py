"""Forensics Engine Module for CleanCheck

Implements 6 forensic checks:
1. Error Level Analysis (ELA) with color-mapped heatmap generation
2. Metadata & software editing signature detection
3. Duplicate & reuse detection via perceptual hashing (pHash) and UTR cross-checks
4. Text consistency (12-digit UTR, valid amounts, no future dates, success status)
5. Layout and noise inconsistency (sharpness & Laplacian variance disparity)
6. Missing required information penalties
"""

import io
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import imagehash
import numpy as np
from PIL import Image, ImageChops, ImageEnhance

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import (
    ELA_JPEG_QUALITY,
    ELA_SCALE_MULTIPLIER,
    OUTPUT_DIR,
    PHASH_HAMMING_THRESHOLD,
)
from backend.db import find_similar_phash_scans

logger = logging.getLogger("cleancheck.forensics")

# Known photo editing and graphic design software signatures
EDITING_SIGNATURES = [
    "photoshop", "canva", "gimp", "picsart", "snapseed", "lightroom",
    "illustrator", "pixelmator", "pixlr", "inshot", "corel", "procreate",
    "affinity", "vsco", "remini", "faceapp", "fotor", "befunky"
]


def compute_ela(image_path: Path, output_filename: str) -> Dict[str, Any]:
    """Performs Error Level Analysis (ELA).

    Re-saves the image at quality 90, calculates the absolute difference between
    the original and re-compressed pixels, amplifies the difference, and outputs
    a vivid scientific heatmap indicating potential compression artifacts and patches.
    """
    try:
        orig = Image.open(image_path).convert("RGB")
        
        # Save temp in memory at specified JPEG quality
        buffer = io.BytesIO()
        orig.save(buffer, "JPEG", quality=ELA_JPEG_QUALITY)
        buffer.seek(0)
        resaved = Image.open(buffer)

        # Calculate pixel difference and amplify
        diff = ImageChops.difference(orig, resaved)
        extrema = diff.getextrema()
        max_diff = max([ex[1] for ex in extrema]) if extrema else 0
        scale = 255.0 / max_diff if max_diff > 0 else 1.0

        # Enhance difference image
        diff_np = np.array(diff, dtype=np.float32)
        amplified = np.clip(diff_np * ELA_SCALE_MULTIPLIER, 0, 255).astype(np.uint8)

        # Convert to single channel intensity for heatmap
        gray_diff = cv2.cvtColor(amplified, cv2.COLOR_RGB2GRAY)
        
        # Apply COLORMAP_JET / COLORMAP_INFERNO for high-contrast visual inspection
        heatmap = cv2.applyColorMap(gray_diff, cv2.COLORMAP_JET)

        # Save heatmap to static/output
        out_path = OUTPUT_DIR / output_filename
        cv2.imwrite(str(out_path), heatmap)

        # Compute statistical indicators of tampering
        mean_diff = float(np.mean(gray_diff))
        std_diff = float(np.std(gray_diff))
        max_val = float(np.max(gray_diff))

        # Splitting image into grid blocks to detect localized spikes (pasted patches)
        h, w = gray_diff.shape
        block_h, block_w = max(16, h // 8), max(16, w // 8)
        block_means = []
        for y in range(0, h - block_h + 1, block_h):
            for x in range(0, w - block_w + 1, block_w):
                block = gray_diff[y : y + block_h, x : x + block_w]
                block_means.append(np.mean(block))

        max_block_mean = max(block_means) if block_means else mean_diff
        min_block_mean = min(block_means) if block_means else mean_diff
        block_disparity = max_block_mean - min_block_mean

        # Scoring heuristics
        # Standard screenshots have uniform low compression delta.
        # Modified or re-saved regions show high localized block disparity and extreme variance.
        risk_score = 0.0
        if block_disparity > 55.0 and mean_diff > 8.0:
            risk_score = min(95.0, 45.0 + (block_disparity * 0.8))
            flag = True
            detail = (
                f"High localized compression variance detected ({block_disparity:.1f} disparity). "
                "Significant digital splicing or text overlay artifacts observed in ELA heatmap."
            )
        elif block_disparity > 30.0:
            risk_score = min(35.0, 15.0 + (block_disparity * 0.4))
            flag = False
            detail = (
                f"Moderate compression fluctuation ({block_disparity:.1f}). "
                "Minor resaving or mixed compression levels present."
            )
        else:
            risk_score = min(15.0, block_disparity * 0.3)
            flag = False
            detail = (
                f"Uniform error level distribution (disparity {block_disparity:.1f}). "
                "No localized compression spikes detected."
            )

        return {
            "name": "Error Level Analysis (ELA)",
            "score": round(risk_score, 1),
            "flag": flag,
            "detail": detail,
            "heatmap_filename": output_filename,
            "stats": {
                "mean_diff": round(mean_diff, 2),
                "std_diff": round(std_diff, 2),
                "block_disparity": round(block_disparity, 2),
            },
        }

    except Exception as e:
        logger.error(f"Error Level Analysis failed: {e}", exc_info=True)
        return {
            "name": "Error Level Analysis (ELA)",
            "score": 25.0,
            "flag": False,
            "detail": f"ELA calculation encountered error: {str(e)}",
            "heatmap_filename": None,
            "stats": {},
        }


def check_metadata(image_path: Path) -> Dict[str, Any]:
    """Inspects EXIF, XMP, and container metadata for graphic editing tools."""
    try:
        img = Image.open(image_path)
        software_found = []
        raw_info = {}

        # 1. Inspect PIL info dict (e.g. PNG text chunks, software tags)
        for k, v in img.info.items():
            if isinstance(v, (str, bytes)):
                v_str = str(v).lower()
                raw_info[str(k)] = str(v)[:100]
                for tool in EDITING_SIGNATURES:
                    if tool in v_str and tool not in software_found:
                        software_found.append(tool)

        # 2. Inspect EXIF data if present
        exif = getattr(img, "_getexif", lambda: None)()
        if exif:
            for tag_id, value in exif.items():
                v_str = str(value).lower()
                for tool in EDITING_SIGNATURES:
                    if tool in v_str and tool not in software_found:
                        software_found.append(tool)

        if software_found:
            detected = ", ".join(s.capitalize() for s in software_found)
            return {
                "name": "Metadata & Software Signatures",
                "score": 90.0,
                "flag": True,
                "detail": f"Tampering indicators found: image metadata references editing software ({detected}).",
                "software_detected": software_found,
            }
        elif raw_info:
            return {
                "name": "Metadata & Software Signatures",
                "score": 10.0,
                "flag": False,
                "detail": "Standard image container metadata. No editing or manipulation tool signatures found.",
                "software_detected": [],
            }
        else:
            return {
                "name": "Metadata & Software Signatures",
                "score": 15.0,
                "flag": False,
                "detail": "No metadata tags present. Normal for native mobile screenshots (weak neutral signal).",
                "software_detected": [],
            }

    except Exception as e:
        logger.warning(f"Metadata extraction failed: {e}")
        return {
            "name": "Metadata & Software Signatures",
            "score": 15.0,
            "flag": False,
            "detail": "Metadata could not be parsed; treated as standard neutral signal.",
            "software_detected": [],
        }


def check_duplicates(
    image_path: Path,
    current_txn_id: Optional[str] = None,
    current_amount: Optional[float] = None,
) -> Tuple[Dict[str, Any], str]:
    """Calculates perceptual hash (pHash) and checks against historical scans."""
    try:
        img = Image.open(image_path)
        phash_val = str(imagehash.phash(img))

        # Query all historical scans with pHash
        past_scans = find_similar_phash_scans(phash_val)
        
        exact_or_near_dup = None
        txn_collision = None

        target_hash = imagehash.hex_to_hash(phash_val)

        for s in past_scans:
            past_phash_str = s.get("phash")
            if not past_phash_str:
                continue

            # Compute Hamming distance
            try:
                past_hash = imagehash.hex_to_hash(past_phash_str)
                dist = target_hash - past_hash
                if dist <= PHASH_HAMMING_THRESHOLD:
                    exact_or_near_dup = (s, dist)
                    break
            except Exception:
                continue

            # Also check if same UTR was submitted with different amount
            past_txn = s.get("extracted_txn_id")
            past_amt = s.get("extracted_amount")
            if (
                current_txn_id
                and past_txn
                and current_txn_id.strip() == past_txn.strip()
                and current_amount is not None
                and past_amt is not None
            ):
                if abs(float(past_amt) - float(current_amount)) > 0.01:
                    txn_collision = s
                    break

        if txn_collision:
            return {
                "name": "Duplicate & Reuse Detection",
                "score": 95.0,
                "flag": True,
                "detail": (
                    f"Transaction ID collision! UTR '{current_txn_id}' was previously submitted in Scan #{txn_collision.get('id')} "
                    f"with amount ₹{txn_collision.get('extracted_amount')}, but current screenshot claims ₹{current_amount}."
                ),
                "is_duplicate": True,
            }, phash_val

        if exact_or_near_dup:
            dup_record, dist = exact_or_near_dup
            return {
                "name": "Duplicate & Reuse Detection",
                "score": 90.0,
                "flag": True,
                "detail": (
                    f"Duplicate screenshot detected! Visually identical image (Hamming distance {dist}) was already "
                    f"analyzed in Scan #{dup_record.get('id')} on {dup_record.get('created_at')}."
                ),
                "is_duplicate": True,
            }, phash_val

        return {
            "name": "Duplicate & Reuse Detection",
            "score": 0.0,
            "flag": False,
            "detail": "Unique image submission. No matching perceptual hashes or UTR collisions in scan history.",
            "is_duplicate": False,
        }, phash_val

    except Exception as e:
        logger.error(f"Perceptual hashing failed: {e}", exc_info=True)
        return {
            "name": "Duplicate & Reuse Detection",
            "score": 20.0,
            "flag": False,
            "detail": f"Duplicate hash verification encountered error: {str(e)}",
            "is_duplicate": False,
        }, ""


def check_text_consistency(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validates structural and temporal plausibility of extracted fields."""
    reasons = []
    risk_score = 0.0
    flag = False

    txn_id = parsed_data.get("txn_id")
    amount = parsed_data.get("amount")
    dt_str = parsed_data.get("datetime")
    status = parsed_data.get("status")

    # If neither txn_id nor amount exists, this is non-payment text (unverified, not fraudulent)
    if not txn_id and amount is None:
        return {
            "name": "Text & Format Consistency",
            "score": 10.0,
            "flag": False,
            "detail": "No payment transaction text identified on image.",
        }

    # 1. UPI Reference / UTR format check (Standard Indian UPI is 12 digits)
    if txn_id:
        if not txn_id.isdigit():
            risk_score += 40.0
            reasons.append(f"Transaction ID '{txn_id}' contains non-numeric characters (standard UPI UTR is 12 digits).")
        elif len(txn_id) != 12:
            risk_score += 35.0
            reasons.append(f"Transaction ID length is {len(txn_id)} digits (standard UPI UTR is exactly 12 digits).")
    else:
        risk_score += 25.0
        reasons.append("Missing UPI reference or transaction ID number.")

    # 2. Amount format check
    if amount is not None:
        if amount <= 0:
            risk_score += 50.0
            reasons.append(f"Invalid non-positive transaction amount: ₹{amount}.")
        elif amount > 100000.0:
            # Over standard NPCI consumer UPI per-transaction limit
            risk_score += 20.0
            reasons.append(f"Amount ₹{amount:,.2f} exceeds standard retail UPI single-transaction threshold (₹1,00,000).")
    else:
        risk_score += 40.0
        reasons.append("No valid currency amount detected.")

    # 3. Temporal plausibility (Date must not be in the future)
    if dt_str:
        try:
            # Try parsing date portion
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", dt_str)
            if date_match:
                extracted_dt = datetime.strptime(date_match.group(1), "%Y-%m-%d")
                now = datetime.now()
                # If extracted date is more than 1 day in the future
                if extracted_dt.date() > now.date():
                    risk_score += 70.0
                    reasons.append(f"Future date detected ({date_match.group(1)}). Screenshot has fabricated timestamps.")
        except Exception:
            pass

    # 4. Status keyword check
    if status != "SUCCESS":
        risk_score += 30.0
        reasons.append(f"Payment status is '{status}', not confirmed SUCCESS.")

    risk_score = min(100.0, risk_score)
    flag = (risk_score >= 50.0)

    if not reasons:
        detail = "All extracted fields follow standard UPI formats (12-digit numeric UTR, valid ₹ amount, plausible date, SUCCESS status)."
    else:
        detail = "; ".join(reasons)

    return {
        "name": "Text & Format Consistency",
        "score": round(risk_score, 1),
        "flag": flag,
        "detail": detail,
    }


def check_layout_noise(
    image_path: Path,
    words: List[Dict[str, Any]],
    parsed_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Analyzes visual noise and sharpness disparities between key fields and canvas."""
    try:
        img_bgr = cv2.imread(str(image_path))
        if img_bgr is None:
            return {
                "name": "Layout & Noise Inconsistency",
                "score": 20.0,
                "flag": False,
                "detail": "Unable to read image for noise analysis.",
            }

        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Global sharpness via Laplacian variance
        global_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        # Locate bounding boxes around key elements (Amount & Txn ID)
        target_words = []
        amount_str = str(int(parsed_data.get("amount", 0))) if parsed_data.get("amount") else ""
        txn_id = parsed_data.get("txn_id") or ""

        for wd in words:
            text = wd.get("text", "")
            if (amount_str and amount_str in text) or (txn_id and txn_id[:6] in text):
                target_words.append(wd)

        roi_vars = []
        for tw in target_words:
            x, y, bw, bh = tw["x"], tw["y"], tw["w"], tw["h"]
            # Pad bounding box slightly
            px1, py1 = max(0, x - 5), max(0, y - 5)
            px2, py2 = min(w, x + bw + 5), min(h, y + bh + 5)
            roi = gray[py1:py2, px1:px2]
            if roi.size > 20:
                roi_var = float(cv2.Laplacian(roi, cv2.CV_64F).var())
                roi_vars.append(roi_var)

        risk_score = 0.0
        flag = False

        if roi_vars and global_var > 1.0:
            avg_roi_var = sum(roi_vars) / len(roi_vars)
            sharpness_ratio = avg_roi_var / global_var

            # If text is unnaturally sharper or blurrier than background canvas
            if sharpness_ratio > 3.2 or sharpness_ratio < 0.25:
                risk_score = min(85.0, 40.0 + abs(sharpness_ratio - 1.0) * 12.0)
                flag = True
                detail = (
                    f"Sharpness disparity detected around critical text (Ratio: {sharpness_ratio:.2f}x). "
                    "Font edge sharpness does not match background texture, indicating possible pasted overlay."
                )
            else:
                risk_score = 10.0
                detail = f"Consistent sharpness and noise profile across amount/ID and background canvas (Ratio: {sharpness_ratio:.2f}x)."
        else:
            # Fallback based on OCR confidence distribution
            confs = [w.get("conf", 0) for w in words if w.get("conf", 0) > 0]
            if confs and min(confs) < 30 and max(confs) > 90:
                risk_score = 25.0
                detail = "Minor confidence variance between distinct text regions; acceptable."
            else:
                risk_score = 5.0
                detail = "Uniform text rendering and background noise characteristics."

        return {
            "name": "Layout & Noise Inconsistency",
            "score": round(risk_score, 1),
            "flag": flag,
            "detail": detail,
            "global_sharpness": round(global_var, 2),
        }

    except Exception as e:
        logger.warning(f"Layout/noise analysis error: {e}")
        return {
            "name": "Layout & Noise Inconsistency",
            "score": 15.0,
            "flag": False,
            "detail": "Noise pattern analysis ran with default tolerance.",
        }


def check_missing_info(parsed_data: Dict[str, Any]) -> Dict[str, Any]:
    """Penalizes images lacking critical transaction proof fields."""
    missing = parsed_data.get("missing_fields", [])
    risk_score = 0.0
    flags = []

    if "txn_id" in missing:
        risk_score += 45.0
        flags.append("Transaction/UTR reference ID not found")
    if "amount" in missing:
        risk_score += 35.0
        flags.append("Payment amount not found")
    if "status" in missing:
        risk_score += 15.0
        flags.append("Confirmation status not found")
    if "datetime" in missing:
        risk_score += 10.0
        flags.append("Timestamp missing")

    risk_score = min(100.0, risk_score)
    flag = (risk_score >= 45.0)

    if not flags:
        detail = "All critical transaction fields (Amount, UTR ID, Date, Status) successfully extracted."
    else:
        detail = "Missing essential proof fields: " + ", ".join(flags) + "."

    return {
        "name": "Missing Required Information",
        "score": round(risk_score, 1),
        "flag": flag,
        "detail": detail,
    }


def run_all_forensic_checks(
    image_path: Path,
    parsed_data: Dict[str, Any],
    ocr_result: Dict[str, Any],
    output_filename: str,
) -> Tuple[List[Dict[str, Any]], str]:
    """Runs all 6 forensic checks in sequence and collects scores and explanations."""
    checks = []

    # 1. Error Level Analysis (ELA)
    ela_res = compute_ela(image_path, output_filename)
    checks.append(ela_res)

    # 2. Metadata check
    meta_res = check_metadata(image_path)
    checks.append(meta_res)

    # 3. Duplicate / reuse check
    dup_res, phash_str = check_duplicates(
        image_path,
        current_txn_id=parsed_data.get("txn_id"),
        current_amount=parsed_data.get("amount"),
    )
    checks.append(dup_res)

    # 4. Text consistency
    text_res = check_text_consistency(parsed_data)
    checks.append(text_res)

    # 5. Layout & noise inconsistency
    layout_res = check_layout_noise(image_path, ocr_result.get("words", []), parsed_data)
    checks.append(layout_res)

    # 6. Missing information
    missing_res = check_missing_info(parsed_data)
    checks.append(missing_res)

    return checks, phash_str
